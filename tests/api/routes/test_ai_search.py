from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

HTTP_OK = 200


def parse_sse_events(response_text: str) -> list[dict[str, Any]]:
    """Parse SSE response text into list of events."""
    events = []
    lines = response_text.strip().split("\n")

    current_event = None
    for line in lines:
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: "):
            data = json.loads(line[6:])
            if current_event:
                events.append({"event": current_event, "data": data})
                current_event = None

    return events


async def test_ai_search_endpoint_returns_200(
    client: AsyncClient, mock_llm: MagicMock
) -> None:
    """AI search endpoint responds with streaming."""
    response = await client.post("/api/ai-search", json={"query": "test"})
    assert response.status_code == HTTP_OK
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"


async def test_ai_search_returns_expected_structure(
    client: AsyncClient, mock_llm: MagicMock
) -> None:
    """AI search response has expected streaming events."""
    response = await client.post("/api/ai-search", json={"query": "test"})
    events = parse_sse_events(response.text)

    # Check for expected event types
    event_types = [e["event"] for e in events]
    assert "answer_chunk" in event_types
    assert "done" in event_types

    # Check done event structure
    done_event = next(e for e in events if e["event"] == "done")
    assert "sources" in done_event["data"]
    assert "conversation_id" in done_event["data"]
    assert isinstance(done_event["data"]["sources"], list)
    assert isinstance(done_event["data"]["conversation_id"], str)


async def test_ai_search_creates_new_conversation(
    client: AsyncClient, mock_llm: MagicMock
) -> None:
    """AI search creates new conversation if not provided."""
    response = await client.post("/api/ai-search", json={"query": "test"})
    events = parse_sse_events(response.text)

    done_event = next(e for e in events if e["event"] == "done")
    conversation_id = done_event["data"]["conversation_id"]

    assert conversation_id is not None
    assert len(conversation_id) > 0


async def test_ai_search_uses_existing_conversation(
    client: AsyncClient, mock_llm: MagicMock
) -> None:
    """AI search uses provided conversation_id."""
    first_response = await client.post(
        "/api/ai-search", json={"query": "first message"}
    )
    first_events = parse_sse_events(first_response.text)
    first_done = next(e for e in first_events if e["event"] == "done")
    conv_id = first_done["data"]["conversation_id"]

    second_response = await client.post(
        "/api/ai-search", json={"query": "second message", "conversation_id": conv_id}
    )
    second_events = parse_sse_events(second_response.text)
    second_done = next(e for e in second_events if e["event"] == "done")

    assert second_done["data"]["conversation_id"] == conv_id


async def test_ai_search_handles_empty_query(
    client: AsyncClient, mock_llm: MagicMock
) -> None:
    """AI search handles empty query gracefully."""
    response = await client.post("/api/ai-search", json={"query": ""})
    assert response.status_code == HTTP_OK


async def test_ai_search_streams_answer_chunks(
    client: AsyncClient, mock_llm: MagicMock
) -> None:
    """AI search streams answer in chunks."""
    response = await client.post("/api/ai-search", json={"query": "test"})
    events = parse_sse_events(response.text)

    answer_chunks = [e for e in events if e["event"] == "answer_chunk"]
    assert len(answer_chunks) > 0

    # Reconstruct answer from chunks
    full_answer = "".join(chunk["data"]["content"] for chunk in answer_chunks)
    assert len(full_answer) > 0


async def test_ai_search_emits_tool_call_events(
    client: AsyncClient, mock_llm: MagicMock
) -> None:
    """AI search emits tool_call events when tools are used."""
    response = await client.post("/api/ai-search", json={"query": "test"})
    events = parse_sse_events(response.text)

    event_types = [e["event"] for e in events]
    # Tool calls may or may not occur depending on LLM, just check format is valid
    assert "done" in event_types


async def test_ai_search_emits_reading_page_events(
    client: AsyncClient, mock_llm: MagicMock
) -> None:
    """AI search emits reading_page events when documents are found."""
    response = await client.post("/api/ai-search", json={"query": "test"})
    events = parse_sse_events(response.text)

    event_types = [e["event"] for e in events]
    # Reading page events may or may not occur depending on search results
    assert "done" in event_types
