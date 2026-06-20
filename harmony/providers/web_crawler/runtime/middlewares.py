from __future__ import annotations

import fnmatch
import json
import logging
import os
import re
import threading
import typing
from pathlib import Path
from urllib.parse import urlparse

import httpx
from pydantic import JsonValue
from scrapy import Request, Spider, signals
from scrapy.exceptions import IgnoreRequest
from scrapy.http import Response

from harmony.core import logger
from harmony.providers.web_crawler.runtime.config import CrawlerConfig
from harmony.providers.web_crawler.runtime.safety import SafetyConfig, is_url_safe

_mw_logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from scrapy.crawler import Crawler

    from harmony.providers.web_crawler.runtime.safety_lists import SafetyListsManager
    from harmony.providers.web_crawler.runtime.state import CrawlStateManager


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
            if pattern.search(domain) or pattern.search(request.url):
                logger.info(f"Skipping forbidden domain: {request.url}")
                if spider and spider.crawler.stats:
                    spider.crawler.stats.inc_value("filter/forbidden_domain")
                msg = f"Domain/URL matches forbidden pattern: {domain}"
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

    def __init__(self, crawler_config: CrawlerConfig):
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
        harmony_api_url: str = "http://localhost:8000",
    ):
        self.config = config
        self.lists_manager = lists_manager
        self.interactive = interactive
        self.job_id = os.environ.get("HARMONY_CRAWL_JOB_ID")
        self.backend_url = os.environ.get(
            "HARMONY_BACKEND_URL", "http://localhost:8001"
        )
        self._harmony_api_url = harmony_api_url
        self._blacklist_patterns: set[str] = set()
        self.blocked_count = 0
        self.blocked_reasons: dict[str, int] = {}
        self._lock = threading.Lock()
        self._asked_patterns: set[str] = set()

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> SafetyMiddleware:
        config = crawler.settings.get("SAFETY_CONFIG") or SafetyConfig()
        lists_manager = crawler.settings.get("SAFETY_LISTS_MANAGER")
        interactive = crawler.settings.get("INTERACTIVE_SAFETY", False)
        harmony_api_url = crawler.settings.get("HARMONY_API_URL") or os.environ.get(
            "HARMONY_BACKEND_URL", "http://localhost:8000"
        )

        middleware = cls(
            config,
            lists_manager,
            interactive=interactive,
            harmony_api_url=harmony_api_url,
        )
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)

        return middleware

    def spider_opened(self, spider: Spider) -> None:
        self._blacklist_patterns = self._load_blacklist_patterns()
        _mw_logger.info("loaded %d blacklist patterns", len(self._blacklist_patterns))

    def _load_blacklist_patterns(self) -> set[str]:
        patterns = self._fetch_blacklist_from_api()
        if patterns is not None:
            return patterns
        return self._load_blacklist_fallback()

    @staticmethod
    def _parse_blacklist_response(data: JsonValue) -> set[str]:
        if isinstance(data, list):
            return {str(p) for p in data}
        if isinstance(data, dict) and "patterns" in data:
            return {str(p) for p in data["patterns"]}
        return set()

    def _fetch_blacklist_from_api(self) -> set[str] | None:
        try:
            with httpx.Client(timeout=5) as client:
                resp = client.get(
                    f"{self._harmony_api_url}/api/admin/documents/blacklist"
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.RequestError as e:
            _mw_logger.warning("could not reach Harmony API for blacklist: %s", e)
            return None
        except Exception as e:
            _mw_logger.warning("failed to load blacklist from API: %s", e)
            return None
        else:
            return self._parse_blacklist_response(data)

    def _load_blacklist_fallback(self) -> set[str]:
        safety_lists_path = Path(".harmony-safety-lists.json")
        if safety_lists_path.exists():
            try:
                data = json.loads(safety_lists_path.read_text(encoding="utf-8"))
                deny = data.get("deny", [])
                _mw_logger.warning(
                    "using fallback blacklist from %s (%d patterns)",
                    safety_lists_path,
                    len(deny),
                )
                return set(deny)
            except Exception as e:
                _mw_logger.warning("failed to load fallback safety lists: %s", e)

        _mw_logger.warning("no blacklist available; proceeding with empty blacklist")
        return set()

    def _is_blacklisted(self, url: str) -> str | None:
        for pattern in self._blacklist_patterns:
            if fnmatch.fnmatch(url, pattern) or pattern in url:
                return pattern
        return None

    def process_request(self, request: Request, spider: Spider) -> Request | None:
        """Check request safety before processing."""

        if request.url.endswith("/robots.txt"):
            return None

        blacklist_match = self._is_blacklisted(request.url)
        if blacklist_match:
            self._block_request(
                request, f"URL matches blacklist pattern: {blacklist_match}", spider
            )
            return None

        if request.method not in self.config.allowed_methods:
            self._block_request(
                request, f"Disallowed HTTP method: {request.method}", spider
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

        if self.job_id:
            return self._prompt_via_api(url, reason, pattern_key)

        return self._prompt_via_stdin(url, reason, pattern_key)

    def _prompt_via_api(self, url: str, reason: str, pattern: str) -> bool:
        try:
            with httpx.Client(timeout=5) as client:
                client.post(
                    f"{self.backend_url}/api/internal/safety-pending/{self.job_id}",
                    json={"url": url, "reason": reason, "pattern": pattern},
                )
        except httpx.RequestError:
            logger.warning(f"Failed to publish safety-pending for {pattern}")
        return False

    def _prompt_via_stdin(self, url: str, reason: str, pattern_key: str) -> bool:
        _mw_logger.warning(
            "URL BLOCKED BY SAFETY: %s | reason: %s | pattern: %s",
            url,
            reason,
            pattern_key,
        )
        try:
            return self._handle_stdin_response(pattern_key)
        except (EOFError, KeyboardInterrupt):
            pass
        return False

    def _handle_stdin_response(self, pattern_key: str) -> bool:
        response = input("Allow this URL? [y/N/always/never]: ").strip().lower()
        if response in {"y", "yes"}:
            return True
        if response in {"always", "a"}:
            if self.lists_manager:
                self.lists_manager.add_allow_pattern(pattern_key)
            return True
        if response in {"never", "n"} and self.lists_manager:
            self.lists_manager.add_deny_pattern(pattern_key)
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
            f"  Referer: {(request.headers.get('Referer') or b'').decode()}"
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
