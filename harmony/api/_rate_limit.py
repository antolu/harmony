from __future__ import annotations

import logging
import time
import typing

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from harmony.api.models.user import UserIdentity

if typing.TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    import starlette.types
    from starlette.requests import Request
    from starlette.responses import Response

logger = logging.getLogger(__name__)

_WINDOW_SECONDS = 60
_CONFIG_CACHE_TTL = 10.0
_EXEMPT_PATHS = {"/health", "/ready", "/api/health", "/api/ready"}
_SEARCH_PATH_SUFFIXES = ("/search", "/ai-search", "/agentic-search")
_EXEMPT_ROLE_LEVEL = 2
_ROLE_LEVELS = {"service": 4, "admin": 3, "operator": 2, "read-only": 1, "read_only": 1}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: starlette.types.ASGIApp | None) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._config_cache: dict[str, str] = {}
        self._config_cache_at = 0.0

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        plan = await self._plan(request)
        if plan is None:
            return await call_next(request)
        key, cap = plan

        redis = request.app.state.redis_client
        try:
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, _WINDOW_SECONDS)
            if count > cap:
                retry_after = await redis.ttl(key)
        except Exception:
            logger.exception("Rate limiter Redis error — failing closed")
            return JSONResponse(
                status_code=503,
                content={"detail": "Rate limiting unavailable"},
            )

        if count > cap:
            retry_after = (
                retry_after if retry_after and retry_after > 0 else _WINDOW_SECONDS
            )
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={"detail": "Rate limit exceeded"},
            )

        return await call_next(request)

    async def _plan(self, request: Request) -> tuple[str, int] | None:
        """Return the (redis_key, cap) to enforce, or None to pass through."""
        if request.url.path in _EXEMPT_PATHS:
            return None

        app_state = request.app.state
        if app_state.service_config_store is None or app_state.redis_client is None:
            return None

        config = await self._get_config(app_state.service_config_store)
        if config.get("rate_limit_enabled", "true").lower() != "true":
            return None

        user = request.state.user if hasattr(request.state, "user") else None
        if isinstance(user, UserIdentity):
            if _ROLE_LEVELS.get(user.harmony_role, 0) >= _EXEMPT_ROLE_LEVEL:
                return None
            scope = f"user:{user.id}"
            general_cap = int(config["rate_limit_per_user_per_min"])
        else:
            if request.client is None:
                return None
            scope = f"ip:{request.client.host}"
            general_cap = int(config["rate_limit_anon_per_ip_per_min"])

        is_search = request.url.path.endswith(_SEARCH_PATH_SUFFIXES)
        cap = int(config["rate_limit_search_per_min"]) if is_search else general_cap
        bucket = "search" if is_search else "general"
        window = int(time.time()) // _WINDOW_SECONDS
        return f"ratelimit:{scope}:{bucket}:{window}", cap

    async def _get_config(self, store: typing.Any) -> dict[str, str]:
        now = time.monotonic()
        if self._config_cache and now - self._config_cache_at < _CONFIG_CACHE_TTL:
            return self._config_cache
        keys = (
            "rate_limit_enabled",
            "rate_limit_per_user_per_min",
            "rate_limit_anon_per_ip_per_min",
            "rate_limit_search_per_min",
        )
        self._config_cache = {k: await store.get(k) for k in keys}
        self._config_cache_at = now
        return self._config_cache
