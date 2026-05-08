from __future__ import annotations

from scrapy.http import HtmlResponse
from scrapy.linkextractors import LinkExtractor

from harmony.crawler.safety import (
    SafetyConfig,
    _check_allowlist,  # noqa: PLC2701
    _check_denylist,  # noqa: PLC2701
    is_url_safe,
)


# Converted from TestURLSafety class
def test_dangerous_delete_url() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://example.com/admin/delete/123", config)
    assert not is_safe
    assert "delete" in reason.lower()


def test_dangerous_remove_url() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://example.com/user/remove/456", config)
    assert not is_safe
    assert "remove" in reason.lower()


def test_dangerous_edit_url() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://example.com/post/edit/789", config)
    assert not is_safe
    assert "edit" in reason.lower()


def test_dangerous_query_param_action_delete() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://example.com/item?action=delete", config)
    assert not is_safe
    assert "dangerous pattern" in reason.lower()


def test_dangerous_query_param_action_remove() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://example.com/item?action=remove", config)
    assert not is_safe
    assert "dangerous pattern" in reason.lower()


def test_dangerous_query_param_submit() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://example.com/form?submit=yes", config)
    assert not is_safe
    assert "dangerous" in reason.lower()


def test_dangerous_query_param_method_post() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://example.com/api?method=POST", config)
    assert not is_safe
    assert "query param" in reason.lower()


def test_dangerous_logout_url() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://example.com/logout", config)
    assert not is_safe
    assert "logout" in reason.lower()


def test_dangerous_signout_url() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://example.com/signout", config)
    assert not is_safe
    assert "signout" in reason.lower()


def test_safe_url() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://example.com/docs/guide", config)
    assert is_safe
    assert not reason


def test_safe_url_with_query() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://example.com/search?q=python", config)
    assert is_safe
    assert not reason


def test_safe_url_docs() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://docs.example.com/api/reference", config)
    assert is_safe
    assert not reason


def test_allow_list() -> None:
    config = SafetyConfig(allow_list_patterns=[r"example\.com/admin/view"])
    is_safe, _reason = is_url_safe("https://example.com/admin/view/123", config)
    assert is_safe


def test_allow_list_bypasses_dangerous_pattern() -> None:
    config = SafetyConfig(allow_list_patterns=[r"example\.com/special/delete"])
    is_safe, _reason = is_url_safe("https://example.com/special/delete/item", config)
    assert is_safe


def test_additional_deny_patterns() -> None:
    config = SafetyConfig(additional_deny_patterns=[r"/private/"])
    is_safe, reason = is_url_safe("https://example.com/private/data", config)
    assert not is_safe
    assert "user deny pattern" in reason.lower()


def test_safe_mode_blocks_id_with_delete() -> None:
    config = SafetyConfig(safe_mode=True)
    is_safe, reason = is_url_safe("https://example.com/delete?id=123", config)
    assert not is_safe
    assert "safe mode" in reason.lower()


def test_safe_mode_blocks_id_with_edit() -> None:
    config = SafetyConfig(safe_mode=True)
    is_safe, reason = is_url_safe("https://example.com/edit?id=123", config)
    assert not is_safe
    assert "safe mode" in reason.lower()


def test_safe_mode_blocks_id_with_remove() -> None:
    config = SafetyConfig(safe_mode=True)
    is_safe, reason = is_url_safe("https://example.com/remove?id=456", config)
    assert not is_safe
    assert "safe mode" in reason.lower()


def test_safe_mode_allows_id_without_action() -> None:
    config = SafetyConfig(safe_mode=True)
    is_safe, _reason = is_url_safe("https://example.com/view?id=123", config)
    assert is_safe


def test_case_insensitive_matching() -> None:
    config = SafetyConfig()
    is_safe, _reason = is_url_safe("https://example.com/admin/DELETE/123", config)
    assert not is_safe


def test_dangerous_api_delete() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://api.example.com/v1/delete/user", config)
    assert not is_safe
    assert "delete" in reason.lower()


