from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from harmony.api.agents.base import AgentResult

pytestmark = pytest.mark.asyncio

HTTP_OK = 200
HTTP_UNPROCESSABLE_ENTITY = 422


@pytest.fixture
def mock_agents() -> Generator[dict[str, Any], None, None]:
    """Mock all agent execute methods."""
    with (
        patch(
            "harmony.api.agents.query_planner.QueryPlannerAgent.execute"
        ) as mock_planner,
        patch("harmony.api.agents.searcher.SearcherAgent.execute") as mock_searcher,
        patch("harmony.api.agents.critic.CriticAgent.execute") as mock_critic,
        patch(
            "harmony.api.agents.synthesizer.SynthesizerAgent.execute"
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


async def test_agentic_search_endpoint_returns_200(
    client: AsyncClient, mock_agents: dict[str, Any]
) -> None:
    """Test Agentic search endpoint returns successful response."""
    response = await client.post("/agentic-search", json={"query": "test query"})
    assert response.status_code == HTTP_OK


async def test_agentic_search_response_structure(
    client: AsyncClient, mock_agents: dict[str, Any]
) -> None:
    """Test Agentic search returns expected response structure."""
    response = await client.post("/agentic-search", json={"query": "test query"})
    assert response.status_code == HTTP_OK

    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert "refinement_rounds" in data
    assert "query_variants" in data

    assert isinstance(data["answer"], str)
    assert isinstance(data["sources"], list)
    assert isinstance(data["refinement_rounds"], int)
    assert isinstance(data["query_variants"], list)


async def test_agentic_search_custom_refinement_rounds(
    client: AsyncClient, mock_agents: dict[str, Any]
) -> None:
    """Test Agentic search respects custom refinement rounds."""
    response = await client.post(
        "/agentic-search", json={"query": "test query", "max_refinement_rounds": 1}
    )
    assert response.status_code == HTTP_OK

    data = response.json()
    assert data["refinement_rounds"] <= 1


async def test_agentic_search_handles_empty_query(
    client: AsyncClient, mock_agents: dict[str, Any]
) -> None:
    """Test Agentic search handles empty query with validation error."""
    response = await client.post("/agentic-search", json={"query": ""})
    assert response.status_code == HTTP_UNPROCESSABLE_ENTITY


async def test_agentic_search_includes_sources(
    client: AsyncClient, mock_agents: dict[str, Any]
) -> None:
    """Test Agentic search includes source documents in response."""
    response = await client.post("/agentic-search", json={"query": "test query"})
    assert response.status_code == HTTP_OK

    data = response.json()
    assert len(data["sources"]) > 0

    source = data["sources"][0]
    assert "title" in source
    assert "url" in source
    assert "domain" in source


async def test_agentic_search_includes_query_variants(
    client: AsyncClient, mock_agents: dict[str, Any]
) -> None:
    """Test Agentic search includes generated query variants."""
    response = await client.post("/agentic-search", json={"query": "test query"})
    assert response.status_code == HTTP_OK

    data = response.json()
    assert len(data["query_variants"]) > 0
