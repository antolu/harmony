from __future__ import annotations

import collections.abc
import re
import typing
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

from harmony.providers.web_crawler.runtime.items import DocumentItem, PageItem
from harmony.providers.web_crawler.runtime.logger import logger
from harmony.providers.web_crawler.runtime.processors import (
    DocsProcessor,
    DrupalProcessor,
    GenericProcessor,
    PageProcessor,
)


def _extract_response_meta(response: scrapy.http.Response) -> dict:
    """Extract response metadata for state tracking."""
    # Parse Last-Modified header to Unix timestamp for Elasticsearch
    last_modified = None
    last_modified_header = (response.headers.get("Last-Modified") or b"").decode(
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
        "etag": (response.headers.get("ETag") or b"").decode("utf-8", errors="ignore")
        or None,
        "status_code": response.status,
        "content_type": (response.headers.get("Content-Type") or b"").decode(
            "utf-8", errors="ignore"
        )
        or None,
    }


class HarmonySpider(CrawlSpider):
    """Main spider that delegates processing to type-specific processors."""

    name = "harmony"

    start_urls: typing.ClassVar[list[str]] = []  # type: ignore[misc]  # scrapy Spider base class declares this as instance variable
    allowed_domains: typing.ClassVar[list[str]] = []

    # Crawler config for domain routing (set in from_crawler)
    crawler_config: typing.Any = None

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
        "xml",
        "rss",
        "atom",
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
        "xml",
        "rss",
        "atom",
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

    # Note: rules will be set in from_crawler based on config
    rules: tuple = ()

    @classmethod
    def _is_version_path(cls, url: str) -> bool:
        """Check if URL contains a numeric version path segment."""
        for pattern in cls.VERSION_PATTERNS:
            match = re.search(pattern, url)
            if match:
                # Extract the specific path segment that matched the version pattern
                matched_segment = match.group(0).strip("/")
                return matched_segment.lower() not in cls.VERSION_ALLOWLIST
        return False

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

        # Get auth domain patterns to prevent crawling auth provider URLs
        auth_config = crawler.settings.get("AUTH_CONFIG")
        if auth_config and hasattr(auth_config, "providers"):
            for provider in auth_config.providers:
                if hasattr(provider, "auth_domain_patterns"):
                    for pattern in provider.auth_domain_patterns:
                        # Escape dots and convert to regex that matches URLs
                        escaped = re.escape(pattern)
                        deny.append(escaped)

        # Add spider-specific patterns
        deny.extend([
            r"javascript:",  # JavaScript links
        ])

        # Add user-defined scope patterns from crawler config
        crawler_config = crawler.settings.get("CRAWLER_CONFIG")
        if crawler_config and crawler_config.link_extractor_deny:
            deny.extend(crawler_config.link_extractor_deny)

        # Create rules tuple with process_request for version filtering
        logger.debug(f"LinkExtractor deny patterns: {deny}")
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
                process_request="_filter_request",
            ),
        )

        # Create spider instance
        spider = super().from_crawler(crawler, *args, **kwargs)
        spider.rules = rules
        spider._compile_rules()  # noqa: SLF001

        # Store crawler config for version filtering
        spider.crawler_config = crawler.settings.get("CRAWLER_CONFIG")

        return spider

    def _filter_request(
        self, request: scrapy.Request, response: scrapy.http.Response
    ) -> scrapy.Request | None:
        """Filter URLs based on target domain's spider settings."""
        if not self.crawler_config:
            return request

        domain = urlparse(request.url).netloc
        spider_type = self.crawler_config.get_spider_for_domain(domain)
        spider_settings = self.crawler_config.get_spider_settings_for(spider_type)

        if spider_settings is None:
            return request

        # Helper to get setting from either object or dict
        def get_setting(name: str, *, default: typing.Any = None) -> typing.Any:
            if isinstance(spider_settings, dict):
                return spider_settings.get(name, default)
            return getattr(spider_settings, name, default)

        # Check deny patterns (all spider types)
        deny_patterns = get_setting("deny_patterns", default=[])
        for pattern in deny_patterns:
            if re.search(pattern, request.url):
                logger.info(f"Skipping {spider_type} URL (deny pattern): {request.url}")
                if hasattr(self, "crawler") and self.crawler and self.crawler.stats:
                    self.crawler.stats.inc_value(f"filter/deny/{spider_type}")
                return None

        # Version filtering (docs only)
        if spider_type == "docs":
            skip_versions = get_setting("skip_versions", default=True)
            if skip_versions and self._is_version_path(request.url):
                logger.info(f"Skipping version URL: {request.url}")
                if hasattr(self, "crawler") and self.crawler and self.crawler.stats:
                    self.crawler.stats.inc_value("filter/version")
                return None

        return request

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
        logger.info(f"Visiting: {response.url}")

        # Skip non-HTML responses (XML, JSON, etc.) unless they are documented binary formats
        content_type = (
            (response.headers.get("Content-Type") or b"")
            .decode("utf-8", errors="ignore")
            .lower()
        )
        if "xml" in content_type or "rss" in content_type or "atom" in content_type:
            logger.info(f"Skipping {content_type} response: {response.url}")
            return

        # Check if this is a document (parseable binary)
        url_lower = response.url.lower()
        is_document = any(
            url_lower.endswith(f".{ext}") for ext in self.DOCUMENT_EXTENSIONS
        )

        if is_document:
            # Handle document download
            logger.info(f"Found document: {response.url}")
            yield DocumentItem(
                url=response.url,
                content=response.body,
                depth=response.meta.get("depth", 0),
                **_extract_response_meta(response),
            )
            return

        # Find the matching processor for HTML pages
        for processor in self.processors:
            if processor.should_process(response):
                response_meta = _extract_response_meta(response)
                for p_item in processor.process_page(response):
                    for key, value in response_meta.items():
                        p_item[key] = value
                    yield p_item
                return

        # Fallback to generic if no processor matched
        logger.warning(
            f"No processor matched for {response.url}, using generic fallback"
        )
        # Only try to access .text if it's an HTML response
        if hasattr(response, "text"):
            yield PageItem(
                url=response.url,
                html=response.text,
                depth=response.meta.get("depth", 0),
                **_extract_response_meta(response),
            )
