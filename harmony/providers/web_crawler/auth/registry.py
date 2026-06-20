from __future__ import annotations

import threading
import typing
from importlib.metadata import EntryPoint, EntryPoints, entry_points
from urllib.parse import urlparse

import pydantic

from harmony.core import logger
from harmony.providers.web_crawler.auth.providers.base import AuthProvider
from harmony.providers.web_crawler.auth.providers.basic import BasicAuth
from harmony.providers.web_crawler.auth.providers.bearer import BearerTokenAuth
from harmony.providers.web_crawler.auth.providers.oidc import OIDCAuth
from harmony.providers.web_crawler.auth.providers.playwright_sso import (
    PlaywrightSSOAuth,
)
from harmony.providers.web_crawler.auth.providers.service_account import (
    ServiceAccountAuth,
)
from harmony.providers.web_crawler.auth.providers.static_cookie import (
    StaticCookieAuth,
)
from harmony.providers.web_crawler.auth.session import AuthSession

if typing.TYPE_CHECKING:
    from harmony.core import SessionWriter
    from harmony.providers.web_crawler.auth.config import (
        AuthConfig,
        AuthProviderConfig,
    )

# Built-in authentication providers
BUILTIN_PROVIDERS: dict[str, type[AuthProvider]] = {
    "static_cookie": StaticCookieAuth,
    "basic": BasicAuth,
    "bearer": BearerTokenAuth,
    "service_account": ServiceAccountAuth,
    "playwright_sso": PlaywrightSSOAuth,
    "oidc": OIDCAuth,
}


def _register_entry_point(
    ep: EntryPoint, providers: dict[str, type[AuthProvider]]
) -> None:
    provider_class = ep.load()
    if issubclass(provider_class, AuthProvider):
        providers[ep.name] = provider_class
        logger.info(f"Loaded custom auth provider '{ep.name}' from {ep.value}")
    else:
        logger.warning(f"Entry point '{ep.name}' is not an AuthProvider subclass")


def _load_plugin_providers(providers: dict[str, type[AuthProvider]]) -> None:

    eps: EntryPoints
    try:
        eps = entry_points(group="harmony.auth_providers")
    except TypeError:
        all_eps = entry_points()
        eps = (
            all_eps.get("harmony.auth_providers", [])  # type: ignore[union-attr]  # EntryPoints API varies by python version
            if hasattr(all_eps, "get")
            else []
        )

    for ep in eps:
        try:
            _register_entry_point(ep, providers)
        except Exception as e:
            logger.warning(f"Failed to load auth provider '{ep.name}': {e}")


class AuthProviderRegistry:
    """Manages authentication providers and sessions.

    Supports both built-in providers and custom providers loaded via entry points.
    Third-party packages can register custom providers using:

        [project.entry-points."harmony.auth_providers"]
        my_custom_auth = "my_package.auth:MyCustomAuth"
    """

    def __init__(
        self, config: AuthConfig, session_writer: SessionWriter | None = None
    ) -> None:
        self.config = config
        self._providers: list[AuthProvider] = []
        self._sessions: dict[str, AuthSession] = {}
        self._lock = threading.Lock()
        self._session_writer = session_writer
        self._provider_classes = self._discover_providers()

        self._init_providers()

    def _discover_providers(self) -> dict[str, type[AuthProvider]]:
        """Discover authentication providers from built-ins and plugins.

        Returns:
            Dictionary mapping provider type names to provider classes
        """

        providers = BUILTIN_PROVIDERS.copy()

        try:
            _load_plugin_providers(providers)
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
            return provider_class(config)  # type: ignore[arg-type]

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
        """Store session for subdomain and persist immediately."""
        with self._lock:
            self._sessions[subdomain] = session
            logger.debug(f"Stored session for {subdomain}")
        if self._session_writer:
            self._session_writer.upsert(session.to_dict())

    def invalidate_session(self, subdomain: str) -> None:
        """Invalidate session for subdomain and persist immediately."""
        with self._lock:
            if subdomain in self._sessions:
                del self._sessions[subdomain]
                logger.info(f"Invalidated session for {subdomain}")
        if self._session_writer:
            self._session_writer.invalidate(subdomain)

    def load_sessions(self) -> None:
        """Load persisted sessions via writer."""
        if not self._session_writer:
            return

        try:
            self._load_sessions_from_writer()
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to load sessions: {e}")

    def _load_sessions_from_writer(self) -> None:
        if not self._session_writer:
            return
        entries = self._session_writer.load()
        with self._lock:
            for entry in entries:
                session = AuthSession.from_dict(
                    typing.cast(dict[str, pydantic.JsonValue], entry)
                )
                if not session.is_expired():
                    self._sessions[session.subdomain] = session
                    logger.debug(f"Loaded session for {session.subdomain}")
                else:
                    logger.debug(f"Skipped expired session for {session.subdomain}")
        logger.info(f"Loaded {len(self._sessions)} auth sessions")

    def save_sessions(self) -> None:
        """Final flush: persist all non-expired sessions via writer."""
        if not self._session_writer:
            return

        with self._lock:
            sessions = {
                subdomain: session
                for subdomain, session in self._sessions.items()
                if not session.is_expired()
            }

        for session in sessions.values():
            self._session_writer.upsert(session.to_dict())

        logger.info(f"Saved {len(sessions)} auth sessions")

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
