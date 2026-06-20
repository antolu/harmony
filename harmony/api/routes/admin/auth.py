from __future__ import annotations

import re
import typing
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, JsonValue

from harmony.api.dependencies import (
    get_auth_sessions_repo,
    get_config_store,
    require_role,
)
from harmony.api.models.user import AnonymousIdentity, UserIdentity
from harmony.api.services.admin import ConfigStore
from harmony.db.repositories import AuthSessionsRepo
from harmony.providers.web_crawler import OIDCAuth, OIDCAuthConfig

router = APIRouter()

OIDC_PENDING_STATE_TTL_SECONDS = 600


class AuthProvider(BaseModel):
    name: str
    type: str
    domains: list[str]
    has_session: bool = False
    flow: str | None = None


class AuthProviderListResponse(BaseModel):
    providers: list[AuthProvider]


class OIDCSession(BaseModel):
    provider: str
    created_at: datetime
    domains: list[str]


class AuthSessionListResponse(BaseModel):
    sessions: list[OIDCSession]


class LoginResponse(BaseModel):
    flow: str
    complete: bool
    auth_url: str | None = None
    message: str


class OIDCPendingState(BaseModel):
    provider: str
    verifier: str


class TestConnectionRequest(BaseModel):
    name: str
    type: str
    domains: list[str]
    issuer_url: str
    client_id: str
    client_secret: str | None = None
    flow: typing.Literal["client_credentials", "authorization_code"] = (
        "client_credentials"
    )
    scopes: list[str] = ["openid", "offline_access"]
    audience: str | None = None


class TestConnectionResponse(BaseModel):
    success: bool
    message: str


def _load_auth_config(config_store: ConfigStore) -> dict[str, dict[str, JsonValue]]:
    providers: dict[str, dict[str, JsonValue]] = {}
    for config_entry in config_store.list_configs("crawler"):
        config = config_store.get_config("crawler", config_entry.name)
        if config:
            auth_val = config.get("auth")
            if isinstance(auth_val, dict):
                providers_list = auth_val.get("providers", [])
                if isinstance(providers_list, list):
                    for provider_config in providers_list:
                        if isinstance(provider_config, dict):
                            name = str(provider_config.get("name", ""))
                            if name:
                                providers[name] = typing.cast(
                                    dict[str, JsonValue], provider_config
                                )
    return providers


def _provider_matches_subdomain(
    provider_config: dict[str, JsonValue], subdomain: str
) -> bool:
    domains = provider_config.get("domains", [])
    if isinstance(domains, list):
        for domain_pattern in domains:
            if re.search(str(domain_pattern), subdomain):
                return True
    return False


def _callback_url(request: Request) -> str:
    return str(request.base_url).rstrip("/") + "/api/auth/crawler-provider-callback"


@router.get("/providers", response_model=AuthProviderListResponse)
async def list_auth_providers(
    config_store: ConfigStore = Depends(get_config_store),
    repo: AuthSessionsRepo = Depends(get_auth_sessions_repo),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> AuthProviderListResponse:
    providers_config = _load_auth_config(config_store)
    session_rows = await repo.load_all()
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
                type=str(config.get("type", "unknown")),
                domains=typing.cast(list[str], config.get("domains", [])),
                has_session=has_session,
                flow=str(config.get("flow")) if config.get("flow") else None,
            )
        )
    return AuthProviderListResponse(providers=providers)


@router.get("/sessions", response_model=AuthSessionListResponse)
async def list_auth_sessions(
    repo: AuthSessionsRepo = Depends(get_auth_sessions_repo),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> AuthSessionListResponse:
    rows = await repo.load_all()
    sessions = []
    for row in rows:
        expires_at = row.get("expires_at")
        if expires_at and datetime.fromisoformat(expires_at) < datetime.now(UTC):
            continue
        sessions.append(
            OIDCSession(
                provider=row.get("provider_type", row["subdomain"]),
                created_at=datetime.fromisoformat(row["created_at"])
                if row.get("created_at")
                else datetime.now(UTC),
                domains=[row["subdomain"]],
            )
        )
    return AuthSessionListResponse(sessions=sessions)


@router.post("/login/{provider}", response_model=LoginResponse)
async def start_login(
    provider: str,
    request: Request,
    config_store: ConfigStore = Depends(get_config_store),
    repo: AuthSessionsRepo = Depends(get_auth_sessions_repo),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> LoginResponse:
    providers_config = _load_auth_config(config_store)

    if provider not in providers_config:
        raise HTTPException(
            status_code=404, detail=f"Provider '{provider}' not configured"
        )

    provider_config = providers_config[provider]

    if provider_config.get("type") != "oidc":
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider}' is not an OIDC provider (type: {provider_config.get('type')})",
        )

    oidc_config = OIDCAuthConfig.model_validate(provider_config)
    oidc_provider = OIDCAuth(oidc_config)
    await oidc_provider.ensure_discovered()

    if oidc_config.flow == "client_credentials":
        session = await oidc_provider.authenticate(provider)
        await repo.upsert(
            provider,
            {
                "provider_type": "oidc",
                "domain_pattern": "",
                "cookies": {},
                "headers": session.headers,
                "storage_state_file": None,
                "created_at": session.created_at.isoformat(),
                "expires_at": session.expires_at.isoformat()
                if session.expires_at
                else None,
            },
        )
        return LoginResponse(
            flow="client_credentials",
            complete=True,
            message=f"Token acquired for {provider}",
        )

    callback = _callback_url(request)
    auth_url, state, verifier = oidc_provider.build_auth_url(redirect_uri=callback)
    pending = OIDCPendingState(provider=provider, verifier=verifier)
    await request.app.state.redis_client.setex(
        f"oidc:pending:{state}",
        OIDC_PENDING_STATE_TTL_SECONDS,
        pending.model_dump_json(),
    )
    return LoginResponse(
        flow="authorization_code",
        complete=False,
        auth_url=auth_url,
        message=f"Open auth_url to complete login for {provider}",
    )


