from __future__ import annotations

import re
from unittest.mock import Mock
from urllib.parse import urlparse

from harmony.crawler.config import (
    CrawlerConfig,
    DocsSpiderSettings,
    DrupalSpiderSettings,
)
from harmony.crawler.spiders.harmony import HarmonySpider


def test_docs_deny_patterns_filter_sphinx_urls() -> None:
    """Test that docs spider filters Sphinx-generated URLs."""
    # Create mock spider with config
    spider = Mock(spec=HarmonySpider)
    spider.crawler_config = CrawlerConfig(
        start_urls=["https://docs.example.com"],
        spider_settings={
            "docs": DocsSpiderSettings(
                deny_patterns=[
                    r"/_sources/",
                    r"\.rst\.txt$",
                    r"/genindex\.html$",
                ]
            )
        },
        domain_routing={
            "exact": {"docs.example.com": "docs"},
            "default": "generic",
        },
    )

    # Test URLs that should be filtered
    filtered_urls = [
        "https://docs.example.com/_sources/index.rst.txt",
        "https://docs.example.com/api/_sources/module.rst.txt",
        "https://docs.example.com/genindex.html",
        "https://docs.example.com/guide.rst.txt",
    ]

    # Test URLs that should NOT be filtered
    allowed_urls = [
        "https://docs.example.com/index.html",
        "https://docs.example.com/api/reference.html",
        "https://docs.example.com/guide.html",
    ]

    # Simulate the filtering logic from _filter_request
    def should_filter(url: str) -> bool:
        domain = urlparse(url).netloc
        spider_type = spider.crawler_config.get_spider_for_domain(domain)
        spider_settings = spider.crawler_config.get_spider_settings_for(spider_type)

        if not spider_settings:
            return False

        deny_patterns = getattr(spider_settings, "deny_patterns", [])
        return any(re.search(pattern, url) for pattern in deny_patterns)

    # Verify filtered URLs are blocked
    for url in filtered_urls:
        assert should_filter(url), f"Expected {url} to be filtered"

    # Verify allowed URLs pass through
    for url in allowed_urls:
        assert not should_filter(url), f"Expected {url} to be allowed"


def test_drupal_deny_patterns_filter_node_urls() -> None:
    """Test that drupal spider filters /node/NNN URLs."""
    spider = Mock(spec=HarmonySpider)
    spider.crawler_config = CrawlerConfig(
        start_urls=["https://drupal.example.com"],
        spider_settings={"drupal": DrupalSpiderSettings(deny_patterns=[r"/node/\d+"])},
        domain_routing={
            "exact": {"drupal.example.com": "drupal"},
            "default": "generic",
        },
    )

    def should_filter(url: str) -> bool:
        domain = urlparse(url).netloc
        spider_type = spider.crawler_config.get_spider_for_domain(domain)
        spider_settings = spider.crawler_config.get_spider_settings_for(spider_type)

        if not spider_settings:
            return False

        deny_patterns = getattr(spider_settings, "deny_patterns", [])
        return any(re.search(pattern, url) for pattern in deny_patterns)

    # Should filter node URLs
    assert should_filter("https://drupal.example.com/node/123")
    assert should_filter("https://drupal.example.com/en/node/456")

    # Should allow other URLs
    assert not should_filter("https://drupal.example.com/page/about")
    assert not should_filter("https://drupal.example.com/article/test")


def test_cross_domain_filtering() -> None:
    """Test that deny patterns only apply to their spider type's domains."""
    spider = Mock(spec=HarmonySpider)
    spider.crawler_config = CrawlerConfig(
        start_urls=["https://docs.example.com", "https://drupal.example.com"],
        spider_settings={
            "docs": DocsSpiderSettings(deny_patterns=[r"/_sources/"]),
            "drupal": DrupalSpiderSettings(deny_patterns=[r"/node/\d+"]),
        },
        domain_routing={
            "exact": {
                "docs.example.com": "docs",
                "drupal.example.com": "drupal",
            },
            "default": "generic",
        },
    )

    def should_filter(url: str) -> bool:
        domain = urlparse(url).netloc
        spider_type = spider.crawler_config.get_spider_for_domain(domain)
        spider_settings = spider.crawler_config.get_spider_settings_for(spider_type)

        if not spider_settings:
            return False

        deny_patterns = getattr(spider_settings, "deny_patterns", [])
        return any(re.search(pattern, url) for pattern in deny_patterns)

    # Docs patterns only apply to docs domain
    assert should_filter("https://docs.example.com/_sources/index.rst.txt")
    assert not should_filter("https://drupal.example.com/_sources/index.rst.txt")

    # Drupal patterns only apply to drupal domain
    assert should_filter("https://drupal.example.com/node/123")
    assert not should_filter("https://docs.example.com/node/123")
