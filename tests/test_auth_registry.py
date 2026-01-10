from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from harmony.crawler.auth.config import (
    AuthConfig,
    BasicAuthConfig,
    BearerTokenAuthConfig,
    CustomAuthConfig,
)
from harmony.crawler.auth.providers.base import AuthProvider
from harmony.crawler.auth.registry import BUILTIN_PROVIDERS, AuthProviderRegistry
from harmony.crawler.auth.session import AuthSession


class TestAuthProviderRegistry:
    """Tests for AuthProviderRegistry."""

    def test_init_loads_providers(self, tmp_path: Path) -> None:
        config = AuthConfig(
            session_storage_path=tmp_path,
            providers=[
                BasicAuthConfig(
                    domains=["api\\.example\\.com"], username="user", password="pass"
                ),
                BearerTokenAuthConfig(
                    domains=["data\\.example\\.com"], token="token123"
                ),
            ],
        )

        registry = AuthProviderRegistry(config)

        assert len(registry._providers) == 2  # noqa: PLR2004
        assert registry._providers[0].provider_type == "basic"
        assert registry._providers[1].provider_type == "bearer"

    def test_builtin_providers_registered(self) -> None:
        """Verify all built-in providers are registered."""
        expected_types = {
            "static_cookie",
            "basic",
            "bearer",
            "service_account",
            "playwright_sso",
        }
        assert set(BUILTIN_PROVIDERS.keys()) == expected_types

    def test_get_provider_for_domain(self, tmp_path: Path) -> None:
        config = AuthConfig(
            session_storage_path=tmp_path,
            providers=[
                BasicAuthConfig(
                    domains=["api\\.example\\.com"], username="user", password="pass"
                ),
                BearerTokenAuthConfig(
                    domains=["data\\.example\\.com"], token="token123"
                ),
            ],
        )

        registry = AuthProviderRegistry(config)

        # Test exact match
        provider = registry.get_provider_for_domain("api.example.com")
        assert provider is not None
        assert provider.provider_type == "basic"

        # Test different domain
        provider = registry.get_provider_for_domain("data.example.com")
        assert provider is not None
        assert provider.provider_type == "bearer"

        # Test no match
        provider = registry.get_provider_for_domain("other.com")
        assert provider is None

    def test_get_provider_from_url(self, tmp_path: Path) -> None:
        config = AuthConfig(
            session_storage_path=tmp_path,
            providers=[
                BasicAuthConfig(
                    domains=["api\\.example\\.com"], username="user", password="pass"
                ),
            ],
        )

        registry = AuthProviderRegistry(config)

        # Should extract domain from URL
        provider = registry.get_provider_for_domain("https://api.example.com/data")
        assert provider is not None
        assert provider.provider_type == "basic"

    def test_store_and_get_session(self, tmp_path: Path) -> None:
        config = AuthConfig(
            session_storage_path=tmp_path,
            providers=[],
        )

        registry = AuthProviderRegistry(config)

        session = AuthSession(
            provider_type="test-provider",
            subdomain="example.com",
            domain_pattern="example\\.com",
            created_at=datetime.now(UTC),
            cookies={"session": "abc123"},
        )

        registry.store_session("example.com", session)

        retrieved = registry.get_session("example.com")
        assert retrieved is not None
        assert retrieved.subdomain == "example.com"
        assert retrieved.cookies == {"session": "abc123"}

    def test_get_expired_session_returns_none(self, tmp_path: Path) -> None:
        config = AuthConfig(
            session_storage_path=tmp_path,
            providers=[],
        )

        registry = AuthProviderRegistry(config)

        # Create expired session
        past_time = datetime.now(UTC) - timedelta(hours=1)
        session = AuthSession(
            provider_type="test-provider",
            subdomain="example.com",
            domain_pattern="example\\.com",
            created_at=datetime.now(UTC),
            expires_at=past_time,
        )

        registry.store_session("example.com", session)

        # Should return None for expired session
        retrieved = registry.get_session("example.com")
        assert retrieved is None

    def test_invalidate_session(self, tmp_path: Path) -> None:
        config = AuthConfig(
            session_storage_path=tmp_path,
            providers=[],
        )

        registry = AuthProviderRegistry(config)

        session = AuthSession(
            provider_type="test-provider",
            subdomain="example.com",
            domain_pattern="example\\.com",
            created_at=datetime.now(UTC),
        )

        registry.store_session("example.com", session)
        assert registry.get_session("example.com") is not None

        registry.invalidate_session("example.com")
        assert registry.get_session("example.com") is None

    def test_save_and_load_sessions(self, tmp_path: Path) -> None:
        config = AuthConfig(
            session_storage_path=tmp_path,
            providers=[],
        )

        registry = AuthProviderRegistry(config)

        session1 = AuthSession(
            provider_type="provider1",
            subdomain="api.example.com",
            domain_pattern="api\\.example\\.com",
            created_at=datetime.now(UTC),
            headers={"Authorization": "Bearer token1"},
        )
        session2 = AuthSession(
            provider_type="provider2",
            subdomain="data.example.com",
            domain_pattern="data\\.example\\.com",
            created_at=datetime.now(UTC),
            cookies={"session": "abc123"},
        )

        registry.store_session("api.example.com", session1)
        registry.store_session("data.example.com", session2)

        # Save to disk
        registry.save_sessions()

        # Verify file was created
        sessions_file = tmp_path / "sessions.json"
        assert sessions_file.exists()

        # Create new registry and load sessions
        new_registry = AuthProviderRegistry(
            AuthConfig(session_storage_path=tmp_path, providers=[])
        )
        new_registry.load_sessions()

        # Verify sessions were loaded
        loaded1 = new_registry.get_session("api.example.com")
        loaded2 = new_registry.get_session("data.example.com")

        assert loaded1 is not None
        assert loaded1.provider_type == "provider1"
        assert loaded2 is not None
        assert loaded2.provider_type == "provider2"

    def test_load_sessions_no_file(self, tmp_path: Path) -> None:
        config = AuthConfig(
            session_storage_path=tmp_path,
            providers=[],
        )

        registry = AuthProviderRegistry(config)

        # Should not raise error if file doesn't exist
        registry.load_sessions()

        # Should have no sessions
        assert len(registry._sessions) == 0

    def test_get_providers(self, tmp_path: Path) -> None:
        config = AuthConfig(
            session_storage_path=tmp_path,
            providers=[
                BasicAuthConfig(
                    domains=["api\\.example\\.com"], username="user", password="pass"
                ),
                BearerTokenAuthConfig(
                    domains=["data\\.example\\.com"], token="token123"
                ),
            ],
        )

        registry = AuthProviderRegistry(config)

        providers = registry.get_providers()
        assert len(providers) == 2  # noqa: PLR2004
        assert providers[0].provider_type == "basic"
        assert providers[1].provider_type == "bearer"

    def test_get_sessions(self, tmp_path: Path) -> None:
        config = AuthConfig(
            session_storage_path=tmp_path,
            providers=[],
        )

        registry = AuthProviderRegistry(config)

        session1 = AuthSession(
            provider_type="provider1",
            subdomain="api.example.com",
            domain_pattern="api\\.example\\.com",
            created_at=datetime.now(UTC),
        )
        session2 = AuthSession(
            provider_type="provider2",
            subdomain="data.example.com",
            domain_pattern="data\\.example\\.com",
            created_at=datetime.now(UTC),
        )

        registry.store_session("api.example.com", session1)
        registry.store_session("data.example.com", session2)

        sessions = registry.get_sessions()
        assert len(sessions) == 2  # noqa: PLR2004
        assert "api.example.com" in sessions
        assert "data.example.com" in sessions

    def test_unknown_provider_type_warning(self, tmp_path: Path) -> None:
        config = AuthConfig(
            session_storage_path=tmp_path,
            providers=[
                CustomAuthConfig(
                    type="nonexistent_provider", domains=["example\\.com"]
                ),
            ],
        )

        registry = AuthProviderRegistry(config)

        # Should log warning but not crash
        assert len(registry._providers) == 0

    def test_plugin_discovery(self, tmp_path: Path) -> None:
        """Test that plugin discovery doesn't crash even if no plugins exist."""
        config = AuthConfig(
            session_storage_path=tmp_path,
            providers=[],
        )

        # Should not raise error
        registry = AuthProviderRegistry(config)

        # Should have all built-in providers available
        assert len(registry._provider_classes) >= 5  # noqa: PLR2004


