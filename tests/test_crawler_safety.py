from __future__ import annotations

from harmony.crawler.safety import SafetyConfig, is_url_safe


class TestURLSafety:
    def test_dangerous_delete_url(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://example.com/admin/delete/123", config)
        assert not is_safe
        assert "delete" in reason.lower()

    def test_dangerous_remove_url(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://example.com/user/remove/456", config)
        assert not is_safe
        assert "remove" in reason.lower()

    def test_dangerous_edit_url(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://example.com/post/edit/789", config)
        assert not is_safe
        assert "edit" in reason.lower()

    def test_dangerous_query_param_action_delete(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://example.com/item?action=delete", config)
        assert not is_safe
        assert "query param" in reason.lower()
        assert "action" in reason.lower()

    def test_dangerous_query_param_action_remove(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://example.com/item?action=remove", config)
        assert not is_safe
        assert "query param" in reason.lower()

    def test_dangerous_query_param_submit(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://example.com/form?submit=yes", config)
        assert not is_safe
        assert "dangerous" in reason.lower()

    def test_dangerous_query_param_method_post(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://example.com/api?method=POST", config)
        assert not is_safe
        assert "query param" in reason.lower()

    def test_dangerous_logout_url(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://example.com/logout", config)
        assert not is_safe
        assert "logout" in reason.lower()

    def test_dangerous_signout_url(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://example.com/signout", config)
        assert not is_safe
        assert "signout" in reason.lower()

    def test_safe_url(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://example.com/docs/guide", config)
        assert is_safe
        assert reason == ""

    def test_safe_url_with_query(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://example.com/search?q=python", config)
        assert is_safe
        assert reason == ""

    def test_safe_url_docs(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://docs.example.com/api/reference", config)
        assert is_safe
        assert reason == ""

    def test_allow_list(self) -> None:
        config = SafetyConfig(allow_list_patterns=[r"example\.com/admin/view"])
        is_safe, _reason = is_url_safe("https://example.com/admin/view/123", config)
        assert is_safe

    def test_allow_list_bypasses_dangerous_pattern(self) -> None:
        config = SafetyConfig(allow_list_patterns=[r"example\.com/special/delete"])
        is_safe, _reason = is_url_safe(
            "https://example.com/special/delete/item", config
        )
        assert is_safe

    def test_additional_deny_patterns(self) -> None:
        config = SafetyConfig(additional_deny_patterns=[r"/private/"])
        is_safe, reason = is_url_safe("https://example.com/private/data", config)
        assert not is_safe
        assert "user deny pattern" in reason.lower()

    def test_safe_mode_blocks_id_with_delete(self) -> None:
        config = SafetyConfig(safe_mode=True)
        is_safe, reason = is_url_safe("https://example.com/delete?id=123", config)
        assert not is_safe
        assert "safe mode" in reason.lower()

    def test_safe_mode_blocks_id_with_edit(self) -> None:
        config = SafetyConfig(safe_mode=True)
        is_safe, reason = is_url_safe("https://example.com/edit?id=123", config)
        assert not is_safe
        assert "safe mode" in reason.lower()

    def test_safe_mode_blocks_id_with_remove(self) -> None:
        config = SafetyConfig(safe_mode=True)
        is_safe, reason = is_url_safe("https://example.com/remove?id=456", config)
        assert not is_safe
        assert "safe mode" in reason.lower()

    def test_safe_mode_allows_id_without_action(self) -> None:
        config = SafetyConfig(safe_mode=True)
        is_safe, _reason = is_url_safe("https://example.com/view?id=123", config)
        assert is_safe

    def test_case_insensitive_matching(self) -> None:
        config = SafetyConfig()
        is_safe, _reason = is_url_safe("https://example.com/admin/DELETE/123", config)
        assert not is_safe

    def test_dangerous_api_delete(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://api.example.com/v1/delete/user", config)
        assert not is_safe
        assert "delete" in reason.lower()

    def test_dangerous_api_update(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://api.example.com/v1/update/user", config)
        assert not is_safe
        assert "update" in reason.lower()

    def test_dangerous_confirm_url(self) -> None:
        config = SafetyConfig()
        is_safe, _reason = is_url_safe(
            "https://example.com/confirm?action=delete", config
        )
        assert not is_safe

    def test_dangerous_submit_url(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://example.com/form/submit", config)
        assert not is_safe
        assert "submit" in reason.lower()

    def test_multiple_query_params_with_dangerous(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe(
            "https://example.com/item?page=2&action=delete&sort=asc", config
        )
        assert not is_safe
        assert "query param" in reason.lower()

    def test_empty_url(self) -> None:
        config = SafetyConfig()
        is_safe, _reason = is_url_safe("", config)
        assert is_safe

    def test_url_without_path(self) -> None:
        config = SafetyConfig()
        is_safe, _reason = is_url_safe("https://example.com", config)
        assert is_safe

    def test_url_with_fragment(self) -> None:
        config = SafetyConfig()
        is_safe, _reason = is_url_safe("https://example.com/docs#section", config)
        assert is_safe

    def test_dangerous_destroy_url(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://example.com/resource/destroy", config)
        assert not is_safe
        assert "destroy" in reason.lower()

    def test_dangerous_purge_url(self) -> None:
        config = SafetyConfig()
        is_safe, reason = is_url_safe("https://example.com/cache/purge", config)
        assert not is_safe
        assert "purge" in reason.lower()


class TestHTTPMethods:
    def test_default_allowed_methods(self) -> None:
        config = SafetyConfig()
        assert "GET" in config.allowed_methods
        assert "HEAD" in config.allowed_methods
        assert "POST" not in config.allowed_methods

    def test_custom_allowed_methods(self) -> None:
        config = SafetyConfig(allowed_methods={"GET", "POST"})
        assert "GET" in config.allowed_methods
        assert "POST" in config.allowed_methods
        assert "DELETE" not in config.allowed_methods


class TestSafetyConfigDefaults:
    def test_default_safe_mode_is_false(self) -> None:
        config = SafetyConfig()
        assert config.safe_mode is False

    def test_default_dry_run_is_false(self) -> None:
        config = SafetyConfig()
        assert config.dry_run is False

    def test_default_allow_list_is_empty(self) -> None:
        config = SafetyConfig()
        assert config.allow_list_patterns == []

    def test_default_additional_deny_patterns_is_empty(self) -> None:
        config = SafetyConfig()
        assert config.additional_deny_patterns == []

    def test_dangerous_patterns_not_empty(self) -> None:
        config = SafetyConfig()
        assert len(config.dangerous_url_patterns) > 0

    def test_dangerous_query_params_not_empty(self) -> None:
        config = SafetyConfig()
        assert len(config.dangerous_query_params) > 0
