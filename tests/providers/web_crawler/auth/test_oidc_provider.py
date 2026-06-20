from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harmony.providers.web_crawler.auth.config import OIDCAuthConfig
from harmony.providers.web_crawler.auth.providers.oidc import (
    OIDCAuth,
    build_pkce_pair,
)


def _make_config(**kwargs: str | list[str] | bool | int | None) -> OIDCAuthConfig:
    defaults: dict[str, str | list[str] | bool | int | None] = {
        "name": "test-oidc",
        "domains": [r".*\.example\.com"],
        "issuer_url": "https://auth.example.com/realms/test",
        "client_id": "harmony-test",
        "client_secret": "secret",
        "flow": "client_credentials",
    }
    defaults.update(kwargs)
    return OIDCAuthConfig(**defaults)  # type: ignore


DISCOVERY_DOC = {
    "token_endpoint": "https://auth.example.com/realms/test/protocol/openid-connect/token",
    "authorization_endpoint": "https://auth.example.com/realms/test/protocol/openid-connect/auth",
}


@pytest.mark.asyncio
async def test_discover_endpoints() -> None:
    config = _make_config()
    provider = OIDCAuth(config)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: DISCOVERY_DOC,
            raise_for_status=lambda: None,
        )
        await provider._discover()

    assert provider._token_endpoint == DISCOVERY_DOC["token_endpoint"]
    assert provider._auth_endpoint == DISCOVERY_DOC["authorization_endpoint"]


@pytest.mark.asyncio
async def test_client_credentials_authenticate() -> None:
    config = _make_config(flow="client_credentials")
    provider = OIDCAuth(config)
    provider._token_endpoint = "https://auth.example.com/token"

    token_response = {
        "access_token": "access-abc",
        "refresh_token": "refresh-xyz",
        "expires_in": 300,
        "token_type": "Bearer",
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: token_response,
            raise_for_status=lambda: None,
        )
        session = await provider.authenticate("api.example.com")

    assert session.headers["Authorization"] == "Bearer access-abc"
    assert session.provider_type == "oidc"
    assert session.subdomain == "api.example.com"
    assert provider._refresh_token == "refresh-xyz"


@pytest.mark.asyncio
async def test_ensure_valid_refreshes_expired_token() -> None:
    config = _make_config(flow="client_credentials", token_expiry_buffer_seconds=30)
    provider = OIDCAuth(config)
    provider._token_endpoint = "https://auth.example.com/token"
    provider._access_token = "old-token"
    provider._refresh_token = "old-refresh"
    provider._token_expires_at = datetime.now(UTC) + timedelta(seconds=10)

    token_response = {
        "access_token": "new-token",
        "refresh_token": "new-refresh",
        "expires_in": 300,
        "token_type": "Bearer",
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: token_response,
            raise_for_status=lambda: None,
        )
        await provider.ensure_valid()

    assert provider._access_token == "new-token"
    assert provider._refresh_token == "new-refresh"


@pytest.mark.asyncio
async def test_ensure_valid_skips_refresh_when_token_fresh() -> None:
    config = _make_config(token_expiry_buffer_seconds=30)
    provider = OIDCAuth(config)
    provider._access_token = "fresh-token"
    provider._token_expires_at = datetime.now(UTC) + timedelta(seconds=120)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        await provider.ensure_valid()
        mock_post.assert_not_called()


def test_apply_to_request_injects_bearer() -> None:
    config = _make_config()
    provider = OIDCAuth(config)
    provider._access_token = "my-token"

    request = MagicMock()
    request.headers = {}
    session = MagicMock()

    provider.apply_to_request(request, session)
    assert request.headers["Authorization"] == "Bearer my-token"


def test_build_pkce_pair() -> None:
    verifier, challenge = build_pkce_pair()
    expected = (
        base64
        .urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert challenge == expected
    assert len(verifier) >= 43


@pytest.mark.asyncio
async def test_receive_code_uses_caller_supplied_verifier() -> None:
    config = _make_config(flow="authorization_code")
    provider = OIDCAuth(config)
    provider._token_endpoint = "https://auth.example.com/token"

    token_response = {
        "access_token": "access-abc",
        "refresh_token": "refresh-xyz",
        "expires_in": 300,
        "token_type": "Bearer",
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: token_response,
            raise_for_status=lambda: None,
        )
        await provider.receive_code(
            code="auth-code",
            verifier="caller-supplied-verifier",
            redirect_uri="http://localhost:8001/auth/callback",
        )

    assert (
        mock_post.call_args.kwargs["data"]["code_verifier"]
        == "caller-supplied-verifier"
    )
    assert provider._access_token == "access-abc"
    assert not hasattr(provider, "pending_states")


def test_build_auth_url() -> None:
    config = _make_config(flow="authorization_code")
    provider = OIDCAuth(config)
    provider._auth_endpoint = "https://auth.example.com/auth"

    url, state, verifier = provider.build_auth_url(
        redirect_uri="http://localhost:8001/auth/callback"
    )

    assert "client_id=harmony-test" in url
    assert f"state={state}" in url
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert verifier
