from __future__ import annotations

import typing
from urllib.parse import urlparse

from scrapy import Request, Spider
from scrapy.http import Response

if typing.TYPE_CHECKING:
    from scrapy.crawler import Crawler


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
