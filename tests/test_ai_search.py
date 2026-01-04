from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_ai_search_endpoint_returns_200(
    client: AsyncClient, mock_llm: MagicMock
) -> None:
    """AI search endpoint responds without crashing."""
    response = await client.post("/ai-search", json={"query": "test"})
    assert response.status_code == 200


async def test_ai_search_returns_expected_structure(
    client: AsyncClient, mock_llm: MagicMock
) -> None:
    """AI search response has expected fields."""
    response = await client.post("/ai-search", json={"query": "test"})
    data = response.json()

    assert "answer" in data
    assert "sources" in data
    assert "conversation_id" in data
    assert isinstance(data["sources"], list)
    assert isinstance(data["conversation_id"], str)


async def test_ai_search_creates_new_conversation(
    client: AsyncClient, mock_llm: MagicMock
) -> None:
    """AI search creates new conversation if not provided."""
    response = await client.post("/ai-search", json={"query": "test"})
    data = response.json()

    assert data["conversation_id"] is not None
    assert len(data["conversation_id"]) > 0


async def test_ai_search_uses_existing_conversation(
    client: AsyncClient, mock_llm: MagicMock
) -> None:
    """AI search uses provided conversation_id."""
    first_response = await client.post("/ai-search", json={"query": "first message"})
    first_data = first_response.json()
    conv_id = first_data["conversation_id"]

    second_response = await client.post(
        "/ai-search", json={"query": "second message", "conversation_id": conv_id}
    )
    second_data = second_response.json()

    assert second_data["conversation_id"] == conv_id


async def test_ai_search_handles_empty_query(
    client: AsyncClient, mock_llm: MagicMock
) -> None:
    """AI search handles empty query gracefully."""
    response = await client.post("/ai-search", json={"query": ""})
    assert response.status_code == 200