class TestPluginSystem:
    """Tests for custom provider plugin system."""

    def test_custom_provider_registration(self, tmp_path: Path) -> None:
        """Test that custom providers can be registered."""

        # Create a mock custom provider
        class CustomAuth(AuthProvider):
            def __init__(self, config):  # type: ignore[no-untyped-def]
                super().__init__(config.domains)
                self.config = config

            @property
            def provider_type(self) -> str:
                return "custom"

            async def authenticate(
                self, subdomain: str, trigger_url: str | None = None
            ) -> AuthSession:
                return AuthSession(
                    provider_type="custom",
                    subdomain=subdomain,
                    domain_pattern="custom\\.example\\.com",
                    created_at=datetime.now(UTC),
                    headers={"X-Custom": "data"},
                )

            def apply_to_request(self, request, session):  # type: ignore[no-untyped-def]
                return request

        # Mock entry points to return our custom provider
        mock_ep = MagicMock()
        mock_ep.name = "custom_auth"
        mock_ep.load.return_value = CustomAuth

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            config = AuthConfig(
                session_storage_path=tmp_path,
                providers=[
                    CustomAuthConfig(
                        type="custom_auth", domains=["custom\\.example\\.com"]
                    ),
                ],
            )

            registry = AuthProviderRegistry(config)

            # Custom provider should be loaded
            assert "custom_auth" in registry._provider_classes
            assert len(registry._providers) == 1
            assert registry._providers[0].provider_type == "custom"

    def test_invalid_plugin_ignored(self, tmp_path: Path) -> None:
        """Test that invalid plugins are logged and ignored."""

        # Create a mock entry point that's not an AuthProvider
        class NotAnAuthProvider:
            pass

        mock_ep = MagicMock()
        mock_ep.name = "invalid_provider"
        mock_ep.load.return_value = NotAnAuthProvider

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            config = AuthConfig(
                session_storage_path=tmp_path,
                providers=[],
            )

            # Should not crash
            registry = AuthProviderRegistry(config)

            # Invalid provider should not be registered
            assert "invalid_provider" not in registry._provider_classes

    def test_plugin_load_error_handled(self, tmp_path: Path) -> None:
        """Test that plugin load errors are handled gracefully."""

        # Mock entry point that raises on load
        mock_ep = MagicMock()
        mock_ep.name = "broken_provider"
        mock_ep.load.side_effect = ImportError("Module not found")

        with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
            config = AuthConfig(
                session_storage_path=tmp_path,
                providers=[],
            )

            # Should not crash
            registry = AuthProviderRegistry(config)

            # Broken provider should not be registered
            assert "broken_provider" not in registry._provider_classes
