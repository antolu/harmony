from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from harmony.api.models.user import AnonymousIdentity, UserIdentity

logger = logging.getLogger(__name__)

PUBLIC_PATHS = {
    "/health",
    "/ready",
    "/auth/callback",
    "/auth/login",
    "/docs",
    "/openapi.json",
    "/api/health",
    "/api/ready",
}


class JWTAuthMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Any,
        *,
        public_key: Any,
        auth_mode: str = "optional",
        redis_client: Any,
        service_config_store: Any,
    ) -> None:
        super().__init__(app)
        self.public_key = public_key
        self.auth_mode = auth_mode
        self.redis_client = redis_client
        self.service_config_store = service_config_store

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        deny = await self._authenticate(request)
        if deny is not None:
            return deny
        return await call_next(request)

    async def _authenticate(self, request: Request) -> JSONResponse | None:
        early = await self._check_api_key(request)
        if early is not None:
            return (
                None
                if early
                else JSONResponse({"detail": "Invalid API key"}, status_code=401)
            )

        result = await self._check_jwt(request)
        if result is True:
            return None

        error_map: dict[str, JSONResponse] = {
            "revoked": JSONResponse({"detail": "Token revoked"}, status_code=401),
            "redis_error": JSONResponse(
                {"detail": "Authentication required"}, status_code=401
            ),
        }
        if isinstance(result, str) and result in error_map:
            return error_map[result]

        if self.auth_mode == "optional":
            request.state.user = AnonymousIdentity()
            return None
        return JSONResponse({"detail": "Authentication required"}, status_code=401)

    async def _check_api_key(self, request: Request) -> bool | None:
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return None
        stored = await self.service_config_store.get("service_api_key")
        if stored and api_key == stored:
            request.state.user = AnonymousIdentity(api_key=api_key)
            return True
        return False

    async def _check_jwt(self, request: Request) -> bool | str | None:
        token = (
            request.cookies.get("harmony_access")
            or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        )
        if not token:
            return None
        return await self._decode_and_validate(request, token)

    async def _decode_and_validate(
        self, request: Request, token: str
    ) -> bool | str | None:
        try:
            payload = jwt.decode(token, self.public_key, algorithms=["RS256"])
        except jwt.ExpiredSignatureError:
            await self._log_auth_failure(
                "expired_token",
                ip=request.client.host if request.client else "",
                user_id=None,
                reason="JWT expired",
            )
            return None
        except jwt.InvalidTokenError:
            await self._log_auth_failure(
                "invalid_token",
                ip=request.client.host if request.client else "",
                user_id=None,
                reason="Invalid JWT",
            )
            return None

        jti = payload.get("jti", "")
        try:
            blacklisted = await self.redis_client.get(f"jti_blacklist:{jti}")
        except Exception:
            logger.exception("Redis unavailable during JTI check — failing closed")
            return "redis_error"

        if blacklisted:
            return "revoked"
        request.state.user = UserIdentity.from_jwt(payload)
        return True

    async def _log_auth_failure(
        self, event_type: str, ip: str, user_id: str | None, reason: str
    ) -> None:
        logger.warning(
            f"Auth failure: {event_type}",
            extra={
                "event_type": event_type,
                "user_id": user_id,
                "ip": ip,
                "timestamp": datetime.now(UTC).isoformat(),
                "reason": reason,
            },
        )


def issue_access_token(user: dict, private_key_pem: str) -> str:
    jti = str(uuid.uuid4())
    now = datetime.now(UTC)
    payload = {
        "user_id": user.get("id", ""),
        "sub": user.get("sub", ""),
        "email": user.get("email"),
        "display_name": user.get("display_name"),
        "harmony_role": user.get("harmony_role", "read_only"),
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


async def store_refresh_token(user_id: str, jti: str, redis: Any) -> None:
    ttl = 7 * 24 * 3600
    await redis.setex(f"refresh:{user_id}:{jti}", ttl, "1")


async def revoke_token(
    jti: str,
    remaining_ttl: int,
    user_id: str,
    refresh_jti: str,
    redis: Any,
) -> None:
    await redis.setex(f"jti_blacklist:{jti}", remaining_ttl, "1")
    await redis.delete(f"refresh:{user_id}:{refresh_jti}")


def set_auth_cookies(
    response: Any, access_token: str, refresh_jti: str, *, secure: bool
) -> None:
    response.set_cookie(
        "harmony_access",
        access_token,
        httponly=True,
        samesite="strict",
        secure=secure,
        max_age=900,
        path="/",
    )
    response.set_cookie(
        "harmony_refresh",
        refresh_jti,
        httponly=True,
        samesite="strict",
        secure=secure,
        max_age=7 * 24 * 3600,
        path="/auth/refresh",
    )
