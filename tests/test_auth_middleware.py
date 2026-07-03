from unittest.mock import AsyncMock, MagicMock

import pytest

from harmony.providers.web_crawler.auth._config import AuthConfig
from harmony.providers.web_crawler.auth._middleware import AuthMiddleware


@pytest.mark.asyncio
async def test_auth_middleware_process_response_split() -> None:
    """
    D-17: Verify process_response correctly dispatches to
    _handle_interactive_reauth and _handle_noninteractive_reauth.
    """
    config = AuthConfig()
    config.auto_authenticate_on_403 = True
    config.enabled = True

    registry = MagicMock()
    middleware = AuthMiddleware(config, registry)
    middleware._can_retry_auth = MagicMock(return_value=True)  # type: ignore[method-assign]
    middleware.registry.invalidate_session = MagicMock()  # type: ignore[method-assign]
    middleware._increment_auth_attempts = MagicMock()  # type: ignore[method-assign]

    request = MagicMock()
    request.url = "http://example.com/foo"
    response = MagicMock()
    spider = MagicMock()

    # 1. Test interactive dispatch
    provider_interactive = MagicMock()
    provider_interactive.is_interactive.return_value = True
    middleware._check_fast_path_bailout = AsyncMock(return_value=provider_interactive)  # type: ignore[method-assign]
    middleware._handle_interactive_busy = MagicMock(return_value=None)  # type: ignore[method-assign]
    middleware._handle_interactive_reauth = AsyncMock()  # type: ignore[method-assign]

    await middleware.process_response(request, response, spider)
    middleware._handle_interactive_reauth.assert_called_once()

    # 2. Test non-interactive dispatch
    provider_noninteractive = MagicMock()
    provider_noninteractive.is_interactive.return_value = False
    middleware._check_fast_path_bailout = AsyncMock(  # type: ignore[method-assign]
        return_value=provider_noninteractive
    )
    middleware._handle_noninteractive_reauth = AsyncMock()  # type: ignore[method-assign]

    await middleware.process_response(request, response, spider)
    middleware._handle_noninteractive_reauth.assert_called_once()
