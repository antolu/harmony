from __future__ import annotations

from unittest.mock import Mock

from scrapy.http import Request

from harmony.crawler.middlewares import SafetyMiddleware
from harmony.crawler.safety import SafetyConfig


class TestSafetyMiddleware:
    def test_blocks_post_request(self) -> None:
        config = SafetyConfig()
        middleware = SafetyMiddleware(config)
        spider = Mock()
        spider.logger = Mock()

        request = Request(
            url="https://example.com/api/data",
            method="POST",
        )

        result = middleware.process_request(request, spider)

        assert result is None
        assert middleware.blocked_count == 1
        spider.logger.warning.assert_called_once()

    def test_allows_get_request(self) -> None:
        config = SafetyConfig()
        middleware = SafetyMiddleware(config)
        spider = Mock()
        spider.logger = Mock()

        request = Request(
            url="https://example.com/docs/guide",
            method="GET",
        )

        result = middleware.process_request(request, spider)

        assert result is None
        assert middleware.blocked_count == 0

    def test_blocks_dangerous_url(self) -> None:
        config = SafetyConfig()
        middleware = SafetyMiddleware(config)
        spider = Mock()
        spider.logger = Mock()

        request = Request(
            url="https://example.com/admin/delete/123",
            method="GET",
        )

        result = middleware.process_request(request, spider)

        assert result is None
        assert middleware.blocked_count == 1
        spider.logger.warning.assert_called_once()

    def test_allows_safe_url(self) -> None:
        config = SafetyConfig()
        middleware = SafetyMiddleware(config)
        spider = Mock()
        spider.logger = Mock()

        request = Request(
            url="https://example.com/docs/reference",
            method="GET",
        )

        result = middleware.process_request(request, spider)

        assert result is None
        assert middleware.blocked_count == 0

    def test_dry_run_mode_blocks_all(self) -> None:
        config = SafetyConfig(dry_run=True)
        middleware = SafetyMiddleware(config)
        spider = Mock()
        spider.logger = Mock()

        request = Request(
            url="https://example.com/safe/page",
            method="GET",
        )

        result = middleware.process_request(request, spider)

        assert result is None
        spider.logger.info.assert_called_once()
        assert "[DRY RUN]" in spider.logger.info.call_args[0][0]

    def test_tracks_blocked_reasons(self) -> None:
        config = SafetyConfig()
        middleware = SafetyMiddleware(config)
        spider = Mock()
        spider.logger = Mock()

        request1 = Request(url="https://example.com/delete/1", method="GET")
        request2 = Request(url="https://example.com/delete/2", method="GET")
        request3 = Request(url="https://example.com/edit/3", method="GET")

        middleware.process_request(request1, spider)
        middleware.process_request(request2, spider)
        middleware.process_request(request3, spider)

        assert middleware.blocked_count == 3
        assert len(middleware.blocked_reasons) >= 1

    def test_spider_closed_logs_stats(self) -> None:
        config = SafetyConfig()
        middleware = SafetyMiddleware(config)
        spider = Mock()
        spider.logger = Mock()

        request = Request(url="https://example.com/delete/123", method="GET")
        middleware.process_request(request, spider)

        middleware.spider_closed(spider)

        assert spider.logger.info.called
        args = spider.logger.info.call_args_list
        assert any("[SAFETY STATS]" in str(call) for call in args)

    def test_spider_closed_no_logs_if_no_blocks(self) -> None:
        config = SafetyConfig()
        middleware = SafetyMiddleware(config)
        spider = Mock()
        spider.logger = Mock()

        middleware.spider_closed(spider)

        spider.logger.info.assert_not_called()

    def test_from_crawler(self) -> None:
        crawler = Mock()
        crawler.settings = Mock()
        crawler.settings.get = Mock(return_value=SafetyConfig())
        crawler.signals = Mock()
        crawler.signals.connect = Mock()

        middleware = SafetyMiddleware.from_crawler(crawler)

        assert isinstance(middleware, SafetyMiddleware)
        crawler.signals.connect.assert_called_once()

    def test_from_crawler_uses_default_config(self) -> None:
        crawler = Mock()
        crawler.settings = Mock()
        crawler.settings.get = Mock(return_value=None)
        crawler.signals = Mock()
        crawler.signals.connect = Mock()

        middleware = SafetyMiddleware.from_crawler(crawler)

        assert isinstance(middleware, SafetyMiddleware)
        assert isinstance(middleware.config, SafetyConfig)

    def test_blocks_delete_method(self) -> None:
        config = SafetyConfig()
        middleware = SafetyMiddleware(config)
        spider = Mock()
        spider.logger = Mock()

        request = Request(
            url="https://example.com/api/resource",
            method="DELETE",
        )

        result = middleware.process_request(request, spider)

        assert result is None
        assert middleware.blocked_count == 1

    def test_blocks_put_method(self) -> None:
        config = SafetyConfig()
        middleware = SafetyMiddleware(config)
        spider = Mock()
        spider.logger = Mock()

        request = Request(
            url="https://example.com/api/resource",
            method="PUT",
        )

        result = middleware.process_request(request, spider)

        assert result is None
        assert middleware.blocked_count == 1

    def test_allows_head_request(self) -> None:
        config = SafetyConfig()
        middleware = SafetyMiddleware(config)
        spider = Mock()
        spider.logger = Mock()

        request = Request(
            url="https://example.com/docs/page",
            method="HEAD",
        )

        result = middleware.process_request(request, spider)

        assert result is None
        assert middleware.blocked_count == 0

    def test_custom_allowed_methods(self) -> None:
        config = SafetyConfig(allowed_methods={"GET", "POST"})
        middleware = SafetyMiddleware(config)
        spider = Mock()
        spider.logger = Mock()

        request = Request(
            url="https://example.com/api/data",
            method="POST",
        )

        result = middleware.process_request(request, spider)

        assert result is None
        assert middleware.blocked_count == 0

    def test_blocks_query_param_action_delete(self) -> None:
        config = SafetyConfig()
        middleware = SafetyMiddleware(config)
        spider = Mock()
        spider.logger = Mock()

        request = Request(
            url="https://example.com/item?action=delete&id=123",
            method="GET",
        )

        result = middleware.process_request(request, spider)

        assert result is None
        assert middleware.blocked_count == 1

    def test_safe_mode_extra_strict(self) -> None:
        config = SafetyConfig(safe_mode=True)
        middleware = SafetyMiddleware(config)
        spider = Mock()
        spider.logger = Mock()

        request = Request(
            url="https://example.com/edit?id=123",
            method="GET",
        )

        result = middleware.process_request(request, spider)

        assert result is None
        assert middleware.blocked_count == 1
