from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from harmony.api.auth.middleware import JWTAuthMiddleware


@pytest.fixture
def _app_with_middleware() -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(
        JWTAuthMiddleware,
        public_key=None,
        auth_mode="required",
        redis_client=AsyncMock(),
        service_config_store=MagicMock(),
    )

    @test_app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @test_app.get("/protected")
    async def protected() -> dict[str, str]:
        return {"data": "secret"}

    return test_app


def test_valid_jwt_passes() -> None:
    import uuid
    from datetime import UTC, datetime, timedelta

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

    payload = {
        "sub": "user-123",
        "email": "user@example.com",
        "harmony_role": "read_only",
        "jti": str(uuid.uuid4()),
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, private_pem, algorithm="RS256")

    test_app = FastAPI()
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)

    test_app.add_middleware(
        JWTAuthMiddleware,
        public_key=private_key.public_key(),
        auth_mode="required",
        redis_client=redis_mock,
        service_config_store=MagicMock(),
    )

    @test_app.get("/protected")
    async def protected() -> dict[str, str]:
        return {"data": "secret"}

    client = TestClient(test_app, raise_server_exceptions=False)
    response = client.get("/protected", cookies={"harmony_access": token})
    assert response.status_code == 200


def test_public_paths() -> None:
    test_app = FastAPI()
    test_app.add_middleware(
        JWTAuthMiddleware,
        public_key=None,
        auth_mode="required",
        redis_client=AsyncMock(),
        service_config_store=MagicMock(),
    )

    @test_app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(test_app, raise_server_exceptions=False)
    response = client.get("/health")
    assert response.status_code == 200


def test_api_key_bypass() -> None:
    test_app = FastAPI()
    service_config_store = MagicMock()
    service_config_store.get = AsyncMock(return_value="test-api-key-12345")

    test_app.add_middleware(
        JWTAuthMiddleware,
        public_key=None,
        auth_mode="required",
        redis_client=AsyncMock(),
        service_config_store=service_config_store,
    )

    @test_app.get("/protected")
    async def protected() -> dict[str, str]:
        return {"data": "secret"}

    client = TestClient(test_app, raise_server_exceptions=False)
    response = client.get("/protected", headers={"X-API-Key": "test-api-key-12345"})
    assert response.status_code == 200


def test_optional_mode_anonymous() -> None:

    test_app = FastAPI()
    test_app.add_middleware(
        JWTAuthMiddleware,
        public_key=None,
        auth_mode="optional",
        redis_client=AsyncMock(),
        service_config_store=MagicMock(),
    )

    @test_app.get("/protected")
    async def protected() -> dict[str, str]:
        return {"data": "ok"}

    client = TestClient(test_app, raise_server_exceptions=False)
    response = client.get("/protected")
    assert response.status_code == 200


def test_blacklisted_jti() -> None:
    import uuid
    from datetime import UTC, datetime, timedelta

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

    jti = str(uuid.uuid4())
    payload = {
        "sub": "user-123",
        "email": "user@example.com",
        "harmony_role": "read_only",
        "jti": jti,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, private_pem, algorithm="RS256")

    test_app = FastAPI()
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=b"1")

    test_app.add_middleware(
        JWTAuthMiddleware,
        public_key=private_key.public_key(),
        auth_mode="required",
        redis_client=redis_mock,
        service_config_store=MagicMock(),
    )

    @test_app.get("/protected")
    async def protected() -> dict[str, str]:
        return {"data": "secret"}

    client = TestClient(test_app, raise_server_exceptions=False)
    response = client.get("/protected", cookies={"harmony_access": token})
    assert response.status_code == 401


def test_failure_logged() -> None:
    import logging

    test_app = FastAPI()
    test_app.add_middleware(
        JWTAuthMiddleware,
        public_key=None,
        auth_mode="required",
        redis_client=AsyncMock(),
        service_config_store=MagicMock(),
    )

    @test_app.get("/protected")
    async def protected() -> dict[str, str]:
        return {"data": "secret"}

    with patch.object(
        logging.getLogger("harmony.api.auth.middleware"), "warning"
    ) as mock_warn:
        client = TestClient(test_app, raise_server_exceptions=False)
        client.get("/protected", cookies={"harmony_access": "invalid-jwt-token"})
        mock_warn.assert_called()
        call_kwargs = mock_warn.call_args
        assert call_kwargs is not None
