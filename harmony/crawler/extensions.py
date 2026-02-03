from __future__ import annotations

import logging
import time
import typing
from datetime import UTC, datetime

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

    def __init__(self, crawler: Crawler, stats_writer: typing.Any = None) -> None:
        self.crawler = crawler
        self.pages_crawled = 0
        self.pages_skipped = 0
        self.log_interval = 10
        self._stats_writer = stats_writer
        self._current_url: str | None = None
        self._start_time: float | None = None

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> ProgressExtension:
        stats_writer = crawler.settings.get("STATS_WRITER")
        if (
            crawler.settings.get("LOG_LEVEL") in {"INFO", "WARNING", "CRITICAL"}
            or stats_writer
        ):
            ext = cls(crawler, stats_writer)
            crawler.signals.connect(ext.item_scraped, signal=signals.item_scraped)
            crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
            crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
            crawler.signals.connect(
                ext.response_received, signal=signals.response_received
            )
            return ext
        raise NotConfigured

    def spider_opened(self, spider: Spider) -> None:
        logger.info(f"Started crawling with {spider.name} spider")
        self._start_time = time.time()

    def response_received(self, response: Response, spider: Spider) -> None:
        self._current_url = response.url

    def item_scraped(self, item: typing.Any, spider: Spider) -> None:
        self.pages_crawled += 1
        if self.pages_crawled % self.log_interval == 0:
            stats = self.crawler.stats.get_stats()
            enqueued = stats.get("scheduler/enqueued", 0)
            dequeued = stats.get("scheduler/dequeued", 0)
            pending = enqueued - dequeued
            logger.info(
                f"Progress: {self.pages_crawled} pages crawled, "
                f"{stats.get('downloader/request_count', 0)} requests, "
                f"{pending} pending"
            )
            self._export_stats()

    def _export_stats(self) -> None:
        """Export stats via the configured writer."""
        if not self._stats_writer:
            return

        stats = self.crawler.stats.get_stats()
        enqueued = stats.get("scheduler/enqueued", 0)
        dequeued = stats.get("scheduler/dequeued", 0)

        elapsed = time.time() - (self._start_time or time.time())
        pages_per_min = (self.pages_crawled / elapsed * 60) if elapsed > 0 else 0.0

        export_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "pages_crawled": self.pages_crawled,
            "requests_made": stats.get("downloader/request_count", 0),
            "pages_pending": enqueued - dequeued,
            "current_url": self._current_url,
            "pages_per_min": round(pages_per_min, 2),
            "elapsed_seconds": round(elapsed, 1),
        }

        self._stats_writer.publish(export_data)

    def spider_closed(self, spider: Spider) -> None:
        stats = self.crawler.stats.get_stats()
        logger.info(
            f"Crawl finished: {self.pages_crawled} pages crawled, "
            f"{stats.get('downloader/request_count', 0)} total requests, "
            f"{stats.get('downloader/response_status_count/200', 0)} successful responses"
        )
        self._export_stats()


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
        logger.info("Checking for missing URLs...")
        urls_to_delete = self.state_manager.get_urls_to_delete(self.threshold)

        if not urls_to_delete:
            logger.info("No URLs to delete")
            return

        logger.info(
            f"Found {len(urls_to_delete)} URLs missing for {self.threshold}+ crawls"
        )

        if self.delete_missing:
            logger.info(f"Deleting {len(urls_to_delete)} URLs from state index...")
            self.state_manager.delete_states(urls_to_delete)
            logger.info("Deletion complete")
        else:
            logger.info(
                "URLs marked for deletion but not deleted (use --crawler.delete_missing to enable)"
            )
            for url in urls_to_delete[: self._MAX_URLS_TO_SHOW]:
                logger.info(f"  - {url}")
            if len(urls_to_delete) > self._MAX_URLS_TO_SHOW:
                logger.info(
                    f"  ... and {len(urls_to_delete) - self._MAX_URLS_TO_SHOW} more"
                )
