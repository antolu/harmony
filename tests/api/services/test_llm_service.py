from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from harmony.api.services import LLMService


def test_llm_service_initializes() -> None:
    mock_config = AsyncMock()
    mock_config.get = AsyncMock(return_value="false")
    service = LLMService(service_config=mock_config, model_settings_store=AsyncMock())
    assert service is not None


@pytest.mark.asyncio
async def test_llm_complete_with_mock(mock_llm: MagicMock) -> None:
    mock_config = AsyncMock()
    mock_config.get = AsyncMock(return_value="false")
    service = LLMService(service_config=mock_config, model_settings_store=AsyncMock())
    messages = [{"role": "user", "content": "hi"}]
    response = await service.complete(messages=messages)

    assert response is not None
    assert response.choices[0].message.content == "Mocked response"


@pytest.mark.asyncio
async def test_llm_complete_with_tools(mock_llm: MagicMock) -> None:
    mock_config = AsyncMock()
    mock_config.get = AsyncMock(return_value="false")
    service = LLMService(service_config=mock_config, model_settings_store=AsyncMock())
    messages = [{"role": "user", "content": "search for something"}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    response = await service.complete_with_tools(messages=messages, tools=tools)

    assert response is not None
    assert response.choices[0].message.content == "Mocked response"


@pytest.mark.asyncio
async def test_llm_service_handles_custom_model(mock_llm: MagicMock) -> None:
    mock_config = AsyncMock()
    mock_config.get = AsyncMock(return_value="false")
    service = LLMService(service_config=mock_config, model_settings_store=AsyncMock())
    messages = [{"role": "user", "content": "test"}]
    response = await service.complete(
        messages=messages, model="gemini/gemini-3-flash-preview"
    )
    assert response is not None