def test_dangerous_api_update() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://api.example.com/v1/update/user", config)
    assert not is_safe
    assert "update" in reason.lower()


def test_dangerous_confirm_url() -> None:
    config = SafetyConfig()
    is_safe, _reason = is_url_safe("https://example.com/confirm?action=delete", config)
    assert not is_safe


def test_dangerous_submit_url() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://example.com/form/submit", config)
    assert not is_safe
    assert "submit" in reason.lower()


def test_multiple_query_params_with_dangerous() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe(
        "https://example.com/item?page=2&action=delete&sort=asc", config
    )
    assert not is_safe
    assert "query param" in reason.lower()


def test_empty_url() -> None:
    config = SafetyConfig()
    is_safe, _reason = is_url_safe("", config)
    assert is_safe


def test_url_without_path() -> None:
    config = SafetyConfig()
    is_safe, _reason = is_url_safe("https://example.com", config)
    assert is_safe


def test_url_with_fragment() -> None:
    config = SafetyConfig()
    is_safe, _reason = is_url_safe("https://example.com/docs#section", config)
    assert is_safe


def test_dangerous_destroy_url() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://example.com/resource/destroy", config)
    assert not is_safe
    assert "destroy" in reason.lower()


def test_dangerous_purge_url() -> None:
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://example.com/cache/purge", config)
    assert not is_safe
    assert "purge" in reason.lower()


# Converted from TestHTTPMethods class
def test_default_allowed_methods() -> None:
    config = SafetyConfig()
    assert "GET" in config.allowed_methods
    assert "HEAD" in config.allowed_methods
    assert "POST" not in config.allowed_methods


def test_custom_allowed_methods() -> None:
    config = SafetyConfig(allowed_methods={"GET", "POST"})
    assert "GET" in config.allowed_methods
    assert "POST" in config.allowed_methods
    assert "DELETE" not in config.allowed_methods


# Converted from TestSafetyConfigDefaults class
def test_default_safe_mode_is_false() -> None:
    config = SafetyConfig()
    assert config.safe_mode is False


def test_default_dry_run_is_false() -> None:
    config = SafetyConfig()
    assert config.dry_run is False


def test_default_allow_list_is_empty() -> None:
    config = SafetyConfig()
    assert config.allow_list_patterns == []


def test_default_additional_deny_patterns_is_empty() -> None:
    config = SafetyConfig()
    assert config.additional_deny_patterns == []


def test_dangerous_patterns_not_empty() -> None:
    config = SafetyConfig()
    assert len(config.dangerous_url_patterns) > 0


def test_dangerous_query_params_not_empty() -> None:
    config = SafetyConfig()
    assert len(config.dangerous_query_params) > 0


# False positive prevention tests
def test_allows_updatesource_url() -> None:
    """Ensure /updatesource/ is not blocked by /update/ pattern."""
    config = SafetyConfig()
    is_safe, _ = is_url_safe("https://example.com/docs/updatesource/index.html", config)
    assert is_safe


def test_allows_updateguide_url() -> None:
    config = SafetyConfig()
    is_safe, _ = is_url_safe("https://example.com/docs/updateguide.html", config)
    assert is_safe


def test_allows_editable_url() -> None:
    config = SafetyConfig()
    is_safe, _ = is_url_safe("https://example.com/api/editable/config", config)
    assert is_safe


def test_allows_editor_url() -> None:
    config = SafetyConfig()
    is_safe, _ = is_url_safe("https://example.com/tools/editor/", config)
    assert is_safe


def test_allows_changelog_url() -> None:
    config = SafetyConfig()
    is_safe, _ = is_url_safe("https://example.com/docs/changelog", config)
    assert is_safe


def test_allows_changeset_url() -> None:
    config = SafetyConfig()
    is_safe, _ = is_url_safe("https://example.com/repo/changeset/123", config)
    assert is_safe


