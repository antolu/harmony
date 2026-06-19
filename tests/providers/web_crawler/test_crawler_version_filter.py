from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import scrapy.http

from harmony.providers.web_crawler.runtime.spiders.harmony import HarmonySpider


@pytest.fixture
def spider() -> HarmonySpider:
    """Create a HarmonySpider instance for testing."""
    return HarmonySpider()


def test_is_version_path_simple_version() -> None:
    assert HarmonySpider._is_version_path("https://docs.example.com/1.0/guide")
    assert HarmonySpider._is_version_path("https://docs.example.com/1.0.1/guide")
    assert HarmonySpider._is_version_path("https://docs.example.com/v1.0/guide")
    assert HarmonySpider._is_version_path("https://docs.example.com/v1.0.1/guide")


def test_is_version_path_date_version() -> None:
    assert HarmonySpider._is_version_path("https://docs.example.com/2024/guide")
    assert HarmonySpider._is_version_path("https://docs.example.com/2024-01/guide")
    assert HarmonySpider._is_version_path("https://docs.example.com/2024-01-15/guide")


def test_is_version_path_trailing_slash() -> None:
    assert HarmonySpider._is_version_path("https://docs.example.com/1.0.1/")
    assert HarmonySpider._is_version_path("https://docs.example.com/v2.3/")


def test_is_version_path_end_of_url() -> None:
    assert HarmonySpider._is_version_path("https://docs.example.com/docs/1.0.1")
    assert HarmonySpider._is_version_path("https://docs.example.com/docs/v2.3")


def test_is_version_path_allowlisted_versions() -> None:
    assert not HarmonySpider._is_version_path("https://docs.example.com/stable/guide")
    assert not HarmonySpider._is_version_path("https://docs.example.com/latest/guide")
    assert not HarmonySpider._is_version_path("https://docs.example.com/current/guide")
    assert not HarmonySpider._is_version_path("https://docs.example.com/main/guide")
    assert not HarmonySpider._is_version_path("https://docs.example.com/master/guide")
    assert not HarmonySpider._is_version_path("https://docs.example.com/dev/guide")
    assert not HarmonySpider._is_version_path("https://docs.example.com/beta/guide")
    assert not HarmonySpider._is_version_path("https://docs.example.com/nightly/guide")


def test_is_version_path_allowlisted_case_insensitive() -> None:
    assert not HarmonySpider._is_version_path("https://docs.example.com/STABLE/guide")
    assert not HarmonySpider._is_version_path("https://docs.example.com/Latest/guide")
    assert not HarmonySpider._is_version_path("https://docs.example.com/CURRENT/guide")


def test_is_version_path_no_version() -> None:
    assert not HarmonySpider._is_version_path("https://docs.example.com/guide")
    assert not HarmonySpider._is_version_path("https://docs.example.com/api/reference")
    assert not HarmonySpider._is_version_path("https://docs.example.com/tutorial/intro")


def test_is_version_path_real_world_nxcals() -> None:
    assert HarmonySpider._is_version_path(
        "https://nxcals-docs.web.cern.ch/1.1.1/user-guide/swan/notebook-examples/"
    )
    assert HarmonySpider._is_version_path(
        "https://nxcals-docs.web.cern.ch/1.1.1/user-guide/swan/swan-session/"
    )
    assert not HarmonySpider._is_version_path(
        "https://nxcals-docs.web.cern.ch/current/user-guide/swan/notebook-examples/"
    )


class MockCrawlerConfig:
    """Mock crawler config for testing."""

    def __init__(
        self,
        domain_to_spider: dict[str, str] | None = None,
        spider_settings: dict[str, dict] | None = None,
    ) -> None:
        self._domain_to_spider = domain_to_spider or {}
        self._spider_settings = spider_settings or {}

    def get_spider_for_domain(self, domain: str) -> str:
        return self._domain_to_spider.get(domain, "generic")

    def get_spider_settings_for(self, spider_type: str) -> dict:
        return self._spider_settings.get(spider_type, {})


def _make_mock_response() -> scrapy.http.Response:
    """Create a mock response."""
    response = MagicMock(spec=scrapy.http.Response)
    response.meta = {}
    return response


def _make_mock_request(url: str) -> scrapy.Request:
    """Create a mock request with the given URL."""
    request = MagicMock(spec=scrapy.Request)
    request.url = url
    return request


