from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from harmony.api.agents import AgentResult

pytestmark = pytest.mark.asyncio

HTTP_OK = 200
HTTP_UNPROCESSABLE_ENTITY = 422


@pytest.fixture
def mock_agents() -> Generator[dict[str, Any], None, None]:
    """Mock all agent execute methods."""
    with (
        patch(
            "harmony.api.agents._query_planner.QueryPlannerAgent.execute"
        ) as mock_planner,
        patch("harmony.api.agents._searcher.SearcherAgent.execute") as mock_searcher,
        patch("harmony.api.agents._critic.CriticAgent.execute") as mock_critic,
        patch(
            "harmony.api.agents._synthesizer.SynthesizerAgent.execute"
        ) as mock_synthesizer,
    ):
        mock_planner.return_value = AgentResult(
            content=json.dumps(["query 1", "query 2", "query 3"]),
            metadata={"num_variants": 3},
            confidence=1.0,
        )

        mock_searcher.return_value = AgentResult(
            content=json.dumps([
                {
                    "title": "Test Document",
                    "url": "https://example.com/test",
                    "domain": "example.com",
                    "content": "Test content",
                    "snippet": "Test snippet",
                    "score": 0.95,
                }
            ]),
            metadata={"total": 1},
            confidence=0.8,
        )

        mock_critic.return_value = AgentResult(
            content=json.dumps({
                "factual_accuracy": 0.9,
                "completeness": 0.85,
                "hallucination_risk": 0.1,
                "issues": [],
                "suggestions": [],
                "consensus_reached": True,
            }),
            metadata={"consensus_reached": True},
            confidence=0.9,
        )

        mock_synthesizer.return_value = AgentResult(
            content="This is a test answer based on the sources.",
            metadata={"num_sources": 1},
            confidence=0.9,
        )

        yield {
            "planner": mock_planner,
            "searcher": mock_searcher,
            "critic": mock_critic,
            "synthesizer": mock_synthesizer,
        }


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


async def test_agentic_search_endpoint_returns_200(
    client: AsyncClient, mock_agents: dict[str, Any]
) -> None:
    """Test Agentic search endpoint returns successful streaming response."""
    response = await client.post("/api/agentic-search", json={"query": "test query"})
    assert response.status_code == HTTP_OK
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"


async def test_agentic_search_response_structure(
    client: AsyncClient, mock_agents: dict[str, Any]
) -> None:
    """Test Agentic search returns expected streaming events."""
    response = await client.post("/api/agentic-search", json={"query": "test query"})
    assert response.status_code == HTTP_OK

    events = parse_sse_events(response.text)

    # Check for expected event types
    event_types = [e["event"] for e in events]
    assert "query_variant" in event_types
    assert "reading_page" in event_types
    assert "answer_chunk" in event_types
    assert "done" in event_types

    # Check done event structure
    done_event = next(e for e in events if e["event"] == "done")
    assert "sources" in done_event["data"]
    assert "refinement_rounds" in done_event["data"]
    assert "query_variants" in done_event["data"]


async def test_agentic_search_custom_refinement_rounds(
    client: AsyncClient, mock_agents: dict[str, Any]
) -> None:
    """Test Agentic search respects custom refinement rounds."""
    response = await client.post(
        "/api/agentic-search", json={"query": "test query", "max_refinement_rounds": 1}
    )
    assert response.status_code == HTTP_OK

    events = parse_sse_events(response.text)
    done_event = next(e for e in events if e["event"] == "done")
    assert done_event["data"]["refinement_rounds"] <= 1


async def test_agentic_search_handles_empty_query(
    client: AsyncClient, mock_agents: dict[str, Any]
) -> None:
    """Test Agentic search handles empty query with validation error."""
    response = await client.post("/api/agentic-search", json={"query": ""})
    assert response.status_code == HTTP_UNPROCESSABLE_ENTITY


async def test_agentic_search_includes_sources(
    client: AsyncClient, mock_agents: dict[str, Any]
) -> None:
    """Test Agentic search includes source documents in done event."""
    response = await client.post("/api/agentic-search", json={"query": "test query"})
    assert response.status_code == HTTP_OK

    events = parse_sse_events(response.text)
    done_event = next(e for e in events if e["event"] == "done")

    sources = done_event["data"]["sources"]
    assert len(sources) > 0

    source = sources[0]
    assert "title" in source
    assert "url" in source
    assert "domain" in source


async def test_agentic_search_includes_query_variants(
    client: AsyncClient, mock_agents: dict[str, Any]
) -> None:
    """Test Agentic search includes generated query variants."""
    response = await client.post("/api/agentic-search", json={"query": "test query"})
    assert response.status_code == HTTP_OK

    events = parse_sse_events(response.text)

    # Check query_variant events
    query_variant_events = [e for e in events if e["event"] == "query_variant"]
    assert len(query_variant_events) > 0

    # Check done event has query_variants
    done_event = next(e for e in events if e["event"] == "done")
    assert len(done_event["data"]["query_variants"]) > 0


async def test_agentic_search_streams_answer_chunks(
    client: AsyncClient, mock_agents: dict[str, Any]
) -> None:
    """Test Agentic search streams answer in chunks."""
    response = await client.post("/api/agentic-search", json={"query": "test query"})
    assert response.status_code == HTTP_OK

    events = parse_sse_events(response.text)
    answer_chunks = [e for e in events if e["event"] == "answer_chunk"]

    # Should have at least one answer chunk
    assert len(answer_chunks) > 0

    # Reconstruct answer from chunks
    full_answer = "".join(chunk["data"]["content"] for chunk in answer_chunks)
    assert len(full_answer) > 0
