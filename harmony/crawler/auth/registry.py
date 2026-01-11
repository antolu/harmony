from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from harmony.crawler.auth.providers.base import AuthProvider
from harmony.crawler.auth.providers.basic import BasicAuth
from harmony.crawler.auth.providers.bearer import BearerTokenAuth
from harmony.crawler.auth.providers.playwright_sso import PlaywrightSSOAuth
from harmony.crawler.auth.providers.service_account import ServiceAccountAuth
from harmony.crawler.auth.providers.static_cookie import StaticCookieAuth
from harmony.crawler.auth.session import AuthSession
from harmony.crawler.logger import logger

if TYPE_CHECKING:
    from harmony.crawler.auth.config import AuthConfig, AuthProviderConfig

# Built-in authentication providers
BUILTIN_PROVIDERS: dict[str, type[AuthProvider]] = {
    "static_cookie": StaticCookieAuth,
    "basic": BasicAuth,
    "bearer": BearerTokenAuth,
    "service_account": ServiceAccountAuth,
    "playwright_sso": PlaywrightSSOAuth,
}


class AuthProviderRegistry:
    """Manages authentication providers and sessions.

    Supports both built-in providers and custom providers loaded via entry points.
    Third-party packages can register custom providers using:

        [project.entry-points."harmony.auth_providers"]
        my_custom_auth = "my_package.auth:MyCustomAuth"
    """

    def __init__(self, config: AuthConfig) -> None:
        self.config = config
        self._providers: list[AuthProvider] = []
        self._sessions: dict[str, AuthSession] = {}
        self._lock = threading.Lock()
        self._sessions_file = config.session_storage_path / "sessions.json"
        self._provider_classes = self._discover_providers()

        self._init_providers()

    def _discover_providers(self) -> dict[str, type[AuthProvider]]:
        """Discover authentication providers from built-ins and plugins.

        Returns:
            Dictionary mapping provider type names to provider classes
        """
        from importlib.metadata import entry_points  # noqa: PLC0415
        from typing import Any  # noqa: PLC0415

        providers = BUILTIN_PROVIDERS.copy()

        try:
            eps: Any
            try:
                eps = entry_points(group="harmony.auth_providers")
            except TypeError:
                all_eps = entry_points()
                eps = (
                    all_eps.get("harmony.auth_providers", [])  # type: ignore[union-attr]
                    if hasattr(all_eps, "get")
                    else []
                )

            for ep in eps:
                try:
                    provider_class = ep.load()
                    if issubclass(provider_class, AuthProvider):
                        providers[ep.name] = provider_class
                        logger.info(
                            f"Loaded custom auth provider '{ep.name}' from {ep.value}"
                        )
                    else:
                        logger.warning(
                            f"Entry point '{ep.name}' is not an AuthProvider subclass"
                        )
                except Exception as e:
                    logger.warning(f"Failed to load auth provider '{ep.name}': {e}")

        except ImportError:
            logger.debug("importlib.metadata not available, skipping plugin discovery")
        except Exception as e:
            logger.debug(f"Error discovering custom auth providers: {e}")

        return providers

    def _init_providers(self) -> None:
        """Initialize providers from config."""
        for provider_config in self.config.providers:
            provider = self._create_provider(provider_config)
            if provider:
                self._providers.append(provider)
                logger.info(
                    f"Registered auth provider: {provider.provider_type} for {provider_config.domains}"
                )

    def _create_provider(self, config: AuthProviderConfig) -> AuthProvider | None:
        """Create provider instance from config."""
        provider_class = self._provider_classes.get(config.type)
        if provider_class:
            return provider_class(config)  # type: ignore[abstract]

        logger.warning(
            f"Unknown auth provider type: {config.type}. "
            f"Available types: {', '.join(self._provider_classes.keys())}"
        )
        return None

    def get_provider_for_domain(self, url_or_domain: str) -> AuthProvider | None:
        """Find the first provider that handles this domain."""
        if url_or_domain.startswith(("http://", "https://")):
            subdomain = urlparse(url_or_domain).netloc
        else:
            subdomain = url_or_domain

        for provider in self._providers:
            if provider.matches_domain(subdomain):
                return provider
        return None

    def get_session(self, subdomain: str) -> AuthSession | None:
        """Get existing session for subdomain."""
        with self._lock:
            session = self._sessions.get(subdomain)
            if session and not session.is_expired():
                return session
            if session and session.is_expired():
                logger.info(f"Session expired for {subdomain}")
                del self._sessions[subdomain]
        return None

    def store_session(self, subdomain: str, session: AuthSession) -> None:
        """Store session for subdomain."""
        with self._lock:
            self._sessions[subdomain] = session
            logger.debug(f"Stored session for {subdomain}")

    def invalidate_session(self, subdomain: str) -> None:
        """Invalidate session for subdomain."""
        with self._lock:
            if subdomain in self._sessions:
                del self._sessions[subdomain]
                logger.info(f"Invalidated session for {subdomain}")

    def load_sessions(self) -> None:
        """Load persisted sessions from disk."""
        if not self._sessions_file.exists():
            return

        try:
            with open(self._sessions_file, encoding="utf-8") as f:
                data = json.load(f)

            with self._lock:
                for subdomain, session_data in data.items():
                    session = AuthSession.from_dict(session_data)
                    if not session.is_expired():
                        self._sessions[subdomain] = session
                        logger.debug(f"Loaded session for {subdomain}")
                    else:
                        logger.debug(f"Skipped expired session for {subdomain}")

            logger.info(f"Loaded {len(self._sessions)} auth sessions")
        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning(f"Failed to load sessions: {e}")

    def save_sessions(self) -> None:
        """Save sessions to disk."""
        self.config.session_storage_path.mkdir(parents=True, exist_ok=True)

        with self._lock:
            data = {
                subdomain: session.to_dict()
                for subdomain, session in self._sessions.items()
                if not session.is_expired()
            }

        try:
            with open(self._sessions_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(data)} auth sessions")
        except OSError as e:
            logger.error(f"Failed to save sessions: {e}")

    def get_interactive_providers(self) -> list[AuthProvider]:
        """Get all interactive auth providers (for CLI pre-auth)."""
        return [p for p in self._providers if p.is_interactive()]

    def get_provider_by_name(self, name: str) -> AuthProvider | None:
        """Get provider by name (for CLI pre-auth)."""
        for provider in self._providers:
            if (
                hasattr(provider, "config")
                and hasattr(provider.config, "name")
                and provider.config.name == name
            ):
                return provider
        return None

    def get_providers(self) -> list[AuthProvider]:
        """Get all registered providers."""
        return list(self._providers)

    def get_sessions(self) -> dict[str, AuthSession]:
        """Get all active sessions."""
        with self._lock:
            return dict(self._sessions)
