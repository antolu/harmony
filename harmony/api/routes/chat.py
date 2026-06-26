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
from harmony.api.services import (
    ConversationService,
    LLMContext,
    LLMService,
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
    sources: list[dict[str, JsonValue]]
    conversation_service: ConversationService
    sink: StatusSink
    prompt_manager: PromptManager
    llm_service: LLMService
    seen_titles: set[str] = dataclasses.field(default_factory=set)


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
    sources: list[dict[str, JsonValue]]
    seen_titles: set[str]
    assistant_reply: list[str]


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


def _extract_search_sources(tool_response: str) -> list[dict[str, JsonValue]]:
    try:
        search_results = json.loads(tool_response)
        if "results" in search_results:
            return [
                {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": result.get("snippet", ""),
                }
                for result in search_results["results"][:5]
            ]
    except json.JSONDecodeError:
        pass
    return []


_NARRATION_TIMEOUT_SECONDS = 3.0


async def _narrate_tool_call(
    ctx: ToolCallContext,
    function_name: str,
    function_args: dict[str, JsonValue],
) -> str | None:
    """Generate a present-tense narration phrase for a tool call.

    Returns None on failure or timeout so the caller can suppress the status
    line entirely rather than fall back to a generic phrase.
    """
    try:
        system_prompt = ctx.prompt_manager.render_system_prompt(
            "narration",
            {
                "function_name": function_name,
                "function_args": typing.cast(JsonValue, function_args),
            },
        )
        response = await asyncio.wait_for(
            ctx.llm_service.complete(
                messages=[{"role": "system", "content": system_prompt}],
                ctx=LLMContext(agent_step="narration"),
            ),
            timeout=_NARRATION_TIMEOUT_SECONDS,
        )
        content = response.choices[0].message.content
        return content.strip() if content else None
    except TimeoutError:
        logger.warning(
            "Narration timed out after %.1fs for tool call %s",
            _NARRATION_TIMEOUT_SECONDS,
            function_name,
        )
        return None
    except Exception:
        logger.warning(
            "Narration failed for tool call %s", function_name, exc_info=True
        )
        return None


async def _process_tool_calls(
    tool_calls: typing.Sequence[LiteLLMToolCallProtocol],
    tool_registry: ToolRegistry,
    ctx: ToolCallContext,
) -> None:
    """Process and execute tool calls, emitting narrated status into the sink."""
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

        narration_task = asyncio.create_task(
            _narrate_tool_call(ctx, function_name, function_args)
        )
        tool_response = await tool_registry.execute(
            function_name, function_args, ctx.sink
        )
        logger.info("Tool call %s returned %d chars", function_name, len(tool_response))
        narration = await narration_task
        logger.info("Narration for %s: %r", function_name, narration)
        if narration:
            ctx.sink.emit(narration, kind="tool_call")

        if function_name == "search_documents":
            extracted_sources = _extract_search_sources(tool_response)
            logger.info(
                "Extracted %d sources from %s", len(extracted_sources), function_name
            )
            for source in extracted_sources:
                title = source.get("title", "")
                if title and str(title) in ctx.seen_titles:
                    continue
                ctx.sources.append(source)
                if title:
                    ctx.seen_titles.add(str(title))

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
    model_registry_service: ModelRegistryService | None = None,
) -> AsyncIterator[str]:
    """Generate SSE events for AI search streaming."""
    # Resolve the model string: the client sends a litellm_model_id from the registry.
    # We look it up server-side to guarantee the full provider/model_id form is used,
    # regardless of what legacy bare strings may exist in older registry rows.
    if request.model is None:
        yield f"event: error\ndata: {json.dumps({'message': 'No model selected'})}\n\n"
        return

    resolved_model: str | None = None
    if model_registry_service is not None:
        resolved_model = await model_registry_service.resolve_litellm_model_id(
            request.model
        )
    if resolved_model is None:
        resolved_model = request.model

    if (
        isinstance(deps.current_user, UserIdentity)
        and deps.model_policy_store is not None
    ):
        allowed_roles = await deps.model_policy_store.get_allowed_roles(resolved_model)
        if allowed_roles and deps.current_user.harmony_role not in allowed_roles:
            yield f"event: error\ndata: {json.dumps({'message': 'Model not permitted for your role'})}\n\n"
            return

    user_id = (
        deps.current_user.id if isinstance(deps.current_user, UserIdentity) else None
    )
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

    sources: list[dict[str, JsonValue]] = []
    seen_titles: set[str] = set()
    assistant_reply: list[str] = []

    with use_model(resolved_model):
        try:
            loop_state = SearchLoopState(
                conversation_id=conversation_id,
                messages=messages,
                sources=sources,
                seen_titles=seen_titles,
                assistant_reply=assistant_reply,
            )
            async for event in _run_ai_search_loop(loop_state, deps, tool_registry):
                yield event
        except Exception as e:
            logger.exception(
                "ai-search loop failed for conversation %s", conversation_id
            )
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

        if is_new_conversation and assistant_reply:
            title = await deps.conversation_service.generate_title_async(
                conversation_id,
                user_id,
                request.query,
                "".join(assistant_reply),
                deps.llm_service,
            )
            if title:
                yield (
                    f"event: title\ndata: "
                    f"{json.dumps({'conversation_id': conversation_id, 'title': title})}"
                    f"\n\n"
                )


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
    max_iterations = 5
    for iteration in range(max_iterations):
        logger.info(
            "ai-search loop iteration %d/%d for conversation %s",
            iteration + 1,
            max_iterations,
            state.conversation_id,
        )
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

        if not assistant_message.tool_calls:
            await deps.conversation_service.add_message(
                state.conversation_id, "assistant", assistant_message.content
            )

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

            logger.info(
                "Emitting done for conversation %s with %d sources",
                state.conversation_id,
                len(state.sources),
            )
            yield f"event: done\ndata: {json.dumps({'sources': state.sources, 'conversation_id': state.conversation_id})}\n\n"
            return

        sink = StatusSink()
        ctx = ToolCallContext(
            conversation_id=state.conversation_id,
            messages=state.messages,
            sources=state.sources,
            seen_titles=state.seen_titles,
            conversation_service=deps.conversation_service,
            sink=sink,
            prompt_manager=deps.prompt_manager,
            llm_service=deps.llm_service,
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
            yield (
                "event: status\n"
                f"data: {json.dumps({'message': status_event.message, **status_event.metadata})}\n\n"
            )
        logger.info(
            "Drained %d status event(s) for conversation %s iteration %d",
            status_count,
            state.conversation_id,
            iteration + 1,
        )
        await process_task

    logger.warning(
        "Exhausted %d iterations without a final answer for conversation %s; "
        "falling back to stream_complete without tools",
        max_iterations,
        state.conversation_id,
    )
    async for token in deps.llm_service.stream_complete(
        messages=typing.cast(list[dict[str, str]], state.messages)
    ):
        state.assistant_reply.append(token)
        yield f"event: answer_chunk\ndata: {json.dumps({'content': token})}\n\n"

    logger.info(
        "Fallback stream_complete produced %d chars for conversation %s",
        len("".join(state.assistant_reply)),
        state.conversation_id,
    )
    await deps.conversation_service.add_message(
        state.conversation_id, "assistant", "".join(state.assistant_reply)
    )
    yield f"event: done\ndata: {json.dumps({'sources': state.sources, 'conversation_id': state.conversation_id})}\n\n"


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
            model_registry_service=http_request.app.state.model_registry_service,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
