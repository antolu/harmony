from __future__ import annotations

import re
import sys
import threading
import typing
from urllib.parse import urlparse

from rich.console import Console
from scrapy import Request, Spider, signals
from scrapy.exceptions import IgnoreRequest
from scrapy.http import Response

from harmony.crawler.logger import logger
from harmony.crawler.safety import SafetyConfig, is_url_safe

if typing.TYPE_CHECKING:
    from scrapy.crawler import Crawler

    from harmony.crawler.safety_lists import SafetyListsManager
    from harmony.crawler.state import CrawlStateManager


class AllowedDomainsMiddleware:
    """Middleware to filter requests based on regex domain patterns."""

    def __init__(
        self, allowed_patterns: list[str], forbidden_patterns: list[str]
    ) -> None:
        self.allowed_patterns: list[re.Pattern[str]] = []
        self.forbidden_patterns: list[re.Pattern[str]] = []

        for pattern in allowed_patterns:
            try:
                self.allowed_patterns.append(re.compile(pattern))
            except re.error:
                logger.warning(f"Invalid regex pattern in allowed_domains: {pattern}")

        for pattern in forbidden_patterns:
            try:
                self.forbidden_patterns.append(re.compile(pattern))
            except re.error:
                logger.warning(f"Invalid regex pattern in forbidden_domains: {pattern}")

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> AllowedDomainsMiddleware:
        allowed_domains = crawler.settings.get("ALLOWED_DOMAIN_PATTERNS", [])
        forbidden_domains = crawler.settings.get("FORBIDDEN_DOMAIN_PATTERNS", [])
        return cls(allowed_domains, forbidden_domains)

    def process_request(self, request: Request, spider: Spider) -> Request | None:
        """Filter requests that don't match allowed domain patterns."""
        domain = urlparse(request.url).netloc

        # Check forbidden patterns first (takes priority)
        for pattern in self.forbidden_patterns:
            if pattern.search(domain):
                logger.debug(f"Filtered forbidden domain request: {request.url}")
                msg = f"Domain matches forbidden pattern: {domain}"
                raise IgnoreRequest(msg)

        # If no allowed patterns specified, allow all (that aren't forbidden)
        if not self.allowed_patterns:
            return None

        # Check if domain matches any allowed pattern
        for pattern in self.allowed_patterns:
            if pattern.search(domain):
                return None

        # Domain not allowed
        logger.debug(f"Filtered offsite request: {request.url}")
        msg = f"Domain not in allowed patterns: {domain}"
        raise IgnoreRequest(msg)


class DomainRouterMiddleware:
    """Middleware that tags requests with spider type based on domain routing."""

    def __init__(self, crawler_config: typing.Any):
        self.config = crawler_config

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> DomainRouterMiddleware:
        # Get the config from crawler settings
        config = crawler.settings.get("CRAWLER_CONFIG")
        return cls(config)

    def process_request(self, request: Request, spider: Spider) -> None:
        """Tag request with spider type based on domain."""
        domain = urlparse(request.url).netloc
        spider_type = self.config.get_spider_for_domain(domain)

        request.meta["spider_type"] = spider_type

        spider_settings = self.config.get_spider_settings_for(spider_type)
        request.meta["spider_settings"] = spider_settings

    def process_response(
        self, request: Request, response: Response, spider: Spider
    ) -> Response:
        """Pass through response unchanged."""
        return response


class DeltaFetchMiddleware:
    """Middleware for HTTP-based change detection using If-Modified-Since and ETag."""

    _HTTP_NOT_MODIFIED = 304
    _HTTP_NOT_FOUND = 404
    _HTTP_GONE = 410

    def __init__(self, state_manager: CrawlStateManager | None):
        self.state_manager = state_manager

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> DeltaFetchMiddleware:
        state_manager = crawler.settings.get("STATE_MANAGER")
        return cls(state_manager)

    def process_request(self, request: Request, spider: Spider) -> None:
        """Add conditional request headers if state exists."""
        if not self.state_manager:
            return

        state = self.state_manager.get_state(request.url)
        if not state:
            return

        request.meta["crawl_state"] = state

        if state.get("last_modified"):
            request.headers["If-Modified-Since"] = state["last_modified"]

        if state.get("etag"):
            request.headers["If-None-Match"] = state["etag"]

    def process_response(
        self, request: Request, response: Response, spider: Spider
    ) -> Response:
        """Handle 304 Not Modified and 404 responses."""
        if not self.state_manager:
            return response

        # Skip robots.txt from state tracking
        if request.url.endswith("/robots.txt"):
            return response

        if response.status == self._HTTP_NOT_MODIFIED:
            logger.info(f"304 Not Modified: {request.url}")
            self.state_manager.mark_seen(request.url)
            msg = f"304 Not Modified: {request.url}"
            raise IgnoreRequest(msg)

        if response.status in {self._HTTP_NOT_FOUND, self._HTTP_GONE}:
            logger.warning(f"{response.status} Not Found: {request.url}")
            self.state_manager.increment_missing(request.url)
            msg = f"{response.status} response: {request.url}"
            raise IgnoreRequest(msg)

        return response