# True positive validation (ensure still blocking)
def test_still_blocks_exact_delete() -> None:
    config = SafetyConfig()
    urls = [
        "https://example.com/delete/123",
        "https://example.com/admin/delete",
        "https://example.com/delete",
    ]
    for url in urls:
        is_safe, _ = is_url_safe(url, config)
        assert not is_safe, f"Should block: {url}"


def test_still_blocks_exact_update() -> None:
    config = SafetyConfig()
    urls = [
        "https://example.com/update/user/123",
        "https://example.com/api/update",
        "https://example.com/admin/update/",
    ]
    for url in urls:
        is_safe, _ = is_url_safe(url, config)
        assert not is_safe, f"Should block: {url}"


# Safe mode tests
def test_safe_mode_allows_updatesource_with_id() -> None:
    config = SafetyConfig(safe_mode=True)
    is_safe, _ = is_url_safe("https://example.com/updatesource?id=123", config)
    assert is_safe


def test_safe_mode_still_blocks_delete_with_id() -> None:
    config = SafetyConfig(safe_mode=True)
    is_safe, _ = is_url_safe("https://example.com/delete?id=123", config)
    assert not is_safe


# Real-world case from .harmony-safety-lists.json
def test_real_world_updatesource_html() -> None:
    config = SafetyConfig()
    url = "https://acc-py.web.cern.ch/gitlab/acc-co/pyui/accwidgets/docs/stable/widgets/graphs/api/model/datasrc/updatesource.html"
    is_safe, _ = is_url_safe(url, config)
    assert is_safe


# LinkExtractor integration tests
def test_linkextractor_blocks_dangerous_urls() -> None:
    """Test that LinkExtractor blocks URLs at crawl-time."""
    config = SafetyConfig()
    le = LinkExtractor(deny=tuple(config.dangerous_url_patterns))

    html = """
    <html><body>
        <a href="/docs/guide">Safe link</a>
        <a href="/admin/delete/123">Dangerous link</a>
        <a href="/edit/user">Edit link</a>
        <a href="/updatesource/index.html">Updatesource</a>
    </body></html>
    """

    response = HtmlResponse(
        url="https://example.com",
        body=html.encode("utf-8"),
        encoding="utf-8",
    )

    links = le.extract_links(response)
    extracted_urls = [link.url for link in links]

    assert "https://example.com/docs/guide" in extracted_urls
    assert "https://example.com/updatesource/index.html" in extracted_urls
    assert "https://example.com/admin/delete/123" not in extracted_urls
    assert "https://example.com/edit/user" not in extracted_urls


def test_linkextractor_allows_safe_urls() -> None:
    """Test that LinkExtractor allows legitimate URLs."""
    config = SafetyConfig()
    le = LinkExtractor(deny=tuple(config.dangerous_url_patterns))

    html = """
    <html><body>
        <a href="/docs/changelog">Changelog</a>
        <a href="/tools/editor/settings">Editor settings</a>
        <a href="/api/editable/config">Editable config</a>
        <a href="/guides/updateguide.html">Update guide</a>
    </body></html>
    """

    response = HtmlResponse(
        url="https://example.com",
        body=html.encode("utf-8"),
        encoding="utf-8",
    )

    links = le.extract_links(response)
    extracted_urls = [link.url for link in links]

    expected_urls = [
        "https://example.com/docs/changelog",
        "https://example.com/tools/editor/settings",
        "https://example.com/api/editable/config",
        "https://example.com/guides/updateguide.html",
    ]
    assert len(extracted_urls) == len(expected_urls)
    for url in expected_urls:
        assert url in extracted_urls


# Pattern consistency test
def test_safety_patterns_cover_linkextractor_needs() -> None:
    """Ensure SafetyConfig has all necessary patterns for LinkExtractor."""
    config = SafetyConfig()

    # Critical patterns that must exist
    required_patterns = [
        "delete",
        "remove",
        "edit",
        "update",
        "submit",
        "logout",
    ]

    patterns_str = "|".join(config.dangerous_url_patterns)
    for required in required_patterns:
        assert required in patterns_str, f"Missing pattern for: {required}"


