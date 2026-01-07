from __future__ import annotations

import typing
from urllib.parse import urlparse

from scrapy import Request, Spider
from scrapy.http import Response

from harmony.crawler.logger import logger

if typing.TYPE_CHECKING:
    from scrapy.crawler import Crawler

    from harmony.crawler.state import CrawlStateManager


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

        # Store spider type in request meta
        request.meta["spider_type"] = spider_type

        # Also store spider-specific settings
        spider_settings = self.config.get_spider_settings_for(spider_type)
        request.meta["spider_settings"] = spider_settings

    def process_response(  # noqa: PLR6301
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
    ) -> Response | None:
        """Handle 304 Not Modified and 404 responses."""
        if not self.state_manager:
            return response

        if response.status == self._HTTP_NOT_MODIFIED:
            logger.info(f"304 Not Modified: {request.url}")
            self.state_manager.mark_seen(request.url)
            return None

        if response.status in {self._HTTP_NOT_FOUND, self._HTTP_GONE}:
            logger.warning(f"{response.status} Not Found: {request.url}")
            self.state_manager.increment_missing(request.url)
            return None

        return response
