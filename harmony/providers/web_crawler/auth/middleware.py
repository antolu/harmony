from __future__ import annotations

import asyncio
import typing
from urllib.parse import urlparse

from scrapy import signals
from scrapy.exceptions import IgnoreRequest

from harmony.core import logger
from harmony.providers.web_crawler.auth.config import AuthConfig
from harmony.providers.web_crawler.auth.providers.oidc import OIDCAuth
from harmony.providers.web_crawler.auth.registry import AuthProviderRegistry

if typing.TYPE_CHECKING:
    from scrapy import Request, Spider
    from scrapy.crawler import Crawler
    from scrapy.http import Response

    from harmony.providers.web_crawler.auth.providers.base import AuthProvider


class AuthMiddleware:
    """
    Scrapy downloader middleware for authentication.

    Handles:
    - Applying credentials to outgoing requests
    - Detecting 401/403 responses and triggering re-authentication
    - Retrying requests after successful authentication
    - Pausing crawler during interactive authentication
    """

    AUTH_WAIT_TIMEOUT_SECONDS = 600

    def __init__(self, config: AuthConfig, registry: AuthProviderRegistry) -> None:
        self.config = config
        self.registry = registry
        self._auth_attempts: dict[str, int] = {}
        self._pending_auth: set[str] = set()
        self._crawler: Crawler | None = None

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> AuthMiddleware:
        """Create middleware from crawler settings."""
        auth_config = crawler.settings.get("AUTH_CONFIG")
        if not auth_config:
            auth_config = AuthConfig()

        # Inject global proxy settings into PlaywrightSSO config if available
        crawler_config = crawler.settings.get("CRAWLER_CONFIG")
        if crawler_config and crawler_config.proxy:
            proxy_settings = {"server": crawler_config.proxy.url}
            if crawler_config.proxy.username:
                proxy_settings["username"] = crawler_config.proxy.username
            if crawler_config.proxy.password:
                proxy_settings["password"] = crawler_config.proxy.password

            for provider in auth_config.providers:
                if provider.type == "playwright_sso":
                    provider.proxy = proxy_settings

        session_writer = crawler.settings.get("SESSION_WRITER")
        registry = AuthProviderRegistry(auth_config, session_writer=session_writer)
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

    async def process_request(self, request: Request, spider: Spider) -> Request | None:
        """Apply authentication credentials to outgoing requests."""
        if not self.config.enabled:
            return None

        # Skip authentication for robots.txt to avoid infinite recursion and timeouts
        if request.url.endswith("/robots.txt"):
            return None

        if self._pending_auth:
            subdomain_list = ", ".join(self._pending_auth)
            logger.debug(
                f"Interactive auth in progress for {subdomain_list}, "
                f"pausing request to {request.url}"
            )
            wait_time = 0
            while self._pending_auth and wait_time < self.AUTH_WAIT_TIMEOUT_SECONDS:
                await asyncio.sleep(1)
                wait_time += 1
            if self._pending_auth:
                logger.warning(
                    f"Auth wait timeout after {self.AUTH_WAIT_TIMEOUT_SECONDS}s, "
                    f"proceeding with request to {request.url}"
                )
            else:
                logger.debug(f"Auth finished, resuming request to {request.url}")

        subdomain = urlparse(request.url).netloc

        provider = self.registry.get_provider_for_domain(subdomain)
        if not provider:
            return None

        # BLOCK requests to the Auth Provider itself (prevent loops)
        if provider.is_auth_domain(request.url):
            logger.debug(
                f"Blocking request to Auth Provider domain: {request.url}. "
                "Authentication should be handled via interactive flow, not by crawling."
            )
            msg = "Blocked Auth Provider URL"
            raise IgnoreRequest(msg)

        session = self.registry.get_session(subdomain)

        if not session and hasattr(provider, "refresh_session_for_subdomain"):
            session = await provider.refresh_session_for_subdomain(subdomain)
            if session:
                self.registry.store_session(subdomain, session)
                logger.debug(f"Created session for {subdomain} from SSO state")

        if not session:
            logger.debug(f"No auth session for {subdomain}, proceeding without auth")
            return None

        if isinstance(provider, OIDCAuth):
            await provider.ensure_valid()
        request = provider.apply_to_request(request, session)
        logger.debug(f"Applied auth credentials for {subdomain}")

        return None

    async def process_response(
        self, request: Request, response: Response, spider: Spider
    ) -> Response | Request:
        """Handle authentication failures and trigger re-auth."""
        provider = await self._check_fast_path_bailout(request, response)
        if provider is None:
            return response

        subdomain = urlparse(request.url).netloc

        if not self._can_retry_auth(request.url):
            logger.error(
                f"Auth failed for {subdomain} after {self.config.max_auth_retries} attempts"
            )
            msg = f"Authentication failed for {request.url} after retries"
            raise IgnoreRequest(msg)

        self.registry.invalidate_session(subdomain)

        if provider.is_interactive():
            if not self.config.auto_authenticate_on_403:
                self._log_interactive_auth_required(subdomain, provider)
                return response

            reschedule = self._handle_interactive_busy(request, subdomain, provider)
            if reschedule is not None:
                return reschedule

            await self._handle_interactive_reauth(subdomain, request.url, provider)
        else:
            await self._handle_noninteractive_reauth(subdomain, request.url, provider)

        self._increment_auth_attempts(request.url)

        logger.info(f"Retrying request after auth: {request.url}")
        return request.replace(dont_filter=True)

    async def _check_fast_path_bailout(
        self, request: Request, response: Response
    ) -> AuthProvider | None:
        """Run the fast-path checks that should bail out before any re-auth
        side effect: disabled config, robots.txt, no provider for domain,
        auth not required, and retries disabled.

        Returns the matched provider if auth is required and retries are
        enabled, or None if process_response should return the response
        unchanged.
        """
        if not self.config.enabled:
            return None

        # Skip authentication for robots.txt
        if request.url.endswith("/robots.txt"):
            return None

        subdomain = urlparse(request.url).netloc

        provider = self.registry.get_provider_for_domain(subdomain)
        if not provider:
            return None

        if not await self._is_auth_required(request, response, provider):
            self._reset_auth_attempts(request.url)
            return None

        logger.info(f"Auth required for {request.url} (status: {response.status})")

        if not self.config.retry_on_auth_failure:
            return None

        return provider

    async def _is_auth_required(
        self, request: Request, response: Response, provider: AuthProvider
    ) -> bool:
        """Check sync/async/semantic indicators that auth is required."""
        # Check synchronous/fast indicators first to avoid unnecessary async/LLM calls
        if provider.is_auth_required(response):
            # Standard auth detected (status code or headers)
            return True

        if await provider.is_auth_required_async(response):
            # Semantic auth detected (LLM check returned True)
            logger.warning(
                f"SEMANTIC AUTH DETECTED: Page content indicates unauthorized access at {request.url}"
            )
            if self._crawler and self._crawler.stats:
                self._crawler.stats.inc_value("auth/semantic_detection_count")
            return True

        return False

    def _log_interactive_auth_required(
        self, subdomain: str, provider: AuthProvider
    ) -> None:
        """Log a warning that interactive auth is required but disabled."""
        provider_name = "sso"
        if hasattr(provider, "config") and hasattr(provider.config, "name"):
            provider_name = provider.config.name
        logger.warning(
            f"Interactive auth required for {subdomain}. "
            f"Run: harmony-auth login {provider_name}"
        )

    def _handle_interactive_busy(
        self, request: Request, subdomain: str, provider: AuthProvider
    ) -> Request | None:
        """Return a rescheduled request if another subdomain under the same
        provider is already mid-auth, otherwise reserve this subdomain and
        return None."""
        for pending_sub in self._pending_auth:
            if self.registry.get_provider_for_domain(pending_sub) == provider:
                logger.debug(
                    f"Auth already in progress for provider of {subdomain}, "
                    f"rescheduling {request.url}"
                )
                return request.replace(dont_filter=True)

        self._pending_auth.add(subdomain)
        return None

    async def _handle_interactive_reauth(
        self, subdomain: str, trigger_url: str, provider: AuthProvider
    ) -> None:
        """Perform interactive re-authentication for subdomain, freeing the
        pending-auth reservation made by _handle_interactive_busy."""
        try:
            logger.info(
                f"Starting interactive auth for {subdomain} - "
                "all crawler requests paused"
            )
            session = await provider.authenticate(subdomain, trigger_url)
            if session:
                self.registry.store_session(subdomain, session)
                logger.info(
                    f"Interactive auth completed for {subdomain} - resuming crawler"
                )
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.warning(f"Interactive auth cancelled for {subdomain}")
            raise
        except Exception as e:
            logger.error(f"Interactive auth failed for {subdomain}: {e}")
        finally:
            self._pending_auth.discard(subdomain)

    async def _handle_noninteractive_reauth(
        self, subdomain: str, trigger_url: str, provider: AuthProvider
    ) -> None:
        """Perform non-interactive re-authentication for subdomain."""
        try:
            session = await provider.authenticate(subdomain, trigger_url)
            if session:
                self.registry.store_session(subdomain, session)
        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.warning(f"Authentication cancelled for {subdomain}")
            raise
        except Exception as e:
            logger.error(f"Authentication failed for {subdomain}: {e}")

    def _can_retry_auth(self, url: str) -> bool:
        """Check if we can retry auth for this URL."""
        attempts = self._auth_attempts.get(url, 0)
        return attempts < self.config.max_auth_retries

    def _increment_auth_attempts(self, url: str) -> None:
        """Increment auth retry counter for URL."""
        self._auth_attempts[url] = self._auth_attempts.get(url, 0) + 1

    def _reset_auth_attempts(self, url: str) -> None:
        """Reset auth retry counter for URL."""
        self._auth_attempts.pop(url, None)