def test_filter_version_request_non_docs_spider(spider: HarmonySpider) -> None:
    """Non-docs spiders should not filter version URLs."""
    spider.crawler_config = MockCrawlerConfig(
        domain_to_spider={"example.com": "generic"},
    )
    request = _make_mock_request("https://example.com/1.0.1/guide")
    response = _make_mock_response()

    result = spider._filter_request(request, response)
    assert result is request


def test_filter_version_request_docs_spider_filters_version(
    spider: HarmonySpider,
) -> None:
    """Docs spider should filter version URLs when skip_versions is enabled."""
    spider.crawler_config = MockCrawlerConfig(
        domain_to_spider={"nxcals-docs.web.cern.ch": "docs"},
        spider_settings={"docs": {"skip_versions": True}},
    )
    request = _make_mock_request("https://nxcals-docs.web.cern.ch/1.1.1/guide")
    response = _make_mock_response()

    result = spider._filter_request(request, response)
    assert result is None


def test_filter_version_request_docs_spider_allows_safe_url(
    spider: HarmonySpider,
) -> None:
    """Docs spider should not filter non-version URLs."""
    spider.crawler_config = MockCrawlerConfig(
        domain_to_spider={"nxcals-docs.web.cern.ch": "docs"},
        spider_settings={"docs": {"skip_versions": True}},
    )
    request = _make_mock_request("https://nxcals-docs.web.cern.ch/current/guide")
    response = _make_mock_response()

    result = spider._filter_request(request, response)
    assert result is request


def test_filter_version_request_docs_spider_skip_versions_disabled(
    spider: HarmonySpider,
) -> None:
    """Docs spider should not filter when skip_versions is disabled."""
    spider.crawler_config = MockCrawlerConfig(
        domain_to_spider={"nxcals-docs.web.cern.ch": "docs"},
        spider_settings={"docs": {"skip_versions": False}},
    )
    request = _make_mock_request("https://nxcals-docs.web.cern.ch/1.1.1/guide")
    response = _make_mock_response()

    result = spider._filter_request(request, response)
    assert result is request


def test_filter_version_request_docs_spider_default_skip_versions(
    spider: HarmonySpider,
) -> None:
    """Docs spider should default to skip_versions=True when not specified."""
    spider.crawler_config = MockCrawlerConfig(
        domain_to_spider={"nxcals-docs.web.cern.ch": "docs"},
        spider_settings={"docs": {}},
    )
    request = _make_mock_request("https://nxcals-docs.web.cern.ch/1.1.1/guide")
    response = _make_mock_response()

    result = spider._filter_request(request, response)
    assert result is None


def test_filter_version_request_drupal_spider(spider: HarmonySpider) -> None:
    """Drupal spider should not filter version URLs."""
    spider.crawler_config = MockCrawlerConfig(
        domain_to_spider={"example.com": "drupal"},
    )
    request = _make_mock_request("https://example.com/1.0.1/guide")
    response = _make_mock_response()

    result = spider._filter_request(request, response)
    assert result is request


def test_filter_version_request_no_config(spider: HarmonySpider) -> None:
    """Without crawler_config, requests should pass through."""
    spider.crawler_config = None
    request = _make_mock_request("https://example.com/1.0.1/guide")
    response = _make_mock_response()

    result = spider._filter_request(request, response)
    assert result is request


@pytest.mark.parametrize(
    ("url", "should_be_version"),
    [
        ("https://docs.example.com/1.0/guide", True),
        ("https://docs.example.com/1.0.1/guide", True),
        ("https://docs.example.com/v1.0/guide", True),
        ("https://docs.example.com/v1.0.1/guide", True),
        ("https://docs.example.com/2.3.4/api", True),
        ("https://docs.example.com/10.20.30/ref", True),
        ("https://docs.example.com/stable/guide", False),
        ("https://docs.example.com/latest/guide", False),
        ("https://docs.example.com/current/api", False),
        ("https://docs.example.com/main/ref", False),
        ("https://docs.example.com/guide", False),
        ("https://docs.example.com/api/v1/users", False),
    ],
)
def test_is_version_path_parametrized(url: str, should_be_version: bool) -> None:  # noqa: FBT001
    assert HarmonySpider._is_version_path(url) == should_be_version
