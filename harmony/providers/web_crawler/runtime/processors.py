from __future__ import annotations

import abc
import collections.abc
import re
import typing

import scrapy

from harmony.providers.web_crawler.runtime.items import PageItem

if typing.TYPE_CHECKING:
    from scrapy.spiders import Spider


class PageProcessor(abc.ABC):
    """Base class for page processing logic."""

    def __init__(self, spider: Spider) -> None:
        self.spider = spider

    @abc.abstractmethod
    def should_process(self, response: scrapy.http.Response) -> bool:
        """Check if this processor should handle the response."""

    @abc.abstractmethod
    def process_page(
        self, response: scrapy.http.Response
    ) -> collections.abc.Generator[PageItem, None, None]:
        """Process the page and yield items."""


class DrupalProcessor(PageProcessor):
    """Processor for Drupal sites."""

    def should_process(self, response: scrapy.http.Response) -> bool:
        spider_type = response.meta.get("spider_type", "generic")
        return spider_type == "drupal"

    def process_page(
        self, response: scrapy.http.Response
    ) -> collections.abc.Generator[PageItem, None, None]:
        if not hasattr(response, "text"):
            self.spider.logger.info(f"Skipping non-text response: {response.url}")
            return

        yield PageItem(
            url=response.url,
            html=response.text,
            depth=response.meta.get("depth", 0),
        )


class DocsProcessor(PageProcessor):
    """Processor for documentation sites with version filtering."""

    # Version path patterns to skip
    VERSION_PATTERNS: typing.ClassVar[list[str]] = [
        r"/v?\d+\.\d+(\.\d+)?(/|$)",  # /1.0, /v1.0, /1.0.1
        r"/\d{4}(-\d{2}){0,2}(/|$)",  # /2024, /2024-01, /2024-01-15
    ]

    VERSION_ALLOWLIST: typing.ClassVar[set[str]] = {
        "stable",
        "latest",
        "current",
        "main",
        "master",
        "dev",
        "beta",
        "nightly",
    }

    def should_process(self, response: scrapy.http.Response) -> bool:
        spider_type = response.meta.get("spider_type", "generic")
        return spider_type == "docs"

    def _is_version_path(self, url: str, *, skip_versions: bool) -> bool:
        """Check if URL contains a numeric version path segment."""
        if not skip_versions:
            return False

        for pattern in self.VERSION_PATTERNS:
            if re.search(pattern, url):
                path_parts = url.split("/")
                for part in path_parts:
                    if part.lower() in self.VERSION_ALLOWLIST:
                        return False
                return True
        return False

    def process_page(
        self, response: scrapy.http.Response
    ) -> collections.abc.Generator[PageItem, None, None]:
        if not hasattr(response, "text"):
            self.spider.logger.info(f"Skipping non-text response: {response.url}")
            return

        spider_settings = response.meta.get("spider_settings", {})
        skip_versions = (
            spider_settings.skip_versions
            if hasattr(spider_settings, "skip_versions")
            else spider_settings.get("skip_versions", True)
            if isinstance(spider_settings, dict)
            else True
        )

        if self._is_version_path(response.url, skip_versions=skip_versions):
            self.spider.logger.info(f"Skipping version path: {response.url}")
            return

        yield PageItem(
            url=response.url,
            html=response.text,
            depth=response.meta.get("depth", 0),
        )


class GenericProcessor(PageProcessor):
    """Processor for generic sites."""

    def should_process(self, response: scrapy.http.Response) -> bool:
        spider_type = response.meta.get("spider_type", "generic")
        return spider_type == "generic"

    def process_page(
        self, response: scrapy.http.Response
    ) -> collections.abc.Generator[PageItem, None, None]:
        if not hasattr(response, "text"):
            self.spider.logger.info(f"Skipping non-text response: {response.url}")
            return

        yield PageItem(
            url=response.url,
            html=response.text,
            depth=response.meta.get("depth", 0),
        )
