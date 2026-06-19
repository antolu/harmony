from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from scrapy.exceptions import IgnoreRequest

from harmony.providers.web_crawler.auth.config import AuthConfig
from harmony.providers.web_crawler.auth.middleware import AuthMiddleware
from harmony.providers.web_crawler.auth.session import AuthSession


def _make_request(url: str = "https://example.com/page") -> MagicMock:
    request = MagicMock()
    request.url = url
    replaced = MagicMock()
    request.replace.return_value = replaced
    return request


def _make_response(status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.headers = {}
    return response


def _make_provider(
    *, interactive: bool = False, auth_required: bool = False
) -> MagicMock:
    provider = MagicMock()
    provider.is_interactive.return_value = interactive
    provider.is_auth_required.return_value = auth_required
    provider.is_auth_required_async = AsyncMock(return_value=False)
    provider.authenticate = AsyncMock(
        return_value=AuthSession(
            provider_type="basic",
            subdomain="example.com",
            domain_pattern="example\\.com",
            created_at=datetime.now(UTC),
        )
    )
    return provider


def _make_middleware(provider: MagicMock | None) -> tuple[AuthMiddleware, MagicMock]:
    config = AuthConfig()
    registry = MagicMock()
    registry.get_provider_for_domain.return_value = provider
    middleware = AuthMiddleware(config, registry)
    middleware._crawler = MagicMock()
    return middleware, registry


@pytest.mark.asyncio
async def test_process_response_fast_path_no_provider_returns_response_unchanged() -> (
    None
):
    middleware, _registry = _make_middleware(provider=None)
    request = _make_request()
    response = _make_response(status=200)

    result = await middleware.process_response(request, response, MagicMock())

    assert result is response


@pytest.mark.asyncio
async def test_process_response_fast_path_not_auth_required_returns_response() -> None:
    provider = _make_provider(interactive=False, auth_required=False)
    middleware, _registry = _make_middleware(provider=provider)
    request = _make_request()
    response = _make_response(status=200)

    result = await middleware.process_response(request, response, MagicMock())

    assert result is response
    provider.authenticate.assert_not_called()


@pytest.mark.asyncio
async def test_process_response_disabled_config_returns_response_unchanged() -> None:
    provider = _make_provider(interactive=False, auth_required=True)
    middleware, _registry = _make_middleware(provider=provider)
    middleware.config.enabled = False
    request = _make_request()
    response = _make_response(status=403)

    result = await middleware.process_response(request, response, MagicMock())

    assert result is response
    provider.authenticate.assert_not_called()


@pytest.mark.asyncio
async def test_process_response_robots_txt_returns_response_unchanged() -> None:
    provider = _make_provider(interactive=False, auth_required=True)
    middleware, _registry = _make_middleware(provider=provider)
    request = _make_request(url="https://example.com/robots.txt")
    response = _make_response(status=403)

    result = await middleware.process_response(request, response, MagicMock())

    assert result is response
    provider.authenticate.assert_not_called()


@pytest.mark.asyncio
async def test_process_response_interactive_auto_authenticate_disabled_logs_and_returns() -> (
    None
):
    provider = _make_provider(interactive=True, auth_required=True)
    middleware, _registry = _make_middleware(provider=provider)
    middleware.config.auto_authenticate_on_403 = False
    request = _make_request()
    response = _make_response(status=403)

    result = await middleware.process_response(request, response, MagicMock())

    assert result is response
    provider.authenticate.assert_not_called()


@pytest.mark.asyncio
async def test_process_response_interactive_happy_path_authenticates_and_retries() -> (
    None
):
    provider = _make_provider(interactive=True, auth_required=True)
    middleware, registry = _make_middleware(provider=provider)

    request = _make_request()
    response = _make_response(status=403)

    result = await middleware.process_response(request, response, MagicMock())

    provider.authenticate.assert_awaited_once()
    registry.store_session.assert_called_once()
    request.replace.assert_called_once_with(dont_filter=True)
    assert result is request.replace.return_value


@pytest.mark.asyncio
async def test_process_response_interactive_busy_provider_reschedules_without_auth() -> (
    None
):
    provider = _make_provider(interactive=True, auth_required=True)
    middleware, registry = _make_middleware(provider=provider)
    middleware._pending_auth.add("other.example.com")
    registry.get_provider_for_domain.return_value = provider

    request = _make_request()
    response = _make_response(status=403)

    result = await middleware.process_response(request, response, MagicMock())

    provider.authenticate.assert_not_called()
    request.replace.assert_called_once_with(dont_filter=True)
    assert result is request.replace.return_value


@pytest.mark.asyncio
async def test_process_response_noninteractive_authenticates_and_retries() -> None:
    provider = _make_provider(interactive=False, auth_required=True)
    middleware, registry = _make_middleware(provider=provider)

    request = _make_request()
    response = _make_response(status=403)

    result = await middleware.process_response(request, response, MagicMock())

    provider.authenticate.assert_awaited_once()
    registry.store_session.assert_called_once()
    request.replace.assert_called_once_with(dont_filter=True)
    assert result is request.replace.return_value


@pytest.mark.asyncio
async def test_process_response_noninteractive_authenticate_exception_still_retries() -> (
    None
):
    provider = _make_provider(interactive=False, auth_required=True)
    provider.authenticate = AsyncMock(side_effect=ValueError("boom"))
    middleware, registry = _make_middleware(provider=provider)

    request = _make_request()
    response = _make_response(status=403)

    result = await middleware.process_response(request, response, MagicMock())

    provider.authenticate.assert_awaited_once()
    registry.store_session.assert_not_called()
    request.replace.assert_called_once_with(dont_filter=True)
    assert result is request.replace.return_value


@pytest.mark.asyncio
async def test_process_response_retry_limit_exceeded_raises_before_any_helper() -> None:
    provider = _make_provider(interactive=False, auth_required=True)
    middleware, registry = _make_middleware(provider=provider)
    request = _make_request()
    response = _make_response(status=403)

    middleware._auth_attempts[request.url] = middleware.config.max_auth_retries

    with pytest.raises(IgnoreRequest):
        await middleware.process_response(request, response, MagicMock())

    provider.authenticate.assert_not_called()
    registry.invalidate_session.assert_not_called()
