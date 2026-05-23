from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from harmony.api.models.user import AnonymousIdentity, UserIdentity
from harmony.db.connection import get_async_pool
from harmony.db.repositories import ApiKeysRepo

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
        public_key: Any = None,
        auth_mode: str = "optional",
        redis_client: Any = None,
        service_config_store: Any = None,
    ) -> None:
        super().__init__(app)
        self._public_key = public_key
        self._auth_mode = auth_mode
        self._redis_client = redis_client
        self._service_config_store = service_config_store

    def _resolve_public_key(self, request: Request) -> Any:
        if self._public_key is not None:
            return self._public_key
        return getattr(request.app.state, "jwt_public_key", None)

    def _resolve_redis(self, request: Request) -> Any:
        if self._redis_client is not None:
            return self._redis_client
        return getattr(request.app.state, "redis_client", None)

    def _resolve_service_config(self, request: Request) -> Any:
        if self._service_config_store is not None:
            return self._service_config_store
        return getattr(request.app.state, "service_config_store", None)

    def _resolve_auth_mode(self, request: Request) -> str:
        if self._auth_mode != "optional":
            return self._auth_mode
        return getattr(request.app.state, "auth_mode", self._auth_mode)

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

        www_auth = {"WWW-Authenticate": 'Bearer realm="Harmony"'}
        error_map: dict[str, JSONResponse] = {
            "expired": JSONResponse(
                {"detail": "Token expired or invalid"},
                status_code=401,
                headers=www_auth,
            ),
            "revoked": JSONResponse(
                {"detail": "Token revoked"}, status_code=401, headers=www_auth
            ),
            "redis_error": JSONResponse(
                {"detail": "Authentication required"}, status_code=401, headers=www_auth
            ),
        }
        if isinstance(result, str) and result in error_map:
            return error_map[result]

        auth_mode = self._resolve_auth_mode(request)
        if auth_mode == "optional":
            request.state.user = AnonymousIdentity()
            return None
        return JSONResponse(
            {"detail": "Authentication required"},
            status_code=401,
            headers=www_auth,
        )

    async def _check_api_key(self, request: Request) -> bool | None:
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return None
        service_config_store = self._resolve_service_config(request)
        if service_config_store is None:
            return None

        stored = await service_config_store.get("service_api_key")
        if stored and api_key == stored:
            request.state.user = UserIdentity(
                id="service",
                sub="service",
                email=None,
                display_name=None,
                harmony_role="service",
                harmony_roles=["service"],
            )
            return True

        try:
            pool = await get_async_pool()
            repo = ApiKeysRepo(pool)
            harmony_role = await repo.get_harmony_role(api_key)
            if harmony_role is not None:
                key_id = hashlib.sha256(api_key.encode()).hexdigest()[:16]
                request.state.user = UserIdentity(
                    id=f"apikey:{key_id}",
                    sub=f"apikey:{key_id}",
                    email=None,
                    display_name=None,
                    harmony_role=harmony_role,
                    harmony_roles=[harmony_role],
                )
                return True
        except Exception:
            logger.exception("Error checking api_keys table")

        return False

    async def _check_jwt(self, request: Request) -> bool | str | None:
        token = request.headers.get("Authorization", "").removeprefix(
            "Bearer "
        ).strip() or request.cookies.get("harmony_access")
        if not token:
            return None
        return await self._decode_and_validate(request, token)

    async def _decode_and_validate(
        self, request: Request, token: str
    ) -> bool | str | None:
        public_key = self._resolve_public_key(request)
        try:
            payload = jwt.decode(token, public_key, algorithms=["RS256"])
        except jwt.ExpiredSignatureError:
            await self._log_auth_failure(
                "expired_token",
                ip=request.client.host if request.client else "",
                user_id=None,
                reason="JWT expired",
            )
            return "expired"
        except jwt.InvalidTokenError:
            await self._log_auth_failure(
                "invalid_token",
                ip=request.client.host if request.client else "",
                user_id=None,
                reason="Invalid JWT",
            )
            return "expired"

        jti = payload.get("jti", "")
        redis_client = self._resolve_redis(request)
        try:
            blacklisted = await redis_client.get(f"jti_blacklist:{jti}")
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


def issue_access_token(user: dict[str, Any], private_key_pem: Any) -> tuple[str, str]:
    """Issue a JWT access token. Returns (token_string, jti)."""
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
    token = jwt.encode(payload, private_key_pem, algorithm="RS256")
    return token, jti


def generate_rsa_key_pair() -> tuple[str, str]:
    """Generate a new RSA 2048-bit key pair. Returns (private_pem, public_pem)."""
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key
        .public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


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
