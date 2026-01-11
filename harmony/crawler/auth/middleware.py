from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from scrapy import signals

from harmony.crawler.auth.config import AuthConfig
from harmony.crawler.auth.providers.base import AuthProvider
from harmony.crawler.auth.registry import AuthProviderRegistry
from harmony.crawler.auth.session import AuthSession
from harmony.crawler.logger import logger

if TYPE_CHECKING:
    from scrapy import Request, Spider
    from scrapy.crawler import Crawler
    from scrapy.http import Response


class AuthMiddleware:
    """
    Scrapy downloader middleware for authentication.

    Handles:
    - Applying credentials to outgoing requests
    - Detecting 401/403 responses and triggering re-authentication
    - Retrying requests after successful authentication
    - Pausing crawler during interactive authentication
    """

    def __init__(self, config: AuthConfig, registry: AuthProviderRegistry) -> None:
        self.config = config
        self.registry = registry
        self._auth_attempts: dict[str, int] = {}
        self._lock = threading.Lock()
        self._pending_auth: set[str] = set()
        self._crawler: Crawler | None = None
        self._auth_lock = threading.Lock()

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> AuthMiddleware:
        """Create middleware from crawler settings."""
        auth_config = crawler.settings.get("AUTH_CONFIG")
        if not auth_config:
            auth_config = AuthConfig()

        registry = AuthProviderRegistry(auth_config)
        middleware = cls(auth_config, registry)
        middleware._crawler = crawler

        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)

        return middleware

    def spider_opened(self, spider: Spider) -> None:
        """Load persisted sessions on spider start."""
        if self.config.enabled:
            self.registry.load_sessions()
            logger.info("Auth middleware initialized")

    def spider_closed(self, spider: Spider) -> None:
        """Save sessions on spider close."""
        if self.config.enabled:
            self.registry.save_sessions()
            logger.info("Auth middleware shut down, sessions saved")

    def process_request(self, request: Request, spider: Spider) -> Request | None:
        """Apply authentication credentials to outgoing requests."""
        if not self.config.enabled:
            return None

        with self._auth_lock:
            if self._pending_auth:
                subdomain_list = ", ".join(self._pending_auth)
                logger.debug(
                    f"Interactive auth in progress for {subdomain_list}, "
                    f"blocking request to {request.url}"
                )

        subdomain = urlparse(request.url).netloc

        provider = self.registry.get_provider_for_domain(subdomain)
        if not provider:
            return None

        session = self.registry.get_session(subdomain)

        if not session and hasattr(provider, "refresh_session_for_subdomain"):
            session = asyncio.get_event_loop().run_until_complete(
                provider.refresh_session_for_subdomain(subdomain)
            )
            if session:
                self.registry.store_session(subdomain, session)
                logger.debug(f"Created session for {subdomain} from SSO state")

        if not session:
            logger.debug(f"No auth session for {subdomain}, proceeding without auth")
            return None

        request = provider.apply_to_request(request, session)
        logger.debug(f"Applied auth credentials for {subdomain}")

        return None

    def process_response(  # noqa: PLR0911, PLR0912
        self, request: Request, response: Response, spider: Spider
    ) -> Response | Request:
        """Handle authentication failures and trigger re-auth."""
        if not self.config.enabled:
            return response

        subdomain = urlparse(request.url).netloc

        provider = self.registry.get_provider_for_domain(subdomain)
        if not provider:
            return response

        if not provider.is_auth_required(response):
            self._reset_auth_attempts(request.url)
            return response

        logger.info(f"Auth required for {request.url} (status: {response.status})")

        if not self.config.retry_on_auth_failure:
            return response

        if not self._can_retry_auth(request.url):
            logger.error(
                f"Auth failed for {subdomain} after {self.config.max_auth_retries} attempts"
            )
            return response

        self.registry.invalidate_session(subdomain)

        if provider.is_interactive():
            if not self.config.auto_authenticate_on_403:
                provider_name = "sso"
                if hasattr(provider, "config") and hasattr(provider.config, "name"):
                    provider_name = provider.config.name
                logger.warning(
                    f"Interactive auth required for {subdomain}. "
                    f"Run: harmony-auth login {provider_name}"
                )
                return response

            if subdomain in self._pending_auth:
                logger.debug(f"Auth already in progress for {subdomain}")
                return response

            with self._auth_lock:
                if subdomain in self._pending_auth:
                    logger.debug(f"Auth already completed for {subdomain}")
                    return response

                self._pending_auth.add(subdomain)
                try:
                    logger.info(
                        f"Starting interactive auth for {subdomain} - "
                        "all crawler requests paused"
                    )
                    session = self._authenticate_sync(provider, subdomain, request.url)
                    if session:
                        self.registry.store_session(subdomain, session)
                        logger.info(
                            f"Interactive auth completed for {subdomain} - "
                            "resuming crawler"
                        )
                finally:
                    self._pending_auth.discard(subdomain)

        else:
            session = self._authenticate_sync(provider, subdomain, request.url)
            if session:
                self.registry.store_session(subdomain, session)

        self._increment_auth_attempts(request.url)

        logger.info(f"Retrying request after auth: {request.url}")
        return request.replace(dont_filter=True)

    def _authenticate_sync(
        self, provider: AuthProvider, subdomain: str, trigger_url: str
    ) -> AuthSession | None:
        """Synchronous wrapper for async authentication."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(
                provider.authenticate(subdomain, trigger_url)
            )
        except Exception as e:
            logger.error(f"Authentication failed for {subdomain}: {e}")
            return None

    def _can_retry_auth(self, url: str) -> bool:
        """Check if we can retry auth for this URL."""
        with self._lock:
            attempts = self._auth_attempts.get(url, 0)
            return attempts < self.config.max_auth_retries

    def _increment_auth_attempts(self, url: str) -> None:
        """Increment auth retry counter for URL."""
        with self._lock:
            self._auth_attempts[url] = self._auth_attempts.get(url, 0) + 1

    def _reset_auth_attempts(self, url: str) -> None:
        """Reset auth retry counter for URL."""
        with self._lock:
            self._auth_attempts.pop(url, None)
