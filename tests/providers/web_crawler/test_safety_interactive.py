from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from scrapy.http import Request

from harmony.core import FileSafetyListsWriter
from harmony.providers.web_crawler.runtime.middlewares import SafetyMiddleware
from harmony.providers.web_crawler.runtime.safety import SafetyConfig
from harmony.providers.web_crawler.runtime.safety_lists import SafetyListsManager


@patch("sys.stdout.isatty", return_value=True)
@patch("builtins.input", return_value="y")
def test_prompt_allow_once(mock_input: Mock, mock_isatty: Mock, tmp_path: Path) -> None:
    """Test allowing URL once."""
    lists_manager = SafetyListsManager(FileSafetyListsWriter(tmp_path))

    config = SafetyConfig()
    middleware = SafetyMiddleware(config, lists_manager, interactive=True)

    result = middleware._prompt_user(
        "https://example.com/admin/delete/123",
        "Matched dangerous pattern",
        Mock(),
    )

    assert result is True
    assert len(lists_manager.get_allow_patterns()) == 0


@patch("sys.stdout.isatty", return_value=True)
@patch("builtins.input", return_value="always")
def test_prompt_allow_always(
    mock_input: Mock, mock_isatty: Mock, tmp_path: Path
) -> None:
    """Test adding to permanent allow-list."""
    lists_manager = SafetyListsManager(FileSafetyListsWriter(tmp_path))

    config = SafetyConfig()
    middleware = SafetyMiddleware(config, lists_manager, interactive=True)

    result = middleware._prompt_user(
        "https://example.com/admin/delete/123",
        "Matched dangerous pattern",
        Mock(),
    )

    assert result is True
    assert len(lists_manager.get_allow_patterns()) == 1


@patch("sys.stdout.isatty", return_value=True)
@patch("builtins.input", return_value="never")
def test_prompt_deny_never(mock_input: Mock, mock_isatty: Mock, tmp_path: Path) -> None:
    """Test adding to permanent deny-list."""
    lists_manager = SafetyListsManager(FileSafetyListsWriter(tmp_path))

    config = SafetyConfig()
    middleware = SafetyMiddleware(config, lists_manager, interactive=True)

    result = middleware._prompt_user(
        "https://example.com/admin/delete/123",
        "Matched dangerous pattern",
        Mock(),
    )

    assert result is False
    assert len(lists_manager.get_deny_patterns()) == 1


def test_url_to_pattern_removes_ids() -> None:
    """Test converting URLs to reusable patterns."""
    config = SafetyConfig()
    middleware = SafetyMiddleware(config, None, interactive=False)

    pattern = middleware._url_to_pattern("https://example.com/admin/delete/123")

    assert r"\d+" in pattern
    assert "123" not in pattern


def test_interactive_mode_merges_runtime_patterns(tmp_path: Path) -> None:
    """Test that runtime patterns are merged from lists manager."""
    lists_manager = SafetyListsManager(FileSafetyListsWriter(tmp_path))
    lists_manager.add_allow_pattern(r"example\.com/special")

    config = SafetyConfig()
    middleware = SafetyMiddleware(config, lists_manager, interactive=False)

    runtime_config = middleware._get_runtime_config()

    assert r"example\.com/special" in runtime_config.allow_list_patterns


def test_process_request_with_lists_manager(tmp_path: Path) -> None:
    """Test request processing with lists manager."""
    lists_manager = SafetyListsManager(FileSafetyListsWriter(tmp_path))
    lists_manager.add_allow_pattern(r"example\.com/admin/delete/.*")

    config = SafetyConfig()
    middleware = SafetyMiddleware(config, lists_manager, interactive=False)

    spider = Mock()
    spider.logger = Mock()

    request = Request(url="https://example.com/admin/delete/123", method="GET")

    result = middleware.process_request(request, spider)

    assert result is None
    assert middleware.blocked_count == 0
