from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from jwt import PyJWKClient

from harmony.api.auth._oidc_core import build_pkce_pair, discover_oidc_endpoints
from harmony.api.auth.middleware import issue_access_token, set_auth_cookies
from harmony.api.auth.user_oidc_client import UserOIDCClient, UserOIDCConfig
from harmony.api.dependencies import (
    get_current_user_or_anonymous,
    get_service_config_store,
    get_users_repo,
)
from harmony.api.models.user import AnonymousIdentity, UserIdentity
from harmony.api.services.admin import ServiceConfigStore
from harmony.db.repositories import UsersRepo

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_ROLES = {"admin", "operator", "read_only"}

_ROLE_ALIASES: dict[str, str] = {"read-only": "read_only"}


async def _get_oidc_client(
    service_config: ServiceConfigStore,
) -> UserOIDCClient:
    issuer_url = await service_config.get("oidc_issuer_url")
    client_id = await service_config.get("oidc_client_id")
    if not issuer_url or not client_id:
        raise HTTPException(status_code=400, detail="OIDC not configured")
    client_secret = await service_config.get("oidc_client_secret")
    scopes_str = await service_config.get("oidc_scopes") or "openid profile email"
    scopes = scopes_str.split()
    internal_url = await service_config.get("oidc_internal_url") or ""
    return UserOIDCClient(
        UserOIDCConfig(
            issuer_url=issuer_url,
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
            internal_url=internal_url,
        )
    )


def _get_redirect_uri(request: Request) -> str:
    public_url = getattr(request.app.state, "harmony_public_url", "") or ""
    base = public_url.rstrip("/") if public_url else str(request.base_url).rstrip("/")
    return base + "/api/auth/callback"


@router.get("/auth/login")
async def initiate_login(
    request: Request,
    redirect: str = "/admin/",
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> RedirectResponse:
    if not redirect.startswith("/") or redirect.startswith("//"):
        raise HTTPException(status_code=400, detail="Invalid redirect destination")

    oidc_client = await _get_oidc_client(service_config)
    await oidc_client.ensure_discovered()

    state = str(uuid.uuid4())
    verifier, challenge = build_pkce_pair()

    redis = request.app.state.redis_client
    await redis.setex(f"pkce_state:{state}", 300, verifier)
    await redis.setex(f"login_redirect:{state}", 300, redirect)

    auth_url = oidc_client.build_auth_url_with_challenge(
        redirect_uri=_get_redirect_uri(request), state=state, code_challenge=challenge
    )
    return RedirectResponse(url=auth_url, status_code=302)


async def _upsert_user_with_role(
    claims: dict,
    service_config: ServiceConfigStore,
    users_repo: UsersRepo,
) -> dict:
    user_row = await users_repo.upsert(
        sub=claims.get("sub", ""),
        email=claims.get("email"),
        display_name=claims.get("name"),
        harmony_role="read_only",
    )

    role_claim_key = await service_config.get("oidc_role_claim_key")
    if role_claim_key and role_claim_key in claims:
        try:
            role_mapping: dict[str, str] = json.loads(
                await service_config.get("oidc_role_mapping") or "{}"
            )
        except (json.JSONDecodeError, ValueError):
            role_mapping = {}
        role_claim_value = claims[role_claim_key]
        mapped_role = role_mapping.get(role_claim_value)
        if not mapped_role:
            normalized = _ROLE_ALIASES.get(role_claim_value, role_claim_value)
            if normalized in VALID_ROLES:
                mapped_role = normalized
        if mapped_role:
            await users_repo.update_role(user_row["id"], mapped_role)
            user_row["harmony_role"] = mapped_role

    bootstrap_sub = await service_config.get("harmony_bootstrap_admin_sub")
    if bootstrap_sub and claims.get("sub", "") == bootstrap_sub:
        await users_repo.update_role(user_row["id"], "admin")
        user_row["harmony_role"] = "admin"

    return dict(user_row)


async def _verify_id_token(id_token: str, service_config: ServiceConfigStore) -> dict:
    issuer_url = await service_config.get("oidc_issuer_url")
    internal_url = await service_config.get("oidc_internal_url") or issuer_url
    client_id = await service_config.get("oidc_client_id")
    try:
        async with httpx.AsyncClient() as client:
            disc = (
                await client.get(
                    f"{internal_url.rstrip('/')}/.well-known/openid-configuration",
                    timeout=10,
                )
            ).json()
        jwks_uri = disc["jwks_uri"].replace(
            issuer_url.rstrip("/"), internal_url.rstrip("/"), 1
        )
        jwks_client = PyJWKClient(jwks_uri)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        return jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=issuer_url,
        )
    except Exception as exc:
        logger.exception(
            "id_token signature verification failed",
            extra={"event_type": "failed_oidc_callback"},
        )
        raise HTTPException(
            status_code=400, detail="id_token verification failed"
        ) from exc


