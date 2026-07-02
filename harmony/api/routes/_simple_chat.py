from __future__ import annotations

import asyncio
import json
import time
import typing
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from harmony.agents.simple import (
    AISearchDeps,
    _make_request_tool_registry,
    stream_ai_search_events,
)
from harmony.api.dependencies import (
    get_authz_context,
    get_conversation_service,
    get_current_user_or_anonymous,
    get_llm_service,
    get_model_policy_store,
    get_prompt_manager,
    get_search_service,
    get_service_config_store,
    get_tool_registry,
)
from harmony.api.routes._search_session import (
    maybe_generate_title_event,
    resolve_and_authorize_model,
    user_id_of,
)
from harmony.db.repositories import SearchLogData
from harmony.models import StreamEvent, UserIdentity
from harmony.services._external_search import ExternalSearchContext

router = APIRouter(prefix="/ai-search", tags=["ai-search"])

_background_tasks: set[asyncio.Task[None]] = set()


class AISearchRequest(BaseModel):
    query: str
    use_external_search: bool = False
    conversation_id: str | None = None
    model: str | None = None
    sources: list[str] | None = None


async def _sse_adaptor(
    domain_events: AsyncIterator[StreamEvent],
) -> AsyncIterator[str]:
    """Convert domain StreamEvent dicts to SSE wire strings."""
    async for event_dict in domain_events:
        event = event_dict.get("event", "message")
        data = event_dict.get("data", {})
        yield f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("")
async def ai_search(  # noqa: PLR0913
    http_request: Request,
    request: AISearchRequest,
    llm_service: typing.Any = Depends(get_llm_service),
    conversation_service: typing.Any = Depends(get_conversation_service),
    base_tool_registry: typing.Any = Depends(get_tool_registry),
    prompt_manager: typing.Any = Depends(get_prompt_manager),
    search_service: typing.Any = Depends(get_search_service),
    authz_context: typing.Any = Depends(get_authz_context),
    current_user: typing.Any = Depends(get_current_user_or_anonymous),
    model_policy_store: typing.Any = Depends(get_model_policy_store),
    service_config_store: typing.Any = Depends(get_service_config_store),
) -> StreamingResponse:
    """LLM-orchestrated search with streaming events."""
    model_registry_service = http_request.app.state.model_registry_service
    resolved_model, error_event = await resolve_and_authorize_model(
        request.model,
        current_user,
        model_policy_store,
        model_registry_service,
    )
    if resolved_model is None:

        async def _error_stream() -> AsyncIterator[str]:  # noqa: RUF029
            if error_event is not None:
                yield error_event

        return StreamingResponse(
            _error_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    deps = AISearchDeps(
        llm_service=llm_service,
        conversation_service=conversation_service,
        base_tool_registry=base_tool_registry,
        prompt_manager=prompt_manager,
        search_service=search_service,
        authz_context=authz_context,
        current_user=current_user,
        model_policy_store=model_policy_store,
        service_config_store=service_config_store,
    )
    ext_ctx = ExternalSearchContext(request_toggle=request.use_external_search)
    tool_registry = _make_request_tool_registry(
        deps.base_tool_registry,
        deps.search_service,
        deps.service_config_store,
        deps.authz_context,
        ext_ctx,
        request.sources,
    )

    audit_log_service = http_request.app.state.audit_log_service
    if audit_log_service is not None:
        user_id = (
            current_user.id if isinstance(current_user, UserIdentity) else "anonymous"
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
                    mode="ai",
                )
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    async def _combined_stream() -> AsyncIterator[str]:
        user_id_val = user_id_of(current_user) or "anonymous"
        is_new_conversation = request.conversation_id is None

        try:
            domain_events = stream_ai_search_events(
                query=request.query,
                conversation_id=request.conversation_id,
                resolved_model=resolved_model,
                is_new_conversation=is_new_conversation,
                user_id=user_id_val,
                deps=deps,
                tool_registry=tool_registry,
                pipeline_config=http_request.app.state.pipeline_config,
                model_registry_service=model_registry_service,
            )
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e

        answer_chunks = []
        actual_conversation_id = request.conversation_id
        async for sse in _sse_adaptor(domain_events):
            yield sse
            if sse.startswith("event: answer_chunk"):
                try:
                    data_str = sse.split("data: ")[1].strip()
                    data_dict = json.loads(data_str)
                    answer_chunks.append(data_dict.get("content", ""))
                except Exception:
                    pass
            elif sse.startswith("event: done"):
                try:
                    data_str = sse.split("data: ")[1].strip()
                    data_dict = json.loads(data_str)
                    if "conversation_id" in data_dict:
                        actual_conversation_id = data_dict["conversation_id"]
                except Exception:
                    pass

        title_event = await maybe_generate_title_event(
            is_new_conversation=is_new_conversation,
            conversation_id=actual_conversation_id or "",
            user_id=user_id_val,
            query=request.query,
            answer="".join(answer_chunks),
            conversation_service=conversation_service,
            llm_service=llm_service,
        )
        if title_event is not None:
            yield title_event

    return StreamingResponse(
        _combined_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
