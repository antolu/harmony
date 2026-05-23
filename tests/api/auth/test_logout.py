from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from harmony.api.auth.middleware import revoke_token


@pytest.mark.asyncio
async def test_jti_blacklisted() -> None:
    redis = AsyncMock()
    jti = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    remaining_ttl = 600

    await revoke_token(
        jti=jti,
        remaining_ttl=remaining_ttl,
        user_id=user_id,
        refresh_jti=jti,
        redis=redis,
    )

    redis.setex.assert_called_once()
    call_args = redis.setex.call_args
    key = call_args[0][0] if call_args[0] else call_args[1].get("name", call_args[0][0])
    assert f"jti_blacklist:{jti}" in str(key)
    assert "1" in str(call_args)


@pytest.mark.asyncio
async def test_refresh_deleted() -> None:
    redis = AsyncMock()
    jti = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    await revoke_token(
        jti=jti, remaining_ttl=100, user_id=user_id, refresh_jti=jti, redis=redis
    )

    redis.delete.assert_called_once()
    call_args = redis.delete.call_args
    deleted_key = call_args[0][0] if call_args[0] else next(iter(call_args[1].values()))
    assert f"refresh:{user_id}:{jti}" in str(deleted_key)