def test_dangerous_patterns_have_boundaries() -> None:
    """Ensure all path-based patterns use proper boundaries."""
    config = SafetyConfig()

    path_action_patterns = [
        p
        for p in config.dangerous_url_patterns
        if not p.startswith("[?&]")
        and not p.startswith(r"\?")
        and r"\." not in p  # Exclude domain patterns like auth\.cern\.ch
        and "javascript:" not in p
    ]

    for pattern in path_action_patterns:
        # Pattern should have boundaries unless it's an admin/api path or has $ anchor
        if "/admin/" not in pattern and "/api/" not in pattern:
            check_p = pattern[4:] if pattern.startswith("(?i)") else pattern
            has_start_boundary = check_p.startswith(r"(?:^|/)")
            has_end_boundary = r"(?:/|$)" in pattern or pattern.endswith("$")
            assert has_start_boundary or has_end_boundary, (
                f"Pattern lacks proper boundaries: {pattern}"
            )


def test_recursive_path_two_repetitions_allowed() -> None:
    """Two repetitions (e.g., /foo/foo/) should be allowed."""
    config = SafetyConfig()
    is_safe, reason = is_url_safe(
        "https://example.com/examples-project/examples-project/", config
    )
    assert is_safe, f"Two repetitions should be allowed, but got: {reason}"


def test_recursive_path_three_repetitions_blocked() -> None:
    """Three repetitions (e.g., /foo/foo/foo/) should be blocked."""
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://example.com/foo/foo/foo/", config)
    assert not is_safe
    assert "dangerous pattern" in reason.lower()


def test_recursive_path_four_repetitions_blocked() -> None:
    """Four repetitions (e.g., /bar/bar/bar/bar/) should be blocked."""
    config = SafetyConfig()
    is_safe, reason = is_url_safe("https://example.com/bar/bar/bar/bar/", config)
    assert not is_safe
    assert "dangerous pattern" in reason.lower()


# Tests for _check_allowlist
def test_check_allowlist_matches() -> None:
    """URL on allowlist should return (True, '')."""
    config = SafetyConfig(allow_list_patterns=[r"example\.com/admin/view"])
    matched, reason = _check_allowlist("https://example.com/admin/view/123", config)
    assert matched
    assert not reason


def test_check_allowlist_no_match() -> None:
    """URL not on allowlist should return (False, '')."""
    config = SafetyConfig(allow_list_patterns=[r"example\.com/admin/view"])
    matched, reason = _check_allowlist("https://example.com/docs/guide", config)
    assert not matched
    assert not reason


def test_check_allowlist_empty_patterns() -> None:
    """Empty allowlist should return (False, '') for any URL."""
    config = SafetyConfig(allow_list_patterns=[])
    matched, reason = _check_allowlist("https://example.com/anything", config)
    assert not matched
    assert not reason


# Tests for _check_denylist
def test_check_denylist_blocks_dangerous() -> None:
    """URL matching dangerous pattern should return (True, reason)."""
    config = SafetyConfig()
    matched, reason = _check_denylist("https://example.com/admin/delete/123", config)
    assert matched
    assert "dangerous pattern" in reason.lower()


def test_check_denylist_blocks_user_deny() -> None:
    """URL matching additional deny pattern should return (True, reason)."""
    config = SafetyConfig(additional_deny_patterns=[r"/private/"])
    matched, reason = _check_denylist("https://example.com/private/data", config)
    assert matched
    assert "user deny pattern" in reason.lower()


def test_check_denylist_no_match() -> None:
    """Safe URL should return (False, '')."""
    config = SafetyConfig()
    matched, reason = _check_denylist("https://example.com/docs/guide", config)
    assert not matched
    assert not reason


def test_check_denylist_dangerous_takes_precedence() -> None:
    """Dangerous pattern check should run before user deny patterns."""
    config = SafetyConfig(additional_deny_patterns=[r"guide"])
    matched, reason = _check_denylist("https://example.com/admin/delete", config)
    assert matched
    assert "dangerous pattern" in reason.lower()
