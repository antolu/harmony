from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from scrapy.http import Request, Response

from harmony.providers.web_crawler.auth.config import (
    BasicAuthConfig,
    BearerTokenAuthConfig,
    ServiceAccountAuthConfig,
    StaticCookieAuthConfig,
)
from harmony.providers.web_crawler.auth.providers.basic import BasicAuth
from harmony.providers.web_crawler.auth.providers.bearer import BearerTokenAuth
from harmony.providers.web_crawler.auth.providers.service_account import (
    ServiceAccountAuth,
)
from harmony.providers.web_crawler.auth.providers.static_cookie import (
    StaticCookieAuth,
)
from harmony.providers.web_crawler.auth.session import AuthSession


class TestStaticCookieAuth:
    """Tests for StaticCookieAuthProvider."""

    def test_provider_type(self) -> None:
        config = StaticCookieAuthConfig(
            domains=["example\\.com"], cookies={"session": "abc123"}
        )
        provider = StaticCookieAuth(config)
        assert provider.provider_type == "static_cookie"

    def test_domain_matching(self) -> None:
        config = StaticCookieAuthConfig(
            domains=["api\\.example\\.com", ".*\\.test\\.com"],
            cookies={"session": "abc123"},
        )
        provider = StaticCookieAuth(config)

        assert provider.matches_domain("api.example.com")
        assert provider.matches_domain("data.test.com")
        assert not provider.matches_domain("example.com")
        assert not provider.matches_domain("other.com")

    @pytest.mark.asyncio
    async def test_authenticate(self) -> None:
        config = StaticCookieAuthConfig(
            domains=["example\\.com"], cookies={"session": "abc123", "csrf": "token"}
        )
        provider = StaticCookieAuth(config)

        session = await provider.authenticate("example.com")

        assert session.subdomain == "example.com"
        assert session.cookies == {"session": "abc123", "csrf": "token"}
        assert session.expires_at is None  # Static cookies don't expire

    def test_apply_to_request(self) -> None:
        config = StaticCookieAuthConfig(
            domains=["example\\.com"], cookies={"session": "abc123"}
        )
        provider = StaticCookieAuth(config)

        request = Request("https://example.com/api/data")
        session = AuthSession(
            provider_type="static_cookie",
            subdomain="example.com",
            domain_pattern="example\\.com",
            created_at=datetime.now(UTC),
            cookies={"session": "abc123"},
        )

        modified_request = provider.apply_to_request(request, session)

        # Check Cookie header was set
        cookie_header = modified_request.headers.get(b"Cookie")
        assert cookie_header is not None
        assert b"session=abc123" in cookie_header


class TestBasicAuth:
    """Tests for BasicAuthProvider."""

    def test_provider_type(self) -> None:
        config = BasicAuthConfig(
            domains=["api\\.example\\.com"], username="user", password="pass"
        )
        provider = BasicAuth(config)
        assert provider.provider_type == "basic"

    @pytest.mark.asyncio
    async def test_authenticate(self) -> None:
        config = BasicAuthConfig(
            domains=["api\\.example\\.com"], username="testuser", password="testpass"
        )
        provider = BasicAuth(config)

        session = await provider.authenticate("api.example.com")

        assert session.subdomain == "api.example.com"
        assert "Authorization" in session.headers
        # Basic auth header format: "Basic base64(username:password)"
        assert session.headers["Authorization"].startswith("Basic ")

    def test_apply_to_request(self) -> None:
        config = BasicAuthConfig(
            domains=["api\\.example\\.com"], username="user", password="pass"
        )
        provider = BasicAuth(config)

        request = Request("https://api.example.com/data")
        session = AuthSession(
            provider_type="basic",
            subdomain="api.example.com",
            domain_pattern="api\\.example\\.com",
            created_at=datetime.now(UTC),
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )

        modified_request = provider.apply_to_request(request, session)

        assert modified_request.headers.get(b"Authorization") == b"Basic dXNlcjpwYXNz"


class TestBearerTokenAuth:
    """Tests for BearerTokenAuthProvider."""

    def test_provider_type(self) -> None:
        config = BearerTokenAuthConfig(
            domains=["api\\.example\\.com"], token="test_token_123"
        )
        provider = BearerTokenAuth(config)
        assert provider.provider_type == "bearer"

    @pytest.mark.asyncio
    async def test_authenticate(self) -> None:
        config = BearerTokenAuthConfig(
            domains=["api\\.example\\.com"], token="test_token_123"
        )
        provider = BearerTokenAuth(config)

        session = await provider.authenticate("api.example.com")

        assert session.subdomain == "api.example.com"
        assert session.headers["Authorization"] == "Bearer test_token_123"

    @pytest.mark.asyncio
    async def test_custom_header(self) -> None:
        config = BearerTokenAuthConfig(
            domains=["api\\.example\\.com"],
            token="test_token_123",
            header_name="X-API-Token",
            header_prefix="Token",
        )
        provider = BearerTokenAuth(config)

        session = await provider.authenticate("api.example.com")

        assert session.headers["X-API-Token"] == "Token test_token_123"

    def test_apply_to_request(self) -> None:
        config = BearerTokenAuthConfig(
            domains=["api\\.example\\.com"], token="test_token"
        )
        provider = BearerTokenAuth(config)

        request = Request("https://api.example.com/data")
        session = AuthSession(
            provider_type="bearer",
            subdomain="api.example.com",
            domain_pattern="api\\.example\\.com",
            created_at=datetime.now(UTC),
            headers={"Authorization": "Bearer test_token"},
        )

        modified_request = provider.apply_to_request(request, session)

        assert modified_request.headers.get(b"Authorization") == b"Bearer test_token"


