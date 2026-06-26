from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import time
import typing
from collections.abc import AsyncIterator

import pydantic
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, JsonValue

from harmony.api.agents._source_pool import normalize_url
from harmony.api.authz import AuthorizationContext
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
from harmony.api.models.user import AnonymousIdentity, UserIdentity
from harmony.api.routes._search_session import (
    lean_sources_for_trace,
    maybe_generate_title_event,
    resolve_and_authorize_model,
    user_id_of,
)
from harmony.api.services import (
    ConversationService,
    LLMService,
    PipelineConfig,
    PromptManager,
    SearchService,
    StatusSink,
    use_model,
)
from harmony.api.services._conversation import ToolCallDict
from harmony.api.services._external_search import ExternalSearchContext
from harmony.api.services.admin import (
    ModelPolicyStore,
    ModelRegistryService,
    ServiceConfigStore,
)
from harmony.api.tools import SearchDocumentsTool, ToolRegistry
from harmony.db.repositories import SearchLogData


class LiteLLMFunctionProtocol(typing.Protocol):
    name: str
    arguments: str


class LiteLLMToolCallProtocol(typing.Protocol):
    id: str
    function: LiteLLMFunctionProtocol


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-search", tags=["ai-search"])

_background_tasks: set[asyncio.Task[None]] = set()


@dataclasses.dataclass
class ToolCallContext:
    conversation_id: str
    messages: list[dict[str, JsonValue]]
    sources_by_url: dict[str, dict[str, JsonValue]]
    conversation_service: ConversationService
    sink: StatusSink


class AISearchRequest(BaseModel):
    query: str
    use_external_search: bool = False
    conversation_id: str | None = None
    model: str | None = None
    sources: list[str] | None = None


@dataclasses.dataclass
class AISearchDeps:
    llm_service: LLMService = Depends(get_llm_service)  # noqa: RUF009
    conversation_service: ConversationService = Depends(get_conversation_service)  # noqa: RUF009
    base_tool_registry: ToolRegistry = Depends(get_tool_registry)  # noqa: RUF009
    prompt_manager: PromptManager = Depends(get_prompt_manager)  # noqa: RUF009
    search_service: SearchService = Depends(get_search_service)  # noqa: RUF009
    authz_context: AuthorizationContext = Depends(get_authz_context)  # noqa: RUF009
    current_user: UserIdentity | AnonymousIdentity = Depends(  # noqa: RUF009
        get_current_user_or_anonymous
    )
    model_policy_store: ModelPolicyStore = Depends(get_model_policy_store)  # noqa: RUF009
    service_config_store: ServiceConfigStore = Depends(get_service_config_store)  # noqa: RUF009


@dataclasses.dataclass
class SearchLoopState:
    conversation_id: str
    messages: list[dict[str, JsonValue]]
    sources_by_url: dict[str, dict[str, JsonValue]]
    assistant_reply: list[str]
    source_token_budget: int
    max_iterations: int
    trace_events: list[dict[str, JsonValue]] = dataclasses.field(default_factory=list)


def _prepare_system_message(
    pm: PromptManager, tool_registry: ToolRegistry
) -> dict[str, str]:
    tools_data = []
    for tool_def in tool_registry.get_all_tools():
        func = typing.cast(dict[str, pydantic.JsonValue], tool_def["function"])
        tools_data.append({
            "name": func["name"],
            "description": func["description"],
            "parameters": func["parameters"],
        })

    system_prompt = pm.render_system_prompt(
        "chat", {"tools": typing.cast(pydantic.JsonValue, tools_data)}
    )
    return {"role": "system", "content": system_prompt}


def _build_tool_call_dicts(
    tool_calls: typing.Sequence[LiteLLMToolCallProtocol],
) -> list[ToolCallDict]:
    return [
        {
            "id": tc.id,
            "type": "function",
            "function": {
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            },
        }
        for tc in tool_calls
    ]


_SOURCE_SNIPPET_CHARS = 300


