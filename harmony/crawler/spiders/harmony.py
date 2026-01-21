from __future__ import annotations

import collections.abc
import typing
from email.utils import parsedate_to_datetime

import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

from harmony.crawler.items import DocumentItem, PageItem
from harmony.crawler.logger import logger
from harmony.crawler.processors import (
    DocsProcessor,
    DrupalProcessor,
    GenericProcessor,
    PageProcessor,
)


def _extract_response_meta(response: scrapy.http.Response) -> dict:
    """Extract response metadata for state tracking."""
    # Parse Last-Modified header to Unix timestamp for Elasticsearch
    last_modified = None
    last_modified_header = response.headers.get("Last-Modified", b"").decode(
        "utf-8", errors="ignore"
    )
    if last_modified_header:
        try:
            dt = parsedate_to_datetime(last_modified_header)
            last_modified = int(dt.timestamp())
        except (ValueError, TypeError):
            pass

    return {
        "last_modified": last_modified,
        "etag": response.headers.get("ETag", b"").decode("utf-8", errors="ignore")
        or None,
        "status_code": response.status,
        "content_type": response.headers.get("Content-Type", b"").decode(
            "utf-8", errors="ignore"
        )
        or None,
    }


class HarmonySpider(CrawlSpider):
    """Main spider that delegates processing to type-specific processors."""

    name = "harmony"

    start_urls: typing.ClassVar[list[str]] = []
    allowed_domains: typing.ClassVar[list[str]] = []

    # Media files to skip (not parseable)
    SKIP_EXTENSIONS: typing.ClassVar[list[str]] = [
        "mng",
        "pct",
        "bmp",
        "gif",
        "jpg",
        "jpeg",
        "png",
        "pst",
        "psp",
        "tif",
        "tiff",
        "ai",
        "drw",
        "dxf",
        "eps",
        "ps",
        "svg",
        "cdr",
        "ico",
        "mp3",
        "wma",
        "ogg",
        "wav",
        "ra",
        "aac",
        "mid",
        "au",
        "aiff",
        "3gp",
        "asf",
        "asx",
        "avi",
        "mov",
        "mp4",
        "mpg",
        "qt",
        "rm",
        "swf",
        "wmv",
        "m4a",
        "m4v",
        "flv",
        "webm",
        "zip",
        "rar",
        "7z",
        "gz",
        "tar",
        "iso",
        "dmg",
        "exe",
        "msi",
        "bin",
    ]

    # Document extensions to download for future parsing
    DOCUMENT_EXTENSIONS: typing.ClassVar[list[str]] = [
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        "odt",
        "ods",
        "odp",
        "rtf",
        "txt",
        "csv",
        "md",
        "markdown",
        "mdown",
        "mkd",
    ]

    # Note: rules will be set in from_crawler based on config
    rules: tuple = ()

    @classmethod
    def from_crawler(
        cls, crawler: scrapy.crawler.Crawler, *args: typing.Any, **kwargs: typing.Any
    ) -> HarmonySpider:
        """Create spider instance with rules built from crawler settings."""
        # Build deny patterns from crawler settings before spider init
        deny = []

        # Get safety config
        safety_config = crawler.settings.get("SAFETY_CONFIG")
        if safety_config:
            deny.extend(safety_config.dangerous_url_patterns)
            deny.extend(safety_config.additional_deny_patterns)

        # Get pre-loaded safety lists
        safety_lists_manager = crawler.settings.get("SAFETY_LISTS_MANAGER")
        if safety_lists_manager:
            deny.extend(safety_lists_manager.get_deny_patterns())

        # Add spider-specific patterns
        deny.extend([
            r"javascript:",  # JavaScript links
            r"/node/\d+",  # Drupal node IDs
        ])

        # Create rules tuple
        rules = (
            Rule(
                LinkExtractor(
                    deny=tuple(deny),
                    deny_extensions=cls.SKIP_EXTENSIONS,
                    tags=("a", "area"),
                    attrs=("href",),
                ),
                callback="parse_page",
                follow=True,
            ),
        )

        # Create spider instance
        spider = super().from_crawler(crawler, *args, **kwargs)
        spider.rules = rules
        spider._compile_rules()  # noqa: SLF001

        return spider

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)

        # Initialize processors
        self.processors: list[PageProcessor] = [
            DrupalProcessor(self),
            DocsProcessor(self),
            GenericProcessor(self),
        ]

    def parse_page(
        self, response: scrapy.http.Response
    ) -> collections.abc.Generator[PageItem | DocumentItem, None, None]:
        """Route to the appropriate processor based on spider_type."""
        # Skip robots.txt
        if response.url.endswith("/robots.txt"):
            return

        logger.info(f"Visiting: {response.url}")

        # Check if this is a document (parseable binary)
        url_lower = response.url.lower()
        is_document = any(
            url_lower.endswith(f".{ext}") for ext in self.DOCUMENT_EXTENSIONS
        )

        if is_document:
            # Handle document download
            logger.info(f"Found document: {response.url}")
            item = DocumentItem(
                url=response.url,
                content=response.body,
                depth=response.meta.get("depth", 0),
                **_extract_response_meta(response),
            )
            yield item
            return

        # Find the matching processor for HTML pages
        for processor in self.processors:
            if processor.should_process(response):
                response_meta = _extract_response_meta(response)
                for item in processor.process_page(response):
                    for key, value in response_meta.items():
                        item[key] = value
                    yield item
                return

        # Fallback to generic if no processor matched
        logger.warning(
            f"No processor matched for {response.url}, using generic fallback"
        )
        # Only try to access .text if it's an HTML response
        if hasattr(response, "text"):
            item = PageItem(
                url=response.url,
                html=response.text,
                depth=response.meta.get("depth", 0),
                **_extract_response_meta(response),
            )
            yield item
