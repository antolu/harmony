from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from harmony.api.agents.critic import CriticAgent
from harmony.api.agents.orchestrator import AgenticOrchestrator
from harmony.api.agents.query_planner import QueryPlannerAgent
from harmony.api.agents.searcher import SearcherAgent
from harmony.api.agents.synthesizer import SynthesizerAgent
from harmony.api.config import settings
from harmony.api.services.elasticsearch import es_service
from harmony.api.services.llm import llm_service

router = APIRouter(tags=["agentic-search"])


class AgenticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User's search query")
    max_refinement_rounds: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum number of critic-synthesizer refinement rounds",
    )


_orchestrator: AgenticOrchestrator | None = None


def get_orchestrator() -> AgenticOrchestrator:
    """Get or create the Agentic orchestrator singleton."""
    global _orchestrator  # noqa: PLW0603
    if _orchestrator is None:
        query_planner = QueryPlannerAgent(llm_service)
        searcher = SearcherAgent(es_service)
        critic = CriticAgent(llm_service)
        synthesizer = SynthesizerAgent(llm_service)

        _orchestrator = AgenticOrchestrator(
            query_planner=query_planner,
            searcher=searcher,
            critic=critic,
            synthesizer=synthesizer,
            max_refinement_rounds=settings.agentic_max_refinement_rounds,
            max_query_variants=settings.agentic_max_query_variants,
        )

    return _orchestrator


async def stream_events(request: AgenticSearchRequest) -> AsyncIterator[str]:
    """Generate SSE events for streaming response."""
    orchestrator = get_orchestrator()

    if hasattr(orchestrator, "max_refinement_rounds"):
        orchestrator.max_refinement_rounds = request.max_refinement_rounds

    async for event in orchestrator.stream_search(request.query):
        # Format as SSE
        event_type = event["event"]
        event_data = json.dumps(event["data"])
        yield f"event: {event_type}\ndata: {event_data}\n\n"


@router.post("/agentic-search")
async def agentic_search(request: AgenticSearchRequest) -> StreamingResponse:
    """Multi-agent search with streaming events.

    This endpoint implements streaming Agentic Search:

    1. Query Planning: Streams query variants as generated
    2. Parallel Search: Emits "Reading [page]" for each unique source
    3. K-Round Refinement: Streams round updates and consensus status
    4. Final Answer: Streams answer tokens in real-time

    Events:
        - query_variant: Each search variant generated
        - reading_page: Once per unique page title
        - refinement_round: Round start/complete with metrics
        - answer_chunk: Token-by-token answer streaming
        - done: Final metadata (sources, rounds, variants)
        - error: Error messages

    Args:
        request: Agentic search request with query and parameters

    Returns:
        StreamingResponse with Server-Sent Events
    """
    return StreamingResponse(
        stream_events(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
