from __future__ import annotations

import asyncio
import dataclasses
import json
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, JsonValue

from harmony.agents import AgenticOrchestrator
from harmony.api.dependencies import (
    get_authz_context,
    get_conversation_service,
    get_current_user_or_anonymous,
    get_llm_service,
    get_model_policy_store,
    get_orchestrator,
)
from harmony.api.exceptions import PermissionDeniedError
from harmony.api.routes._search_session import (
    maybe_generate_title_event,
    resolve_and_authorize_model,
    user_id_of,
)
from harmony.api.services.admin import ModelPolicyStore, ModelRegistryService
from harmony.authz import AuthorizationContext
from harmony.db.repositories import SearchLogData
from harmony.models import AnonymousIdentity, UserIdentity
from harmony.services import ConversationService, LLMService, use_model
from harmony.services._external_search import ExternalSearchContext

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


@dataclasses.dataclass
class AgenticSearchDeps:
    orchestrator: AgenticOrchestrator = Depends(get_orchestrator)  # noqa: RUF009
    authz_context: AuthorizationContext = Depends(get_authz_context)  # noqa: RUF009
    conversation_service: ConversationService = Depends(get_conversation_service)  # noqa: RUF009
    current_user: UserIdentity | AnonymousIdentity = Depends(  # noqa: RUF009
        get_current_user_or_anonymous
    )
    llm_service: LLMService = Depends(get_llm_service)  # noqa: RUF009
    model_policy_store: ModelPolicyStore = Depends(get_model_policy_store)  # noqa: RUF009


async def stream_events(  # noqa: PLR0912, PLR0914
    request: AgenticSearchRequest,
    deps: AgenticSearchDeps,
    model_registry_service: ModelRegistryService | None = None,
) -> AsyncIterator[str]:
    """Generate SSE events for streaming response."""
    resolved_model, error_event = await resolve_and_authorize_model(
        request.model,
        deps.current_user,
        deps.model_policy_store,
        model_registry_service,
    )
    if resolved_model is None:
        if error_event is not None:
            yield error_event
        return

    ext_ctx = ExternalSearchContext(request_toggle=request.use_external_search)
    user_id = user_id_of(deps.current_user)
    is_new_conversation = request.conversation_id is None

    if request.conversation_id is None:
        conversation_id = await deps.conversation_service.create(user_id, mode="search")
        await deps.conversation_service.add_message(
            conversation_id, "user", request.query
        )
    else:
        conversation_id = request.conversation_id
        try:
            await deps.conversation_service.add_message_scoped(
                conversation_id, user_id, "user", request.query
            )
        except PermissionDeniedError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e

    final_answer: list[str] = []
    trace_events: list[dict[str, JsonValue]] = []

    with use_model(resolved_model):
        async for event in deps.orchestrator.stream_search(
            request.query,
            authz_context=deps.authz_context,
            external_context=ext_ctx,
            max_refinement_rounds=request.max_refinement_rounds,
            sources=request.sources,
        ):
            event_type = event["event"]
            event_data = event["data"]
            trace_event = event.get("trace")
            if trace_event is not None:
                trace_events.append(trace_event)

            if event_type == "answer_chunk":
                if not isinstance(event_data, dict):
                    msg = f"answer_chunk event data must be a dict, got {type(event_data)!r}"
                    raise TypeError(msg)
                chunk = event_data["content"]
                if chunk:
                    final_answer.append(str(chunk))

            if event_type == "done":
                assistant_text = "".join(final_answer)

                trace_id = await deps.conversation_service.add_trace(
                    conversation_id, trace_events
                )
                try:
                    await deps.conversation_service.add_message_scoped(
                        conversation_id,
                        user_id,
                        "assistant",
                        assistant_text,
                        trace_id=trace_id,
                    )
                except PermissionDeniedError as e:
                    raise HTTPException(status_code=403, detail=str(e)) from e
                if isinstance(event_data, dict):
                    event_data = {**event_data, "conversation_id": conversation_id}
                else:
                    event_data = {"conversation_id": conversation_id}

            yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"

            if event_type == "done":
                title_event = await maybe_generate_title_event(
                    is_new_conversation=is_new_conversation,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    query=request.query,
                    answer=assistant_text,
                    conversation_service=deps.conversation_service,
                    llm_service=deps.llm_service,
                )
                if title_event is not None:
                    yield title_event


@router.post("/agentic-search")
async def agentic_search(
    http_request: Request,
    request: AgenticSearchRequest,
    deps: AgenticSearchDeps = Depends(),
) -> StreamingResponse:
    """Multi-agent search with streaming events.

    This endpoint implements streaming Agentic Search:

    1. Query Planning + Parallel Search: each query variant emits one status
       event as soon as its search resolves, carrying its sources bundled
    2. K-Round Refinement: emits a status event per round start/complete
    3. Final Answer: Streams answer tokens in real-time

    Events:
        - status: unified status event for all narration/progress. Carries
          a `kind` field ("search", "thinking", "tool_call") plus the shared
          envelope (`message`, optional `step_id`/`status` lifecycle) —
          "search" events bundle that variant's `sources` list
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
            audit_log_service.record_search(
                SearchLogData(
                    user_id=user_id,
                    query=request.query,
                    language=None,
                    result_count=None,
                    latency_ms=latency_ms,
                    tokens=None,
                    mode="agentic",
                )
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    return StreamingResponse(
        stream_events(
            request,
            deps,
            model_registry_service=getattr(
                http_request.app.state, "model_registry_service", None
            ),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
