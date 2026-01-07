from __future__ import annotations

import httpx
import pytest

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

PIPELINES_URL = "http://localhost:9099"
HARMONY_API_URL = "http://localhost:8000"
HTTP_OK = 200


@pytest.mark.elasticsearch
async def test_harmony_api_search_endpoint() -> None:
    """Test harmony-api search endpoint returns results."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{HARMONY_API_URL}/search",
            params={"q": "CERN"},
            timeout=10.0,
        )
        assert response.status_code == HTTP_OK
        data = response.json()
        assert "total" in data
        assert "hits" in data
        assert data["total"] > 0
        assert len(data["hits"]) > 0


@pytest.mark.elasticsearch
async def test_direct_search_pipeline_execution() -> None:
    """Test Direct Search pipeline executes and returns results."""
    async with httpx.AsyncClient() as client:
        # Simulate OpenWebUI request to pipelines service
        request_body = {
            "model": "harmony_direct_search.harmony_direct_search",
            "messages": [{"role": "user", "content": "CERN onboarding"}],
            "stream": False,
        }

        response = await client.post(
            f"{PIPELINES_URL}/v1/chat/completions",
            json=request_body,
            timeout=30.0,
        )

        assert response.status_code == HTTP_OK
        data = response.json()

        # Check OpenAI-compatible response structure
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
        assert "content" in data["choices"][0]["message"]

        # Check that content is not empty
        content = data["choices"][0]["message"]["content"]
        assert len(content) > 0
        assert "results" in content.lower() or "found" in content.lower()


@pytest.mark.llm
@pytest.mark.elasticsearch
async def test_ai_search_pipeline_execution() -> None:
    """Test AI Search pipeline executes and returns results."""
    pytest.skip("AI Search pipeline test - needs to be updated for new API")
    async with httpx.AsyncClient() as client:
        request_body = {
            "model": "harmony_search.harmony_ai_search",
            "messages": [{"role": "user", "content": "What is CERN?"}],
            "stream": False,
        }

        response = await client.post(
            f"{PIPELINES_URL}/v1/chat/completions",
            json=request_body,
            timeout=60.0,
        )

        assert response.status_code == HTTP_OK
        data = response.json()

        assert "choices" in data
        assert len(data["choices"]) > 0
        content = data["choices"][0]["message"]["content"]
        assert len(content) > 0


@pytest.mark.elasticsearch
async def test_direct_search_returns_formatted_results() -> None:
    """Test Direct Search returns properly formatted search results."""
    async with httpx.AsyncClient() as client:
        request_body = {
            "model": "harmony_direct_search.harmony_direct_search",
            "messages": [{"role": "user", "content": "CERN"}],
            "stream": False,
        }

        response = await client.post(
            f"{PIPELINES_URL}/v1/chat/completions",
            json=request_body,
            timeout=30.0,
        )

        assert response.status_code == HTTP_OK
        data = response.json()
        content = data["choices"][0]["message"]["content"]

        # Check for new Google-like formatting
        assert "###" in content  # Markdown headers
        assert "[" in content
        assert "](" in content
        assert "**" in content  # Bold formatting (domain and highlights)
        assert "---" in content  # Result separators
        assert "https://" in content  # Actual URLs
        # Should NOT have "Score:" anymore
        assert "Score:" not in content


@pytest.mark.elasticsearch
async def test_direct_search_handles_no_results() -> None:
    """Test Direct Search handles queries with no results gracefully."""
    async with httpx.AsyncClient() as client:
        request_body = {
            "model": "harmony_direct_search.harmony_direct_search",
            "messages": [{"role": "user", "content": "xyzabc123nonexistentquery456"}],
            "stream": False,
        }

        response = await client.post(
            f"{PIPELINES_URL}/v1/chat/completions",
            json=request_body,
            timeout=30.0,
        )

        assert response.status_code == HTTP_OK
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        assert "no results" in content.lower() or "not found" in content.lower()


@pytest.mark.skip(reason="External /v1/models endpoint requires authentication")
async def test_pipelines_models_endpoint() -> None:
    """Test pipelines models endpoint returns available pipelines."""
    min_expected_pipelines = 2  # Direct Search and AI Search
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{PIPELINES_URL}/v1/models",
            timeout=10.0,
        )

        assert response.status_code == HTTP_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) >= min_expected_pipelines

        # Check for our pipelines
        model_ids = [model["id"] for model in data["data"]]
        assert "harmony_direct_search.harmony_direct_search" in model_ids
        assert "harmony_search.harmony_ai_search" in model_ids