def _extract_search_sources(tool_response: str) -> list[dict[str, JsonValue]]:
    try:
        search_results = json.loads(tool_response)
        if "results" in search_results:
            return [
                {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": str(result.get("content", result.get("snippet", "")))[
                        :_SOURCE_SNIPPET_CHARS
                    ],
                    "score": result.get("score", 0.0),
                    "source_type": result.get("source_type", "indexed"),
                }
                for result in search_results["results"]
            ]
    except json.JSONDecodeError:
        pass
    return []


_CHARS_PER_TOKEN = 4


def _budgeted_sources(
    sources_by_url: dict[str, dict[str, JsonValue]], token_budget: int
) -> list[dict[str, JsonValue]]:
    """Score-ordered sources whose cumulative snippet size fits the token budget.

    Token budget is enforced via a chars-per-token approximation rather than a live
    tokenizer to keep the search path cheap.
    """
    char_budget = token_budget * _CHARS_PER_TOKEN
    ranked = sorted(
        sources_by_url.values(),
        key=lambda s: float(s.get("score", 0.0)),
        reverse=True,
    )
    selected: list[dict[str, JsonValue]] = []
    used = 0
    for source in ranked:
        size = len(str(source.get("snippet", "")))
        if selected and used + size > char_budget:
            break
        selected.append(source)
        used += size
    return selected


def _narrate_tool(function_name: str, function_args: dict[str, JsonValue]) -> str:
    """Deterministic status message for a tool call."""
    if function_name == "search_documents":
        query = function_args.get("query", "")
        return f"Searching: {query}"
    if function_name == "get_document_details":
        doc_id = function_args.get("document_id", "")
        return f"Reading document: {doc_id}"
    if function_name in {"fetch_url", "fetch_pdf", "fetch_document"}:
        url = function_args.get("url", "")
        return f"Fetching: {url}"
    return f"Running: {function_name}"


async def _process_tool_calls(
    tool_calls: typing.Sequence[LiteLLMToolCallProtocol],
    tool_registry: ToolRegistry,
    ctx: ToolCallContext,
) -> None:
    """Process and execute tool calls, emitting structured status into the sink."""
    tool_call_dicts = _build_tool_call_dicts(tool_calls)
    logger.info(
        "Processing %d tool call(s) for conversation %s: %s",
        len(tool_call_dicts),
        ctx.conversation_id,
        [tc["function"]["name"] for tc in tool_call_dicts],
    )
    await ctx.conversation_service.add_tool_call(ctx.conversation_id, tool_call_dicts)
    ctx.messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": typing.cast(JsonValue, tool_call_dicts),
    })

    for tool_call in tool_calls:
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        logger.info("Executing tool call %s args=%s", function_name, function_args)

        narration = _narrate_tool(function_name, function_args)
        ctx.sink.emit(narration, kind="tool_call")

        try:
            tool_response = await tool_registry.execute(
                function_name, function_args, ctx.sink
            )
        except Exception:
            logger.exception(
                "Tool call %s failed for conversation %s",
                function_name,
                ctx.conversation_id,
            )
            tool_response = json.dumps({
                "error": f"Tool {function_name} failed; continue without its result."
            })
        logger.info("Tool call %s returned %d chars", function_name, len(tool_response))

        if function_name == "search_documents":
            extracted_sources = _extract_search_sources(tool_response)
            logger.info(
                "Extracted %d sources from %s", len(extracted_sources), function_name
            )
            for source in extracted_sources:
                key = normalize_url(str(source.get("url", "")))
                if not key:
                    continue
                existing = ctx.sources_by_url.get(key)
                if existing is None or float(source.get("score", 0.0)) > float(
                    existing.get("score", 0.0)
                ):
                    ctx.sources_by_url[key] = source
            ctx.sink.emit(
                narration,
                kind="search",
                query=str(function_args.get("query", "")),
                sources=list(extracted_sources),
            )

        await ctx.conversation_service.add_tool_response(
            ctx.conversation_id, tool_call.id, function_name, tool_response
        )
        ctx.messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": function_name,
            "content": tool_response,
        })

    logger.info(
        "Finished processing tool calls for conversation %s", ctx.conversation_id
    )


