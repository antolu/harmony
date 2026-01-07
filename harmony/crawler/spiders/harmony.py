from __future__ import annotations

import collections.abc
import typing

import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

from harmony.crawler.items import DocumentItem, PageItem
from harmony.crawler.processors import (
    DocsProcessor,
    DrupalProcessor,
    GenericProcessor,
    PageProcessor,
)


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
    ]

    rules = (
        Rule(
            LinkExtractor(
                deny=(
                    r"auth\.cern\.ch",
                    r"/logout",
                    r"/sign-out",
                    r"/logoff",
                    r"javascript:",
                    r"/node/\d+",  # Drupal-specific, but harmless for others
                ),
                deny_extensions=SKIP_EXTENSIONS,
                tags=("a", "area"),
                attrs=("href",),
            ),
            callback="parse_page",
            follow=True,
        ),
    )

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
        # Check if this is a document (parseable binary)
        url_lower = response.url.lower()
        is_document = any(
            url_lower.endswith(f".{ext}") for ext in self.DOCUMENT_EXTENSIONS
        )

        if is_document:
            # Handle document download
            self.logger.info(f"Found document: {response.url}")
            content_type = response.headers.get("Content-Type", b"").decode(
                "utf-8", errors="ignore"
            )
            item = DocumentItem(
                url=response.url,
                content=response.body,
                content_type=content_type,
                depth=response.meta.get("depth", 0),
            )
            item["_response"] = response
            yield item
            return

        # Find the matching processor for HTML pages
        for processor in self.processors:
            if processor.should_process(response):
                for item in processor.process_page(response):
                    item["_response"] = response
                    yield item
                return

        # Fallback to generic if no processor matched
        self.logger.warning(
            f"No processor matched for {response.url}, using generic fallback"
        )
        # Only try to access .text if it's an HTML response
        if hasattr(response, "text"):
            item = PageItem(
                url=response.url,
                html=response.text,
                depth=response.meta.get("depth", 0),
            )
            item["_response"] = response
            yield item