@router.get("/crawler-provider-callback")
async def oidc_callback(
    code: str,
    state: str,
    request: Request,
    config_store: ConfigStore = Depends(get_config_store),
    repo: AuthSessionsRepo = Depends(get_auth_sessions_repo),
) -> HTMLResponse:
    redis = request.app.state.redis_client
    pending_raw = await redis.get(f"oidc:pending:{state}")

    if pending_raw is None:
        return HTMLResponse(
            "<h2>Unknown or expired login session. Please try again.</h2>",
            status_code=400,
        )

    await redis.delete(f"oidc:pending:{state}")
    pending = OIDCPendingState.model_validate_json(pending_raw)

    providers_config = _load_auth_config(config_store)
    provider_config = providers_config.get(pending.provider)
    if not provider_config:
        return HTMLResponse(
            f"<h2>Provider '{pending.provider}' is no longer configured.</h2>",
            status_code=400,
        )
    oidc_config = OIDCAuthConfig.model_validate(provider_config)
    matched_provider = OIDCAuth(oidc_config)

    callback = _callback_url(request)
    try:
        await matched_provider.receive_code(
            code, pending.verifier, redirect_uri=callback
        )
    except Exception as e:
        return HTMLResponse(f"<h2>Login failed: {e}</h2>", status_code=400)

    session = matched_provider.make_session(pending.provider)
    await repo.upsert(
        pending.provider,
        {
            "provider_type": "oidc",
            "domain_pattern": "",
            "cookies": {},
            "headers": session.headers,
            "storage_state_file": None,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat()
            if session.expires_at
            else None,
        },
    )

    return HTMLResponse("""
<html><body>
<h2>Login successful. You can close this tab.</h2>
<script>window.close();</script>
</body></html>
""")


@router.get("/login/{provider}/status")
async def get_login_status(
    provider: str,
    repo: AuthSessionsRepo = Depends(get_auth_sessions_repo),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> dict[str, bool | str]:
    rows = await repo.load_all()
    has_session = any(row["subdomain"] == provider for row in rows)
    if has_session:
        return {"complete": True, "message": f"Session for {provider} is ready"}
    return {"complete": False, "message": f"Waiting for login for {provider}"}


@router.post("/providers/test", response_model=TestConnectionResponse)
async def check_new_provider_connection(
    body: TestConnectionRequest,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> TestConnectionResponse:
    try:
        oidc_config = OIDCAuthConfig(
            name=body.name,
            domains=body.domains,
            issuer_url=body.issuer_url,
            client_id=body.client_id,
            client_secret=body.client_secret,
            flow=body.flow,
            scopes=body.scopes,
            audience=body.audience,
        )
        provider = OIDCAuth(oidc_config)
        await provider.ensure_discovered()

        if body.flow == "client_credentials":
            await provider.do_client_credentials()
            return TestConnectionResponse(
                success=True, message="Token acquired successfully"
            )

        return TestConnectionResponse(
            success=True,
            message=(
                "OIDC discovery endpoint reachable. "
                "Full validation requires completing the login flow."
            ),
        )
    except httpx.HTTPStatusError as e:
        return TestConnectionResponse(
            success=False,
            message=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
        )
    except Exception as e:
        return TestConnectionResponse(success=False, message=str(e))


@router.post("/providers/{provider}/test", response_model=TestConnectionResponse)
async def check_provider_connection(
    provider: str,
    config_store: ConfigStore = Depends(get_config_store),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> TestConnectionResponse:
    providers_config = _load_auth_config(config_store)
    if provider not in providers_config:
        return TestConnectionResponse(
            success=False, message=f"Provider '{provider}' not configured"
        )
    provider_config = providers_config[provider]
    if provider_config.get("type") != "oidc":
        return TestConnectionResponse(
            success=False,
            message=f"Provider '{provider}' is not an OIDC provider",
        )
    try:
        oidc_config = OIDCAuthConfig.model_validate(provider_config)
        oidc_provider = OIDCAuth(oidc_config)
        await oidc_provider.ensure_discovered()
        if oidc_config.flow == "client_credentials":
            await oidc_provider.do_client_credentials()
            return TestConnectionResponse(
                success=True, message="Token acquired successfully"
            )
        return TestConnectionResponse(
            success=True,
            message=(
                "OIDC discovery endpoint reachable. "
                "Full validation requires completing the login flow."
            ),
        )
    except httpx.HTTPStatusError as e:
        return TestConnectionResponse(
            success=False,
            message=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
        )
    except Exception as e:
        return TestConnectionResponse(success=False, message=str(e))


@router.delete("/sessions/{provider}")
async def clear_auth_session(
    provider: str,
    config_store: ConfigStore = Depends(get_config_store),
    repo: AuthSessionsRepo = Depends(get_auth_sessions_repo),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, bool | str]:
    rows = await repo.load_all()

    providers_config = _load_auth_config(config_store)
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

    for row in matched:
        await repo.delete(row["subdomain"])
        storage_state_file = row.get("storage_state_file")
        if storage_state_file:
            storage_path = Path(storage_state_file)
            if storage_path.exists():
                storage_path.unlink()

    return {"success": True, "message": f"Session cleared for {provider}"}