def _make_request_tool_registry(  # noqa: PLR0913
    base_registry: ToolRegistry,
    search_service: SearchService,
    service_config: ServiceConfigStore,
    authz_context: AuthorizationContext,
    external_context: ExternalSearchContext | None = None,
    sources: list[str] | None = None,
) -> ToolRegistry:
    request_registry = ToolRegistry()
    for name, tool in base_registry.tools.items():
        if name == "search_documents":
            request_registry.register(
                SearchDocumentsTool(
                    search_service=search_service,
                    service_config=service_config,
                    authz_context=authz_context,
                    external_context=external_context,
                    sources=sources,
                )
            )
        else:
            request_registry.register(tool)
    return request_registry


async def stream_ai_search_events(
    request: AISearchRequest,
    deps: AISearchDeps,
    tool_registry: ToolRegistry,
    pipeline_config: PipelineConfig,
    model_registry_service: ModelRegistryService | None = None,
) -> AsyncIterator[str]:
    """Generate SSE events for AI search streaming."""
    # Resolve the model string: the client sends a litellm_model_id from the registry.
    # We look it up server-side to guarantee the full provider/model_id form is used,
    # regardless of what legacy bare strings may exist in older registry rows.
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

    user_id = user_id_of(deps.current_user)
    is_new_conversation = request.conversation_id is None
    conversation_id = request.conversation_id or await deps.conversation_service.create(
        user_id, mode="search"
    )
    await deps.conversation_service.add_message(conversation_id, "user", request.query)
    raw_messages = await deps.conversation_service.get_messages(conversation_id)
    messages: list[dict[str, JsonValue]] = raw_messages or []

    if len(messages) == 1:
        system_message = _prepare_system_message(deps.prompt_manager, tool_registry)
        messages.insert(0, typing.cast(dict[str, JsonValue], system_message))

    assistant_reply: list[str] = []
    loop_state = SearchLoopState(
        conversation_id=conversation_id,
        messages=messages,
        sources_by_url={},
        assistant_reply=assistant_reply,
        source_token_budget=pipeline_config.ai_search_source_token_budget,
        max_iterations=pipeline_config.ai_search_max_iterations,
    )

    with use_model(resolved_model):
        try:
            async for event in _run_ai_search_loop(loop_state, deps, tool_registry):
                yield event
        except Exception as e:
            logger.exception(
                "ai-search loop failed for conversation %s", conversation_id
            )
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
        finally:
            if loop_state.trace_events:
                await deps.conversation_service.add_trace(
                    conversation_id, loop_state.trace_events
                )

        title_event = await maybe_generate_title_event(
            is_new_conversation=is_new_conversation,
            conversation_id=conversation_id,
            user_id=user_id,
            query=request.query,
            answer="".join(assistant_reply),
            conversation_service=deps.conversation_service,
            llm_service=deps.llm_service,
        )
        if title_event is not None:
            yield title_event


async def _process_tool_calls_and_close_sink(
    tool_calls: typing.Sequence[LiteLLMToolCallProtocol],
    tool_registry: ToolRegistry,
    ctx: ToolCallContext,
) -> None:
    try:
        await _process_tool_calls(tool_calls, tool_registry, ctx)
    finally:
        ctx.sink.close()


