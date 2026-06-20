from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from harmony.api.agents import AgenticOrchestrator
from harmony.api.authz import AuthorizationContext
from harmony.api.dependencies import (
    get_authz_context,
    get_conversation_service,
    get_current_user_or_anonymous,
    get_llm_service,
    get_orchestrator,
)
from harmony.api.models.user import AnonymousIdentity, UserIdentity
from harmony.api.services import ConversationService, LLMService
from harmony.api.services._external_search import ExternalSearchContext

router = APIRouter(tags=["agentic-search"])

_background_tasks: set[asyncio.Task[None]] = set()


class AgenticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User's search query")
    max_refinement_rounds: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum number of critic-synthesizer refinement rounds",
    )
    use_external_search: bool = False
    conversation_id: str | None = None
    model: str | None = None
    sources: list[str] | None = None


@dataclass
class AgenticSearchDeps:
    orchestrator: AgenticOrchestrator = Depends(get_orchestrator)  # noqa: RUF009
    authz_context: AuthorizationContext = Depends(get_authz_context)  # noqa: RUF009
    conversation_service: ConversationService = Depends(get_conversation_service)  # noqa: RUF009
    current_user: UserIdentity | AnonymousIdentity = Depends(  # noqa: RUF009
        get_current_user_or_anonymous
    )
    llm_service: LLMService = Depends(get_llm_service)  # noqa: RUF009


async def stream_events(
    request: AgenticSearchRequest,
    deps: AgenticSearchDeps,
) -> AsyncIterator[str]:
    """Generate SSE events for streaming response."""
    ext_ctx = ExternalSearchContext(request_toggle=request.use_external_search)
    user_id = (
        deps.current_user.id if isinstance(deps.current_user, UserIdentity) else None
    )
    is_new_conversation = request.conversation_id is None

    if request.conversation_id is None:
        conversation_id = await deps.conversation_service.create(user_id, mode="search")
        await deps.conversation_service.add_message(
            conversation_id, "user", request.query
        )
    else:
        conversation_id = request.conversation_id
        await deps.conversation_service.add_message_scoped(
            conversation_id, user_id, "user", request.query
        )

    final_answer: list[str] = []

    async for event in deps.orchestrator.stream_search(
        request.query,
        authz_context=deps.authz_context,
        external_context=ext_ctx,
        max_refinement_rounds=request.max_refinement_rounds,
        sources=request.sources,
    ):
        event_type = event["event"]
        event_data = event["data"]

        if event_type == "answer_chunk":
            chunk = event_data.get("chunk", "") if isinstance(event_data, dict) else ""
            if chunk:
                final_answer.append(str(chunk))

        if event_type == "done":
            assistant_text = "".join(final_answer)
            await deps.conversation_service.add_message_scoped(
                conversation_id, user_id, "assistant", assistant_text
            )
            if isinstance(event_data, dict):
                event_data = {**event_data, "conversation_id": conversation_id}
            else:
                event_data = {"conversation_id": conversation_id}

            if is_new_conversation and assistant_text:
                title_task = asyncio.create_task(
                    deps.conversation_service.generate_title_async(
                        conversation_id,
                        user_id,
                        request.query,
                        assistant_text,
                        deps.llm_service,
                    )
                )
                _background_tasks.add(title_task)
                title_task.add_done_callback(_background_tasks.discard)

        yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"


@router.post("/agentic-search")
async def agentic_search(
    http_request: Request,
    request: AgenticSearchRequest,
    deps: AgenticSearchDeps = Depends(),
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
    audit_log_service = getattr(http_request.app.state, "audit_log_service", None)
    if audit_log_service is not None:
        user_id = (
            deps.current_user.id
            if isinstance(deps.current_user, UserIdentity)
            else "anonymous"
        )
        start = time.monotonic()
        latency_ms = int((time.monotonic() - start) * 1000)
        task = asyncio.create_task(
            audit_log_service.record_search({
                "user_id": user_id,
                "query": request.query,
                "language": None,
                "result_count": None,
                "latency_ms": latency_ms,
                "tokens": None,
                "mode": "agentic",
            })
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    return StreamingResponse(
        stream_events(
            request,
            deps,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
