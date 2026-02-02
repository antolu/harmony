from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from harmony.api.config import settings

router = APIRouter()


class AuthProvider(BaseModel):
    name: str
    type: str
    domains: list[str]
    has_session: bool = False


class AuthSession(BaseModel):
    provider: str
    created_at: datetime
    domains: list[str]


class SSOLoginResponse(BaseModel):
    vnc_url: str
    session_id: str
    message: str


class AuthProviderListResponse(BaseModel):
    providers: list[AuthProvider]


class AuthSessionListResponse(BaseModel):
    sessions: list[AuthSession]


def _get_session_path(provider: str) -> Path:
    return settings.auth_sessions_path / f"{provider}.json"


def _load_auth_config() -> dict[str, dict]:
    """Load auth providers from config store."""
    from harmony.api.services.admin.config_store import config_store  # noqa: PLC0415

    providers = {}
    for config_entry in config_store.list_configs("crawler"):
        config = config_store.get_config("crawler", config_entry.name)
        if config and config.get("auth"):
            auth = config["auth"]
            for provider_config in auth.get("providers", []):
                name = provider_config.get("name", "")
                if name:
                    providers[name] = provider_config
    return providers


@router.get("/providers", response_model=AuthProviderListResponse)
async def list_auth_providers() -> AuthProviderListResponse:
    """List configured authentication providers."""
    providers_config = _load_auth_config()
    providers = []

    for name, config in providers_config.items():
        session_path = _get_session_path(name)
        providers.append(
            AuthProvider(
                name=name,
                type=config.get("type", "unknown"),
                domains=config.get("domains", []),
                has_session=session_path.exists(),
            )
        )

    return AuthProviderListResponse(providers=providers)


@router.get("/sessions", response_model=AuthSessionListResponse)
async def list_auth_sessions() -> AuthSessionListResponse:
    """List active crawler auth sessions."""
    sessions = []

    if not settings.auth_sessions_path.exists():
        return AuthSessionListResponse(sessions=[])

    for session_file in settings.auth_sessions_path.glob("*.json"):
        try:
            data = json.loads(session_file.read_text())
            sessions.append(
                AuthSession(
                    provider=session_file.stem,
                    created_at=datetime.fromisoformat(data.get("created_at", "")),
                    domains=data.get("domains", []),
                )
            )
        except Exception:
            continue

    return AuthSessionListResponse(sessions=sessions)


@router.post("/login/{provider}", response_model=SSOLoginResponse)
async def start_sso_login(provider: str) -> SSOLoginResponse:
    """Start SSO login for a provider (returns noVNC URL)."""
    from harmony.api.services.admin.sso_handler import sso_handler  # noqa: PLC0415

    providers_config = _load_auth_config()

    if provider not in providers_config:
        raise HTTPException(
            status_code=404, detail=f"Provider '{provider}' not configured"
        )

    provider_config = providers_config[provider]
    provider_type = provider_config.get("type", "")

    if provider_type not in {"sso", "browser"}:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider}' is not an SSO provider (type: {provider_type})",
        )

    # Get login URL from provider config
    login_url = provider_config.get("login_url", "")
    if not login_url:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider}' missing 'login_url' configuration",
        )

    session_id = f"{provider}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"

    # Start browser container
    try:
        vnc_info = await sso_handler.start_browser_session(
            session_id, provider, login_url
        )
        vnc_url = (
            f"{settings.novnc_url}/vnc.html?"
            f"host={vnc_info['vnc_host']}&"
            f"port={vnc_info['vnc_port']}&"
            f"autoconnect=true&"
            f"resize=scale"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start SSO browser: {e!s}"
        ) from e

    return SSOLoginResponse(
        vnc_url=vnc_url,
        session_id=session_id,
        message=f"Open the VNC URL to complete login for {provider}",
    )


@router.get("/login/{provider}/status")
async def get_login_status(provider: str) -> dict[str, bool | str]:
    """Check if SSO login has been completed."""
    session_path = _get_session_path(provider)

    if session_path.exists():
        return {
            "complete": True,
            "message": f"Session for {provider} is ready",
        }

    return {
        "complete": False,
        "message": f"Waiting for login completion for {provider}",
    }


@router.post("/login/{provider}/complete")
async def complete_sso_login(provider: str) -> dict[str, bool | str]:
    """Finalize SSO login (called after browser session completes)."""
    from harmony.api.services.admin.sso_handler import sso_handler  # noqa: PLC0415

    # Find the session ID for this provider
    session_id = None
    for sid, _ in sso_handler.active_containers.items():
        if sid.startswith(provider):
            session_id = sid
            break

    if not session_id:
        raise HTTPException(
            status_code=404, detail=f"No active SSO session for provider '{provider}'"
        )

    # Extract and save session data
    session_path = _get_session_path(provider)
    try:
        await sso_handler.save_session(session_id, provider, session_path)
        # Stop the browser container
        await sso_handler.stop_browser_session(session_id)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to complete SSO login: {e!s}"
        ) from e

    return {
        "success": True,
        "message": f"Session saved for {provider}",
    }


@router.delete("/sessions/{provider}")
async def clear_auth_session(provider: str) -> dict[str, bool | str]:
    """Clear an auth session."""
    from harmony.api.services.admin.sso_handler import sso_handler  # noqa: PLC0415

    session_path = _get_session_path(provider)

    if not session_path.exists():
        raise HTTPException(
            status_code=404, detail=f"No session found for '{provider}'"
        )

    # Stop any active SSO browser sessions for this provider
    for session_id in list(sso_handler.active_containers.keys()):
        if session_id.startswith(provider):
            await sso_handler.stop_browser_session(session_id)

    session_path.unlink()

    return {
        "success": True,
        "message": f"Session cleared for {provider}",
    }