class TestServiceAccountAuth:
    """Tests for ServiceAccountAuthProvider (OAuth2)."""

    def test_provider_type(self) -> None:
        config = ServiceAccountAuthConfig(
            domains=["api\\.example\\.com"],
            client_id="client123",
            client_secret="secret456",
            token_url="https://auth.example.com/token",
        )
        provider = ServiceAccountAuth(config)
        assert provider.provider_type == "service_account"

    @pytest.mark.asyncio
    async def test_authenticate_success(self) -> None:
        config = ServiceAccountAuthConfig(
            domains=["api\\.example\\.com"],
            client_id="client123",
            client_secret="secret456",
            token_url="https://auth.example.com/token",
        )
        provider = ServiceAccountAuth(config)

        # Mock the HTTP client response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_token_abc",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            session = await provider.authenticate("api.example.com")

        assert session.subdomain == "api.example.com"
        assert session.headers["Authorization"] == "Bearer new_token_abc"
        assert session.expires_at is not None  # Token has expiry

    @pytest.mark.asyncio
    async def test_authenticate_with_scopes(self) -> None:
        config = ServiceAccountAuthConfig(
            domains=["api\\.example\\.com"],
            client_id="client123",
            client_secret="secret456",
            token_url="https://auth.example.com/token",
            scope="read:data write:data",
        )
        provider = ServiceAccountAuth(config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "scoped_token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            session = await provider.authenticate("api.example.com")

            # Verify scope was sent in request
            call_data = mock_post.call_args[1]["data"]
            assert call_data["scope"] == "read:data write:data"

        assert session.headers["Authorization"] == "Bearer scoped_token"

    def test_apply_to_request(self) -> None:
        config = ServiceAccountAuthConfig(
            domains=["api\\.example\\.com"],
            client_id="client",
            client_secret="secret",
            token_url="https://auth.example.com/token",
        )
        provider = ServiceAccountAuth(config)

        request = Request("https://api.example.com/data")
        session = AuthSession(
            provider_type="service_account",
            subdomain="api.example.com",
            domain_pattern="api\\.example\\.com",
            created_at=datetime.now(UTC),
            headers={"Authorization": "Bearer oauth_token"},
        )

        modified_request = provider.apply_to_request(request, session)

        assert modified_request.headers.get(b"Authorization") == b"Bearer oauth_token"


class TestAuthSession:
    """Tests for AuthSession dataclass."""

    def test_session_serialization(self) -> None:
        session = AuthSession(
            provider_type="test-provider",
            subdomain="example.com",
            domain_pattern="example\\.com",
            created_at=datetime.now(UTC),
            headers={"Authorization": "Bearer token"},
        )

        serialized = session.to_dict()

        assert serialized["provider_type"] == "test-provider"
        assert serialized["subdomain"] == "example.com"
        assert serialized["headers"] == {"Authorization": "Bearer token"}
        assert "created_at" in serialized

    def test_session_deserialization(self) -> None:
        data = {
            "provider_type": "test-provider",
            "subdomain": "example.com",
            "domain_pattern": "example\\.com",
            "cookies": {"session": "abc"},
            "headers": {},
            "expires_at": None,
            "created_at": "2026-01-10T12:00:00+00:00",
            "storage_state_file": None,
        }

        session = AuthSession.from_dict(data)

        assert session.provider_type == "test-provider"
        assert session.subdomain == "example.com"
        assert session.cookies == {"session": "abc"}
        assert session.expires_at is None

    def test_session_not_expired_no_expiry(self) -> None:
        session = AuthSession(
            provider_type="test",
            subdomain="example.com",
            domain_pattern="example\\.com",
            created_at=datetime.now(UTC),
            expires_at=None,
        )
        assert not session.is_expired()

    def test_session_expired(self) -> None:
        past_time = datetime.now(UTC) - timedelta(hours=1)
        session = AuthSession(
            provider_type="test",
            subdomain="example.com",
            domain_pattern="example\\.com",
            created_at=datetime.now(UTC),
            expires_at=past_time,
        )
        assert session.is_expired()

    def test_session_not_expired_future(self) -> None:
        future_time = datetime.now(UTC) + timedelta(hours=1)
        session = AuthSession(
            provider_type="test",
            subdomain="example.com",
            domain_pattern="example\\.com",
            created_at=datetime.now(UTC),
            expires_at=future_time,
        )
        assert not session.is_expired()


class TestIsAuthRequired:
    """Tests for auth requirement detection."""

    def test_401_requires_auth(self) -> None:
        config = BasicAuthConfig(
            domains=["api\\.example\\.com"], username="user", password="pass"
        )
        provider = BasicAuth(config)

        response = Response(
            "https://api.example.com/data", status=401, body=b"Unauthorized"
        )
        assert provider.is_auth_required(response)

    def test_403_requires_auth(self) -> None:
        config = BasicAuthConfig(
            domains=["api\\.example\\.com"], username="user", password="pass"
        )
        provider = BasicAuth(config)

        response = Response(
            "https://api.example.com/data", status=403, body=b"Forbidden"
        )
        assert provider.is_auth_required(response)

    def test_200_does_not_require_auth(self) -> None:
        config = BasicAuthConfig(
            domains=["api\\.example\\.com"], username="user", password="pass"
        )
        provider = BasicAuth(config)

        response = Response("https://api.example.com/data", status=200, body=b"OK")
        assert not provider.is_auth_required(response)

    def test_redirect_to_login_requires_auth(self) -> None:
        config = BasicAuthConfig(
            domains=["api\\.example\\.com"], username="user", password="pass"
        )
        provider = BasicAuth(config)

        response = Response(
            "https://api.example.com/data",
            status=302,
            headers={"Location": "https://api.example.com/login"},
        )
        assert provider.is_auth_required(response)
