from __future__ import annotations

import logging
import typing

from scrapy import signals
from scrapy.exceptions import NotConfigured

if typing.TYPE_CHECKING:
    from scrapy import Spider
    from scrapy.crawler import Crawler
    from scrapy.http import Response

logger = logging.getLogger(__name__)


class ProgressExtension:
    """Extension that logs crawl progress periodically."""

    def __init__(self, crawler: Crawler) -> None:
        self.crawler = crawler
        self.pages_crawled = 0
        self.pages_skipped = 0
        self.log_interval = 10  # Log every N pages

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> ProgressExtension:
        if crawler.settings.get("LOG_LEVEL") == "WARNING":
            # Only enable progress reporting in WARNING mode (silent mode)
            ext = cls(crawler)
            crawler.signals.connect(ext.item_scraped, signal=signals.item_scraped)
            crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
            crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
            crawler.signals.connect(
                ext.response_received, signal=signals.response_received
            )
            return ext
        raise NotConfigured

    def spider_opened(self, spider: Spider) -> None:  # noqa: PLR6301
        logger.warning(f"Started crawling with {spider.name} spider")

    def response_received(self, response: Response, spider: Spider) -> None:
        # Count responses (not all will produce items)
        pass

    def item_scraped(self, item: typing.Any, spider: Spider) -> None:
        self.pages_crawled += 1
        if self.pages_crawled % self.log_interval == 0:
            stats = self.crawler.stats.get_stats()
            logger.warning(
                f"Progress: {self.pages_crawled} pages crawled, "
                f"{stats.get('downloader/request_count', 0)} requests, "
                f"{stats.get('scheduler/enqueued', 0)} queued"
            )

    def spider_closed(self, spider: Spider) -> None:
        stats = self.crawler.stats.get_stats()
        logger.warning(
            f"Crawl finished: {self.pages_crawled} pages crawled, "
            f"{stats.get('downloader/request_count', 0)} total requests, "
            f"{stats.get('downloader/response_status_count/200', 0)} successful responses"
        )
