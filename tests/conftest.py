from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from harmony.api.main import app
from harmony.api.services.conversation import ConversationService


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def conversation_service() -> ConversationService:
    return ConversationService()


@pytest.fixture
def mock_llm(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock LiteLLM completion to avoid real API calls."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Mocked response"
    mock_response.choices[0].message.tool_calls = None

    def mock_completion(*args: object, **kwargs: object) -> MagicMock:
        return mock_response

    monkeypatch.setattr("harmony.api.services.llm.completion", mock_completion)
    return mock_response
