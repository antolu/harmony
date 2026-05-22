from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from harmony.api.agents import AgenticOrchestrator
from harmony.api.authz import AuthorizationContext
from harmony.api.dependencies import get_authz_context, get_orchestrator

router = APIRouter(tags=["agentic-search"])


class AgenticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User's search query")
    max_refinement_rounds: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum number of critic-synthesizer refinement rounds",
    )


async def stream_events(
    request: AgenticSearchRequest,
    orchestrator: AgenticOrchestrator,
    authz_context: AuthorizationContext,
) -> AsyncIterator[str]:
    """Generate SSE events for streaming response."""
    if hasattr(orchestrator, "max_refinement_rounds"):
        orchestrator.max_refinement_rounds = request.max_refinement_rounds

    async for event in orchestrator.stream_search(
        request.query, authz_context=authz_context
    ):
        event_type = event["event"]
        event_data = json.dumps(event["data"])
        yield f"event: {event_type}\ndata: {event_data}\n\n"


@router.post("/agentic-search")
async def agentic_search(
    request: AgenticSearchRequest,
    orchestrator: AgenticOrchestrator = Depends(get_orchestrator),
    authz_context: AuthorizationContext = Depends(get_authz_context),
) -> StreamingResponse:
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
        stream_events(request, orchestrator, authz_context),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
