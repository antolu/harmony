import json
import os

import httpx
import pytest

pytestmark = pytest.mark.asyncio

HARMONY_API_URL = "http://localhost:8000"
PIPELINES_URL = "http://localhost:9099"
HTTP_OK = 200


def has_llm_keys() -> bool:
    """Check if any LLM API keys are present in the environment."""
    keys = ["GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
    return any(os.getenv(k) for k in keys)


async def is_api_alive() -> bool:
    """Check if harmony-api is alive."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{HARMONY_API_URL}/docs", timeout=2.0)
            return response.status_code == HTTP_OK
    except Exception:
        return False


def is_llm_ready() -> bool:
    """
    Check if LLM is ready on the server.
    """
    return has_llm_keys()


def _handle_sse_event(  # noqa: PLR0913
    data_str: str,
    current_event: str | None,
    answer_chunks: list[str],
    query_variants: list[str],
    sources: list,
    rounds: list[int],
) -> None:
    data = json.loads(data_str)
    if current_event == "answer_chunk":
        answer_chunks.append(data.get("content", ""))
    elif current_event == "query_variant":
        query_variants.append(data.get("variant", ""))
    elif current_event == "done":
        sources[:] = data.get("sources", [])
        rounds[0] = data.get("refinement_rounds", 0)


async def parse_sse_stream(response: httpx.Response) -> dict:
    """Parse SSE stream and extract final data from 'done' event."""
    answer_chunks: list[str] = []
    query_variants: list[str] = []
    sources: list = []
    rounds = [0]
    current_event = None

    async for line in response.aiter_lines():
        line = line.strip()

        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            data_str = line[6:]
            try:
                _handle_sse_event(
                    data_str,
                    current_event,
                    answer_chunks,
                    query_variants,
                    sources,
                    rounds,
                )
            except json.JSONDecodeError:
                continue

    return {
        "answer": "".join(answer_chunks),
        "sources": sources,
        "refinement_rounds": rounds[0],
        "query_variants": query_variants,
    }


@pytest.mark.integration
async def test_foa_search_end_to_end() -> None:
    """Full FoA search with real ES and LLM."""
    if not await is_api_alive():
        pytest.skip("Harmony API is not running")
    if not is_llm_ready():
        pytest.skip("LLM is not ready/configured")
    async with (
        httpx.AsyncClient() as client,
        client.stream(
            "POST",
            f"{HARMONY_API_URL}/agentic-search",
            json={"query": "What is CERN?"},
            timeout=120.0,
        ) as response,
    ):
        assert response.status_code == HTTP_OK

        data = await parse_sse_stream(response)

        assert len(data["answer"]) > 0
        assert len(data["sources"]) > 0
        assert data["refinement_rounds"] >= 1
        assert len(data["query_variants"]) >= 1

        assert "CERN" in data["answer"] or "cern" in data["answer"].lower()


@pytest.mark.integration
async def test_foa_search_with_custom_rounds() -> None:
    """Test FoA search with custom refinement rounds."""
    if not await is_api_alive():
        pytest.skip("Harmony API is not running")
    if not is_llm_ready():
        pytest.skip("LLM is not ready/configured")
    async with (
        httpx.AsyncClient() as client,
        client.stream(
            "POST",
            f"{HARMONY_API_URL}/agentic-search",
            json={"query": "CERN onboarding process", "max_refinement_rounds": 1},
            timeout=120.0,
        ) as response,
    ):
        assert response.status_code == HTTP_OK

        data = await parse_sse_stream(response)
        assert data["refinement_rounds"] <= 1


@pytest.mark.skip(reason="Requires OpenWebUI pipelines service running")
@pytest.mark.integration
async def test_foa_pipeline_via_openwebui() -> None:
    """Test Agentic Search through OpenWebUI pipelines service."""
    async with httpx.AsyncClient() as client:
        request_body = {
            "model": "harmony_agentic_search.harmony_agentic_search",
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
    if not await is_api_alive():
        pytest.skip("Harmony API is not running")
    if not is_llm_ready():
        pytest.skip("LLM is not ready/configured")
    async with (
        httpx.AsyncClient() as client,
        client.stream(
            "POST",
            f"{HARMONY_API_URL}/agentic-search",
            json={"query": "CERN experiments"},
            timeout=120.0,
        ) as response,
    ):
        assert response.status_code == HTTP_OK

        data = await parse_sse_stream(response)
        sources = data["sources"]

        assert len(sources) > 0
        for source in sources:
            assert "title" in source
            assert "url" in source
            assert len(source["url"]) > 0
