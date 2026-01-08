from __future__ import annotations

import logging
import typing

from scrapy import signals
from scrapy.exceptions import NotConfigured

if typing.TYPE_CHECKING:
    from scrapy import Spider
    from scrapy.crawler import Crawler
    from scrapy.http import Response

    from harmony.crawler.state import CrawlStateManager

logger = logging.getLogger(__name__)


class ProgressExtension:
    """Extension that logs crawl progress periodically."""

    def __init__(self, crawler: Crawler) -> None:
        self.crawler = crawler
        self.pages_crawled = 0
        self.pages_skipped = 0
        self.log_interval = 10

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

    def spider_opened(self, spider: Spider) -> None:
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


class DeletionDetectorExtension:
    """Extension that detects and optionally deletes missing URLs after crawl."""

    _MAX_URLS_TO_SHOW = 10

    def __init__(
        self,
        crawler: Crawler,
        state_manager: CrawlStateManager,
        *,
        delete_missing: bool,
        threshold: int,
    ) -> None:
        self.crawler = crawler
        self.state_manager = state_manager
        self.delete_missing = delete_missing
        self.threshold = threshold

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> DeletionDetectorExtension:
        state_manager = crawler.settings.get("STATE_MANAGER")
        if not state_manager:
            msg = "State manager not configured"
            raise NotConfigured(msg)

        delete_missing = crawler.settings.get("DELETE_MISSING", False)
        threshold = crawler.settings.get("MISSING_THRESHOLD", 3)

        ext = cls(
            crawler,
            state_manager,
            delete_missing=delete_missing,
            threshold=threshold,
        )
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        return ext

    def spider_closed(self, spider: Spider) -> None:
        logger.warning("Checking for missing URLs...")
        urls_to_delete = self.state_manager.get_urls_to_delete(self.threshold)

        if not urls_to_delete:
            logger.warning("No URLs to delete")
            return

        logger.warning(
            f"Found {len(urls_to_delete)} URLs missing for {self.threshold}+ crawls"
        )

        if self.delete_missing:
            logger.warning(f"Deleting {len(urls_to_delete)} URLs from state index...")
            self.state_manager.delete_states(urls_to_delete)
            logger.warning("Deletion complete")
        else:
            logger.warning(
                "URLs marked for deletion but not deleted (use --crawler.delete_missing to enable)"
            )
            for url in urls_to_delete[: self._MAX_URLS_TO_SHOW]:
                logger.warning(f"  - {url}")
            if len(urls_to_delete) > self._MAX_URLS_TO_SHOW:
                logger.warning(
                    f"  ... and {len(urls_to_delete) - self._MAX_URLS_TO_SHOW} more"
                )
