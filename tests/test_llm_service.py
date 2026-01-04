from __future__ import annotations

from unittest.mock import MagicMock

from harmony.api.services.llm import LLMService, llm_service


def test_llm_service_initializes() -> None:
    """LLM service can be instantiated."""
    service = LLMService()
    assert service is not None


def test_llm_complete_with_mock(mock_llm: MagicMock) -> None:
    """LLM complete works with mocked response."""
    messages = [{"role": "user", "content": "hi"}]
    response = llm_service.complete(messages=messages)

    assert response is not None
    assert response.choices[0].message.content == "Mocked response"


def test_llm_complete_with_tools(mock_llm: MagicMock) -> None:
    """LLM complete_with_tools works with mocked response."""
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

    response = llm_service.complete_with_tools(messages=messages, tools=tools)

    assert response is not None
    assert response.choices[0].message.content == "Mocked response"


def test_llm_service_handles_custom_model(mock_llm: MagicMock) -> None:
    """LLM service accepts custom model parameter."""
    messages = [{"role": "user", "content": "test"}]
    response = llm_service.complete(
        messages=messages, model="gemini/gemini-3-flash-preview"
    )

    assert response is not None
