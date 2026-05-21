from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from harmony.api.auth.middleware import issue_access_token, store_refresh_token


@pytest.mark.asyncio
async def test_issue_access_token() -> None:
    import jwt
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_key = private_key.public_key()

    user = {
        "id": str(uuid.uuid4()),
        "sub": "sub-123",
        "email": "test@example.com",
        "display_name": "Test User",
        "harmony_role": "read_only",
    }

    token, jti = issue_access_token(user=user, private_key_pem=private_pem)
    decoded = jwt.decode(token, public_key, algorithms=["RS256"])
    assert jti == decoded["jti"]

    assert decoded["sub"] == user["sub"]
    assert decoded["email"] == user["email"]
    assert decoded["harmony_role"] == user["harmony_role"]
    assert "jti" in decoded
    assert "exp" in decoded
    assert "iat" in decoded


@pytest.mark.asyncio
async def test_refresh_token_stored() -> None:
    redis = AsyncMock()
    user_id = str(uuid.uuid4())
    jti = str(uuid.uuid4())

    await store_refresh_token(user_id=user_id, jti=jti, redis=redis)

    redis.setex.assert_called_once()
    call_args = redis.setex.call_args
    key = call_args[0][0] if call_args[0] else call_args[1].get("name", call_args[0][0])
    assert f"refresh:{user_id}:{jti}" in str(key)