class SafetyMiddleware:
    """Middleware for runtime safety checks.

    Note: Most URL pattern filtering happens in LinkExtractor (crawl-time).
    This middleware handles:
    - HTTP method validation
    - Query parameter checks
    - Safe mode checks
    - Interactive approval (runtime pattern additions)
    - Statistics and logging
    """

    def __init__(
        self,
        config: SafetyConfig,
        lists_manager: SafetyListsManager | None = None,
        *,
        interactive: bool = False,
    ):
        self.config = config
        self.lists_manager = lists_manager
        self.interactive = interactive and sys.stdout.isatty()
        self.blocked_count = 0
        self.blocked_reasons: dict[str, int] = {}
        self._lock = threading.Lock()
        self._asked_patterns: set[str] = set()

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> SafetyMiddleware:
        config = crawler.settings.get("SAFETY_CONFIG") or SafetyConfig()
        lists_manager = crawler.settings.get("SAFETY_LISTS_MANAGER")
        interactive = crawler.settings.get("INTERACTIVE_SAFETY", False)

        middleware = cls(config, lists_manager, interactive=interactive)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)

        return middleware

    def process_request(self, request: Request, spider: Spider) -> Request | None:
        """Check request safety before processing."""

        # Skip safety checks for robots.txt to avoid infinite recursion
        if request.url.endswith("/robots.txt"):
            return None

        if request.method not in self.config.allowed_methods:
            self._block_request(
                request,
                f"Disallowed HTTP method: {request.method}",
                spider,
            )
            return None

        runtime_config = self._get_runtime_config()

        is_safe, reason = is_url_safe(request.url, runtime_config)

        if not is_safe:
            if self.interactive and self.lists_manager:
                should_allow = self._prompt_user(request.url, reason, spider)
                if should_allow:
                    pattern = self._url_to_pattern(request.url)
                    self.lists_manager.add_allow_pattern(pattern)
                    spider.logger.info(f"Added to allow-list: {pattern}")
                    return request

            self._block_request(request, reason, spider)
            return None

        if self.config.dry_run:
            spider.logger.info(f"[DRY RUN] Would request: {request.url}")
            return None

        # Return None to let Scrapy continue processing normally
        # Returning the request object can cause middleware re-processing loops
        return None

    def _get_runtime_config(self) -> SafetyConfig:
        """Get config with runtime patterns merged."""
        if self.lists_manager:
            return SafetyConfig(
                allowed_methods=self.config.allowed_methods,
                dangerous_url_patterns=self.config.dangerous_url_patterns,
                dangerous_query_params=self.config.dangerous_query_params,
                safe_mode=self.config.safe_mode,
                dry_run=self.config.dry_run,
                allow_list_patterns=(
                    self.config.allow_list_patterns
                    + self.lists_manager.get_allow_patterns()
                ),
                additional_deny_patterns=(
                    self.config.additional_deny_patterns
                    + self.lists_manager.get_deny_patterns()
                ),
            )
        return self.config

    def _prompt_user(self, url: str, reason: str, spider: Spider) -> bool:
        """Prompt user to allow/deny the URL. Thread-safe with proper output."""
        pattern_key = self._url_to_pattern(url)

        with self._lock:
            if pattern_key in self._asked_patterns:
                return False
            self._asked_patterns.add(pattern_key)

        console = Console()
        console.print()
        console.print("[bold red]⚠ URL BLOCKED BY SAFETY[/bold red]")
        console.print(f"[yellow]URL:[/yellow] {url}")
        console.print(f"[yellow]Reason:[/yellow] {reason}")
        console.print(f"[yellow]Pattern:[/yellow] {pattern_key}")
        console.print()
        console.file.flush()

        try:
            response = input("Allow this URL? [y/N/always/never]: ").strip().lower()

            if response in {"y", "yes"}:
                return True
            if response in {"always", "a"}:
                if self.lists_manager:
                    self.lists_manager.add_allow_pattern(pattern_key)
                return True
            if response in {"never", "n"}:
                if self.lists_manager:
                    self.lists_manager.add_deny_pattern(pattern_key)
            else:
                return False
        except (EOFError, KeyboardInterrupt):
            pass
        return False

    @staticmethod
    def _url_to_pattern(url: str) -> str:
        """Convert URL to a reusable regex pattern."""
        parsed = urlparse(url)

        path = parsed.path.rstrip("/")

        path = re.sub(r"/\d+", r"/\\d+", path)

        domain = re.escape(parsed.netloc)

        return f"{domain}{path}"

    def _block_request(self, request: Request, reason: str, spider: Spider) -> None:
        """Block a request and log the reason. Thread-safe."""
        with self._lock:
            self.blocked_count += 1
            self.blocked_reasons[reason] = self.blocked_reasons.get(reason, 0) + 1

        spider.logger.warning(
            f"[SAFETY BLOCK] {request.url}\n"
            f"  Reason: {reason}\n"
            f"  Method: {request.method}\n"
            f"  Referer: {request.headers.get('Referer', b'').decode()}"
        )

    def spider_closed(self, spider: Spider) -> None:
        """Log statistics when spider closes. Thread-safe read."""
        with self._lock:
            if self.blocked_count > 0:
                spider.logger.info(
                    f"\n[SAFETY STATS] Blocked {self.blocked_count} potentially dangerous requests:"
                )
                for reason, count in sorted(
                    self.blocked_reasons.items(), key=lambda x: x[1], reverse=True
                ):
                    spider.logger.info(f"  - {reason}: {count}")
