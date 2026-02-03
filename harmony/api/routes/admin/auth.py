from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from harmony.api.admin_config import settings as admin_settings
from harmony.db.connection import get_async_pool
from harmony.db.repositories import AuthSessionsRepo

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


def _provider_matches_subdomain(provider_config: dict, subdomain: str) -> bool:
    """Check if a subdomain matches any of the provider's domain patterns."""
    for domain_pattern in provider_config.get("domains", []):
        if re.search(domain_pattern, subdomain):
            return True
    return False


@router.get("/providers", response_model=AuthProviderListResponse)
async def list_auth_providers() -> AuthProviderListResponse:
    """List configured authentication providers."""
    providers_config = _load_auth_config()
    pool = await get_async_pool()
    session_rows = await AuthSessionsRepo(pool).load_all()
    session_subdomains = {row["subdomain"] for row in session_rows}

    providers = []
    for name, config in providers_config.items():
        has_session = (
            any(_provider_matches_subdomain(config, sub) for sub in session_subdomains)
            or name in session_subdomains
        )

        providers.append(
            AuthProvider(
                name=name,
                type=config.get("type", "unknown"),
                domains=config.get("domains", []),
                has_session=has_session,
            )
        )

    return AuthProviderListResponse(providers=providers)


@router.get("/sessions", response_model=AuthSessionListResponse)
async def list_auth_sessions() -> AuthSessionListResponse:
    """List active crawler auth sessions."""
    pool = await get_async_pool()
    rows = await AuthSessionsRepo(pool).load_all()

    sessions = []
    for row in rows:
        expires_at = row.get("expires_at")
        if expires_at and expires_at < datetime.now(UTC):
            continue
        sessions.append(
            AuthSession(
                provider=row.get("provider_type", row["subdomain"]),
                created_at=row.get("created_at") or datetime.now(UTC),
                domains=[row["subdomain"]],
            )
        )

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

    login_url = provider_config.get("login_url", "")
    if not login_url:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider}' missing 'login_url' configuration",
        )

    session_id = f"{provider}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"

    try:
        vnc_info = await sso_handler.start_browser_session(
            session_id, provider, login_url
        )
        vnc_url = (
            f"{admin_settings.novnc_url}/vnc.html?"
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
    pool = await get_async_pool()
    rows = await AuthSessionsRepo(pool).load_all()

    providers_config = _load_auth_config()
    provider_config = providers_config.get(provider, {})

    has_session = any(
        row["subdomain"] == provider
        or _provider_matches_subdomain(provider_config, row["subdomain"])
        for row in rows
    )

    if has_session:
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

    session_id = None
    for sid in sso_handler.active_containers:
        if sid.startswith(provider):
            session_id = sid
            break

    if not session_id:
        raise HTTPException(
            status_code=404, detail=f"No active SSO session for provider '{provider}'"
        )

    try:
        storage_state_file = sso_handler.session_storage_path / f"{provider}.json"
        await sso_handler.save_session(session_id, provider, storage_state_file)
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

    pool = await get_async_pool()
    repo = AuthSessionsRepo(pool)
    rows = await repo.load_all()

    providers_config = _load_auth_config()
    provider_config = providers_config.get(provider, {})

    matched = [
        row
        for row in rows
        if row["subdomain"] == provider
        or _provider_matches_subdomain(provider_config, row["subdomain"])
    ]

    if not matched:
        raise HTTPException(
            status_code=404, detail=f"No session found for '{provider}'"
        )

    for session_id in list(sso_handler.active_containers.keys()):
        if session_id.startswith(provider):
            await sso_handler.stop_browser_session(session_id)

    for row in matched:
        await repo.delete(row["subdomain"])
        if row.get("storage_state_file"):
            storage_path = Path(row["storage_state_file"])
            if storage_path.exists():
                storage_path.unlink()

    return {
        "success": True,
        "message": f"Session cleared for {provider}",
    }
