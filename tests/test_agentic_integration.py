from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.asyncio

HARMONY_API_URL = "http://localhost:8000"
PIPELINES_URL = "http://localhost:9099"
HTTP_OK = 200


@pytest.mark.integration
async def test_foa_search_end_to_end() -> None:
    """Full FoA search with real ES and LLM."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{HARMONY_API_URL}/foa-search",
            json={"query": "What is CERN?"},
            timeout=120.0,
        )
        assert response.status_code == HTTP_OK

        data = response.json()

        assert "answer" in data
        assert "sources" in data
        assert "refinement_rounds" in data
        assert "query_variants" in data

        assert len(data["answer"]) > 0
        assert len(data["sources"]) > 0
        assert data["refinement_rounds"] >= 1
        assert len(data["query_variants"]) >= 1

        assert "CERN" in data["answer"] or "cern" in data["answer"].lower()


@pytest.mark.integration
async def test_foa_search_with_custom_rounds() -> None:
    """Test FoA search with custom refinement rounds."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{HARMONY_API_URL}/foa-search",
            json={"query": "CERN onboarding process", "max_refinement_rounds": 1},
            timeout=120.0,
        )
        assert response.status_code == HTTP_OK

        data = response.json()
        assert data["refinement_rounds"] <= 1


@pytest.mark.integration
async def test_foa_pipeline_via_openwebui() -> None:
    """Test FoA through OpenWebUI pipelines service."""
    async with httpx.AsyncClient() as client:
        request_body = {
            "model": "harmony_foa_search.harmony_foa_search",
            "messages": [{"role": "user", "content": "What is CERN?"}],
            "stream": False,
        }

        response = await client.post(
            f"{PIPELINES_URL}/v1/chat/completions",
            json=request_body,
            timeout=120.0,
        )

        assert response.status_code == HTTP_OK
        data = response.json()

        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
        assert "content" in data["choices"][0]["message"]

        content = data["choices"][0]["message"]["content"]
        assert len(content) > 0
        assert "Sources:" in content or "sources" in content.lower()


@pytest.mark.integration
async def test_foa_search_produces_citations() -> None:
    """Test that FoA search includes proper source citations."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{HARMONY_API_URL}/foa-search",
            json={"query": "CERN experiments"},
            timeout=120.0,
        )
        assert response.status_code == HTTP_OK

        data = response.json()
        sources = data["sources"]

        assert len(sources) > 0
        for source in sources:
            assert "title" in source
            assert "url" in source
            assert len(source["url"]) > 0