async def _run_ai_search_loop(
    state: SearchLoopState,
    deps: AISearchDeps,
    tool_registry: ToolRegistry,
) -> AsyncIterator[str]:
    max_iterations = state.max_iterations
    trace_events = state.trace_events
    for iteration in range(max_iterations):
        is_final_iteration = iteration == max_iterations - 1
        logger.info(
            "ai-search loop iteration %d/%d for conversation %s%s",
            iteration + 1,
            max_iterations,
            state.conversation_id,
            " (synthesis turn, tools disabled)" if is_final_iteration else "",
        )
        if is_final_iteration:
            synthesis_messages = [
                *state.messages,
                {
                    "role": "user",
                    "content": (
                        "Search budget exhausted. Answer now using the results "
                        "above. If nothing relevant was found, say so."
                    ),
                },
            ]
            response = await deps.llm_service.complete(
                messages=typing.cast(list[dict[str, str]], synthesis_messages),
                tools=None,
            )
        else:
            response = await deps.llm_service.complete_with_tools(
                messages=typing.cast(list[dict[str, str]], state.messages),
                tools=tool_registry.get_all_tools(),
            )

        assistant_message = response.choices[0].message
        logger.info(
            "Iteration %d completion: tool_calls=%s content_len=%s",
            iteration + 1,
            bool(assistant_message.tool_calls),
            len(assistant_message.content) if assistant_message.content else 0,
        )

        if is_final_iteration or not assistant_message.tool_calls:
            if assistant_message.content:
                state.assistant_reply.append(assistant_message.content)
                yield f"event: answer_chunk\ndata: {json.dumps({'content': assistant_message.content})}\n\n"
            else:
                logger.warning(
                    "Final completion had no tool_calls and no content "
                    "for conversation %s (iteration %d)",
                    state.conversation_id,
                    iteration + 1,
                )

            await deps.conversation_service.add_message(
                state.conversation_id,
                "assistant",
                "".join(state.assistant_reply) or assistant_message.content,
            )

            final_sources = _budgeted_sources(
                state.sources_by_url, state.source_token_budget
            )
            logger.info(
                "Emitting done for conversation %s with %d sources",
                state.conversation_id,
                len(final_sources),
            )
            trace_events.append({
                "kind": "done",
                "sources": typing.cast(
                    JsonValue, lean_sources_for_trace(final_sources)
                ),
            })
            yield f"event: done\ndata: {json.dumps({'sources': final_sources, 'conversation_id': state.conversation_id})}\n\n"
            return

        sink = StatusSink()
        ctx = ToolCallContext(
            conversation_id=state.conversation_id,
            messages=state.messages,
            sources_by_url=state.sources_by_url,
            conversation_service=deps.conversation_service,
            sink=sink,
        )

        process_task = asyncio.create_task(
            _process_tool_calls_and_close_sink(
                typing.cast(
                    typing.Sequence[LiteLLMToolCallProtocol],
                    assistant_message.tool_calls,
                ),
                tool_registry,
                ctx,
            )
        )
        status_count = 0
        async for status_event in sink.drain():
            status_count += 1
            event_data: dict[str, JsonValue] = {
                "message": status_event.message,
                **status_event.metadata,
            }
            trace_event = event_data
            raw_sources = event_data.get("sources")
            if isinstance(raw_sources, list):
                trace_event = {
                    **event_data,
                    "sources": lean_sources_for_trace(
                        typing.cast(list[dict[str, JsonValue]], raw_sources)
                    ),
                }
            trace_events.append(trace_event)
            yield (f"event: status\ndata: {json.dumps(event_data)}\n\n")
        logger.info(
            "Drained %d status event(s) for conversation %s iteration %d",
            status_count,
            state.conversation_id,
            iteration + 1,
        )
        await process_task

    msg = (
        f"ai-search loop exited without returning for conversation "
        f"{state.conversation_id}; final iteration must always emit an answer"
    )
    raise AssertionError(msg)


@router.post("")
async def ai_search(
    http_request: Request,
    request: AISearchRequest,
    deps: AISearchDeps = Depends(),
) -> StreamingResponse:
    """LLM-orchestrated search with streaming events."""
    ext_ctx = ExternalSearchContext(request_toggle=request.use_external_search)
    tool_registry = _make_request_tool_registry(
        deps.base_tool_registry,
        deps.search_service,
        deps.service_config_store,
        deps.authz_context,
        ext_ctx,
        request.sources,
    )

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
                    mode="ai",
                )
            )
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    return StreamingResponse(
        stream_ai_search_events(
            request,
            deps,
            tool_registry,
            pipeline_config=http_request.app.state.pipeline_config,
            model_registry_service=http_request.app.state.model_registry_service,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
