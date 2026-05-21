from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from harmony.api.auth._oidc_core import build_pkce_pair, discover_oidc_endpoints
from harmony.api.auth.middleware import issue_access_token, set_auth_cookies
from harmony.api.auth.user_oidc_client import UserOIDCClient, UserOIDCConfig
from harmony.api.dependencies import get_service_config_store
from harmony.api.services.admin import ServiceConfigStore
from harmony.db.connection import get_async_pool
from harmony.db.repositories import UsersRepo

logger = logging.getLogger(__name__)

router = APIRouter()


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
    return UserOIDCClient(
        UserOIDCConfig(
            issuer_url=issuer_url,
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
        )
    )


def _get_redirect_uri(request: Request) -> str:
    return str(request.base_url).rstrip("/") + "/api/auth/callback"


@router.get("/auth/login")
async def initiate_login(
    request: Request,
    redirect: str = "/admin/",
    service_config: ServiceConfigStore = Depends(get_service_config_store),
) -> RedirectResponse:
    if not redirect.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid redirect destination")

    oidc_client = await _get_oidc_client(service_config)
    await oidc_client.ensure_discovered()

    state = str(uuid.uuid4())
    verifier, _ = build_pkce_pair()

    redis = request.app.state.redis_client
    await redis.setex(f"pkce_state:{state}", 300, verifier)
    await redis.setex(f"login_redirect:{state}", 300, redirect)

    auth_url, _ = oidc_client.build_auth_url(
        redirect_uri=_get_redirect_uri(request), state=state
    )
    return RedirectResponse(url=auth_url, status_code=302)


async def _upsert_user_with_role(
    claims: dict,
    service_config: ServiceConfigStore,
) -> dict:
    pool = await get_async_pool()
    users_repo = UsersRepo(pool)
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
        mapped_role = role_mapping.get(claims[role_claim_key])
        if mapped_role:
            await users_repo.update_role(user_row["id"], mapped_role)
            user_row["harmony_role"] = mapped_role

    bootstrap_sub = await service_config.get("harmony_bootstrap_admin_sub")
    if bootstrap_sub and claims.get("sub", "") == bootstrap_sub:
        await users_repo.update_role(user_row["id"], "admin")
        user_row["harmony_role"] = "admin"

    return dict(user_row)


@router.get("/auth/callback")
async def oidc_callback(
    code: str,
    state: str,
    request: Request,
    service_config: ServiceConfigStore = Depends(get_service_config_store),
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
    claims = jwt.decode(id_token, options={"verify_signature": False})
    user_row = await _upsert_user_with_role(claims, service_config)

    access_token, jti = issue_access_token(user_row, request.app.state.jwt_private_key)
    await redis.setex(f"refresh:{user_row['id']}:{jti}", 7 * 24 * 3600, "1")

    dest_raw = await redis.get(f"login_redirect:{state}")
    await redis.delete(f"login_redirect:{state}")
    destination = (
        dest_raw.decode() if isinstance(dest_raw, bytes) else dest_raw
    ) or "/admin/"

    response = RedirectResponse(url=destination, status_code=302)
    set_auth_cookies(
        response,
        access_token,
        jti,
        secure=(request.url.scheme == "https"),
    )
    return response


@router.post("/auth/refresh")
async def refresh_token(request: Request) -> JSONResponse:
    refresh_jti = request.cookies.get("harmony_refresh")
    if not refresh_jti:
        raise HTTPException(status_code=401, detail="No refresh token")

    access_token = request.cookies.get("harmony_access")
    if not access_token:
        raise HTTPException(status_code=401, detail="No access token")

    try:
        payload = jwt.decode(
            access_token, options={"verify_signature": False}, algorithms=["RS256"]
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc

    user_id = payload.get("user_id", "")
    redis = request.app.state.redis_client

    if not await redis.get(f"refresh:{user_id}:{refresh_jti}"):
        raise HTTPException(status_code=401, detail="Refresh token invalid")

    await redis.delete(f"refresh:{user_id}:{refresh_jti}")

    pool = await get_async_pool()
    user_row = await UsersRepo(pool).get_by_id(user_id)
    if not user_row:
        raise HTTPException(status_code=401, detail="User not found")

    new_access, new_jti = issue_access_token(
        dict(user_row), request.app.state.jwt_private_key
    )
    await redis.setex(f"refresh:{user_id}:{new_jti}", 7 * 24 * 3600, "1")

    response = JSONResponse({"message": "Token refreshed"})
    set_auth_cookies(
        response,
        new_access,
        new_jti,
        secure=(request.url.scheme == "https"),
    )
    return response


@router.post("/auth/logout")
async def logout(request: Request) -> JSONResponse:
    token = request.cookies.get("harmony_access")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(
            token, options={"verify_signature": False}, algorithms=["RS256"]
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    jti = payload.get("jti", "")
    user_id = payload.get("user_id", "")
    exp = payload.get("exp", 0)

    remaining_ttl = max(0, int(exp - datetime.now(UTC).timestamp()))

    redis = request.app.state.redis_client
    await redis.setex(f"jti_blacklist:{jti}", remaining_ttl or 1, "1")
    await redis.delete(f"refresh:{user_id}:{jti}")

    logger.info(
        "User logged out",
        extra={
            "event_type": "logout",
            "user_id": user_id,
            "ip": request.client.host if request.client else "",
        },
    )

    response = JSONResponse({"message": "Logged out"})
    response.delete_cookie("harmony_access", path="/")
    response.delete_cookie("harmony_refresh", path="/auth/refresh")
    return response


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