@router.get("/auth/callback")
async def oidc_callback(
    code: str,
    state: str,
    request: Request,
    service_config: ServiceConfigStore = Depends(get_service_config_store),
    users_repo: UsersRepo = Depends(get_users_repo),
) -> RedirectResponse:
    redis = request.app.state.redis_client

    verifier_raw = await redis.get(f"pkce_state:{state}")
    if verifier_raw is None:
        logger.warning(
            "OIDC callback with unknown state",
            extra={"event_type": "failed_oidc_callback", "state": state},
        )
        raise HTTPException(status_code=400, detail="Unknown or expired login session")

    await redis.delete(f"pkce_state:{state}")
    verifier = (
        verifier_raw.decode() if isinstance(verifier_raw, bytes) else verifier_raw
    )

    oidc_client = await _get_oidc_client(service_config)
    await oidc_client.ensure_discovered()

    try:
        token_payload = await oidc_client.exchange_code(
            code=code,
            redirect_uri=_get_redirect_uri(request),
            code_verifier=verifier,
        )
    except Exception as exc:
        logger.exception(
            "OIDC token exchange failed",
            extra={"event_type": "failed_oidc_callback"},
        )
        raise HTTPException(status_code=400, detail="Token exchange failed") from exc

    id_token = token_payload.get("id_token", "")
    claims = await _verify_id_token(id_token, service_config)
    user_row = await _upsert_user_with_role(claims, service_config, users_repo)

    access_token, _jti = issue_access_token(user_row, request.app.state.jwt_private_key)
    refresh_jti = str(uuid.uuid4())
    user_id = str(user_row["id"])
    await redis.setex(f"refresh:{user_id}:{refresh_jti}", 7 * 24 * 3600, "1")
    await redis.setex(f"refresh_owner:{refresh_jti}", 7 * 24 * 3600, user_id)

    dest_raw = await redis.get(f"login_redirect:{state}")
    await redis.delete(f"login_redirect:{state}")
    destination = (
        dest_raw.decode() if isinstance(dest_raw, bytes) else dest_raw
    ) or "/admin/"

    response = RedirectResponse(url=destination, status_code=302)
    set_auth_cookies(
        response,
        access_token,
        refresh_jti,
        secure=(request.url.scheme == "https"),
    )
    return response


@router.post("/auth/refresh")
async def refresh_token(
    request: Request,
    users_repo: UsersRepo = Depends(get_users_repo),
) -> JSONResponse:
    refresh_jti = request.cookies.get("harmony_refresh")
    if not refresh_jti:
        raise HTTPException(status_code=401, detail="No refresh token")

    redis = request.app.state.redis_client

    user_id_raw = await redis.get(f"refresh_owner:{refresh_jti}")
    if not user_id_raw:
        raise HTTPException(status_code=401, detail="Refresh token invalid")
    user_id = user_id_raw.decode() if isinstance(user_id_raw, bytes) else user_id_raw

    if not await redis.get(f"refresh:{user_id}:{refresh_jti}"):
        raise HTTPException(status_code=401, detail="Refresh token invalid")

    await redis.delete(f"refresh:{user_id}:{refresh_jti}")
    await redis.delete(f"refresh_owner:{refresh_jti}")

    user_row = await users_repo.get_by_id(user_id)
    if not user_row:
        raise HTTPException(status_code=401, detail="User not found")

    new_access, _new_jti = issue_access_token(
        dict(user_row),  # type: ignore[arg-type]
        request.app.state.jwt_private_key,
    )
    new_refresh_jti = str(uuid.uuid4())
    ttl = 7 * 24 * 3600
    await redis.setex(f"refresh:{user_id}:{new_refresh_jti}", ttl, "1")
    await redis.setex(f"refresh_owner:{new_refresh_jti}", ttl, user_id)

    response = JSONResponse({"message": "Token refreshed"})
    set_auth_cookies(
        response,
        new_access,
        new_refresh_jti,
        secure=(request.url.scheme == "https"),
    )
    return response


async def _revoke_session(request: Request, token: str) -> None:
    try:
        payload = jwt.decode(
            token, options={"verify_signature": False}, algorithms=["RS256"]
        )
    except jwt.InvalidTokenError:
        return
    jti = payload.get("jti", "")
    user_id = payload.get("user_id", "")
    remaining_ttl = max(0, int(payload.get("exp", 0) - datetime.now(UTC).timestamp()))
    refresh_jti = request.cookies.get("harmony_refresh", "")
    redis = request.app.state.redis_client
    await redis.setex(f"jti_blacklist:{jti}", remaining_ttl or 1, "1")
    await redis.delete(f"refresh:{user_id}:{refresh_jti}")
    if refresh_jti:
        await redis.delete(f"refresh_owner:{refresh_jti}")
    logger.info(
        "User logged out",
        extra={
            "event_type": "logout",
            "user_id": user_id,
            "ip": request.client.host if request.client else "",
        },
    )


@router.get("/auth/logout")
async def logout(request: Request) -> RedirectResponse:
    token = request.cookies.get("harmony_access")
    if token:
        await _revoke_session(request, token)
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("harmony_access", path="/")
    response.delete_cookie("harmony_refresh", path="/auth/refresh")
    return response


@router.get("/me")
async def get_current_user_info(
    current_user: Annotated[
        UserIdentity | AnonymousIdentity, Depends(get_current_user_or_anonymous)
    ],
) -> dict[str, str | None]:
    if isinstance(current_user, AnonymousIdentity):
        return {
            "id": "anonymous",
            "email": None,
            "display_name": None,
            "harmony_role": "",
        }
    return {
        "id": current_user.id,
        "email": current_user.email,
        "display_name": current_user.display_name,
        "harmony_role": current_user.harmony_role,
    }


@router.post("/auth/oidc/test")
async def check_oidc_connection(
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> dict[str, str]:
    issuer_url = await service_config.get("oidc_issuer_url")
    if not issuer_url:
        raise HTTPException(status_code=400, detail="OIDC not configured")
    try:
        await discover_oidc_endpoints(issuer_url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok"}
