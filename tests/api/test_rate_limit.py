from __future__ import annotations

import types
import typing

import pytest
from starlette.responses import JSONResponse

from harmony.api._rate_limit import RateLimitMiddleware  # noqa: PLC2701
from harmony.models import AnonymousIdentity, UserIdentity


class FakeRedis:
    """Async in-memory Redis stand-in for INCR/EXPIRE/TTL fixed-window logic."""

    def __init__(self, *, fail: bool = False) -> None:
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self._fail = fail

    async def incr(self, key: str) -> int:
        if self._fail:
            msg = "redis down"
            raise ConnectionError(msg)
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> None:
        if self._fail:
            msg = "redis down"
            raise ConnectionError(msg)
        self.ttls[key] = seconds

    async def ttl(self, key: str) -> int:
        if self._fail:
            msg = "redis down"
            raise ConnectionError(msg)
        return self.ttls.get(key, -1)


class FakeServiceConfig:
    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    async def get(self, key: str) -> str:
        return self._values[key]


def _make_request(
    path: str,
    user: UserIdentity | AnonymousIdentity | None,
    redis: FakeRedis,
    config: FakeServiceConfig,
    client_host: str = "1.2.3.4",
) -> typing.Any:
    app_state = types.SimpleNamespace(redis_client=redis, service_config_store=config)
    app = types.SimpleNamespace(state=app_state)
    state = types.SimpleNamespace()
    if user is not None:
        state.user = user
    client = types.SimpleNamespace(host=client_host)
    url = types.SimpleNamespace(path=path)
    return types.SimpleNamespace(app=app, state=state, client=client, url=url)


def _default_config(**overrides: str) -> FakeServiceConfig:
    values = {
        "rate_limit_enabled": "true",
        "rate_limit_per_user_per_min": "5",
        "rate_limit_anon_per_ip_per_min": "3",
        "rate_limit_search_per_min": "2",
    }
    values.update(overrides)
    return FakeServiceConfig(values)


def _user(role: str) -> UserIdentity:
    return UserIdentity(
        id=f"u-{role}",
        sub=f"u-{role}",
        email=None,
        display_name=None,
        harmony_role=role,
        harmony_roles=[role],
    )


async def _call(mw: RateLimitMiddleware, request: typing.Any) -> typing.Any:
    sentinel = JSONResponse({"ok": True})

    async def call_next(_req: typing.Any) -> typing.Any:
        return sentinel

    return await mw.dispatch(request, call_next)


@pytest.fixture
def mw() -> RateLimitMiddleware:
    return RateLimitMiddleware(app=None)


@pytest.mark.asyncio
async def test_under_limit_passes_through(mw: RateLimitMiddleware) -> None:
    redis = FakeRedis()
    req = _make_request("/api/x", _user("read_only"), redis, _default_config())
    resp = await _call(mw, req)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_over_user_limit_returns_429_with_retry_after(
    mw: RateLimitMiddleware,
) -> None:
    redis = FakeRedis()
    config = _default_config(rate_limit_per_user_per_min="2")
    req = _make_request("/api/x", _user("read_only"), redis, config)
    await _call(mw, req)
    await _call(mw, req)
    resp = await _call(mw, req)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


@pytest.mark.asyncio
async def test_anonymous_keyed_by_ip(mw: RateLimitMiddleware) -> None:
    redis = FakeRedis()
    config = _default_config(rate_limit_anon_per_ip_per_min="1")
    req_a = _make_request("/api/x", AnonymousIdentity(), redis, config, "10.0.0.1")
    req_b = _make_request("/api/x", AnonymousIdentity(), redis, config, "10.0.0.2")
    assert (await _call(mw, req_a)).status_code == 200
    # different IP not affected by req_a's count
    assert (await _call(mw, req_b)).status_code == 200
    # same IP as req_a now over the cap of 1
    assert (await _call(mw, req_a)).status_code == 429


@pytest.mark.asyncio
async def test_search_endpoint_uses_tighter_cap(mw: RateLimitMiddleware) -> None:
    redis = FakeRedis()
    config = _default_config(
        rate_limit_per_user_per_min="100", rate_limit_search_per_min="1"
    )
    req = _make_request("/api/ai-search", _user("read_only"), redis, config)
    assert (await _call(mw, req)).status_code == 200
    assert (await _call(mw, req)).status_code == 429


@pytest.mark.asyncio
async def test_admin_is_exempt(mw: RateLimitMiddleware) -> None:
    redis = FakeRedis()
    config = _default_config(rate_limit_per_user_per_min="1")
    req = _make_request("/api/x", _user("admin"), redis, config)
    for _ in range(5):
        assert (await _call(mw, req)).status_code == 200


@pytest.mark.asyncio
async def test_operator_is_exempt(mw: RateLimitMiddleware) -> None:
    redis = FakeRedis()
    config = _default_config(rate_limit_per_user_per_min="1")
    req = _make_request("/api/x", _user("operator"), redis, config)
    for _ in range(5):
        assert (await _call(mw, req)).status_code == 200


@pytest.mark.asyncio
async def test_disabled_passes_through(mw: RateLimitMiddleware) -> None:
    redis = FakeRedis()
    config = _default_config(
        rate_limit_enabled="false", rate_limit_per_user_per_min="1"
    )
    req = _make_request("/api/x", _user("read_only"), redis, config)
    for _ in range(5):
        assert (await _call(mw, req)).status_code == 200


@pytest.mark.asyncio
async def test_redis_failure_fails_closed(mw: RateLimitMiddleware) -> None:
    redis = FakeRedis(fail=True)
    req = _make_request("/api/x", _user("read_only"), redis, _default_config())
    resp = await _call(mw, req)
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_public_path_not_limited(mw: RateLimitMiddleware) -> None:
    redis = FakeRedis()
    config = _default_config(rate_limit_anon_per_ip_per_min="1")
    # no user set on state (JWTAuth skips PUBLIC_PATHS), health path
    req = _make_request("/health", None, redis, config)
    for _ in range(5):
        assert (await _call(mw, req)).status_code == 200
