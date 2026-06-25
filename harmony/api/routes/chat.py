from __future__ import annotations

import asyncio
import dataclasses
import json
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
)
from harmony.api.services._conversation import ToolCallDict
from harmony.api.services._external_search import ExternalSearchContext
from harmony.api.services.admin import (
    ModelPolicyStore,
    ModelRegistryService,
    ServiceConfigStore,
)
from harmony.api.tools import SearchDocumentsTool, ToolRegistry


class LiteLLMFunctionProtocol(typing.Protocol):
    name: str
    arguments: str


class LiteLLMToolCallProtocol(typing.Protocol):
    id: str
    function: LiteLLMFunctionProtocol


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
    prompt_manager: PromptManager,
    llm_service: LLMService,
    function_name: str,
    function_args: dict[str, JsonValue],
) -> str | None:
    """Generate a present-tense narration phrase for a tool call.

    Returns None on failure or timeout so the caller can suppress the status
    line entirely rather than fall back to a generic phrase.
    """
    try:
        system_prompt = prompt_manager.render_system_prompt(
            "narration",
            {
                "function_name": function_name,
                "function_args": typing.cast(JsonValue, function_args),
            },
        )
        response = await asyncio.wait_for(
            llm_service.complete(
                messages=[{"role": "system", "content": system_prompt}],
                ctx=LLMContext(agent_step="narration"),
            ),
            timeout=_NARRATION_TIMEOUT_SECONDS,
        )
        content = response.choices[0].message.content
        return content.strip() if content else None
    except Exception:
        return None


async def _process_tool_calls(
    tool_calls: typing.Sequence[LiteLLMToolCallProtocol],
    tool_registry: ToolRegistry,
    ctx: ToolCallContext,
) -> None:
    """Process and execute tool calls, emitting narrated status into the sink."""
    tool_call_dicts = _build_tool_call_dicts(tool_calls)
    await ctx.conversation_service.add_tool_call(ctx.conversation_id, tool_call_dicts)
    ctx.messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": typing.cast(JsonValue, tool_call_dicts),
    })

    for tool_call in tool_calls:
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)

        narration_task = asyncio.create_task(
            _narrate_tool_call(
                ctx.prompt_manager, ctx.llm_service, function_name, function_args
            )
        )
        tool_response = await tool_registry.execute(
            function_name, function_args, ctx.sink
        )
        narration = await narration_task
        if narration:
            ctx.sink.emit(narration, kind="tool_call")

        if function_name == "search_documents":
            for source in _extract_search_sources(tool_response):
                ctx.sources.append(source)
                title = source.get("title", "")
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
    resolved_model: str | None = None
    if request.model is not None:
        if model_registry_service is not None:
            resolved_model = await model_registry_service.resolve_litellm_model_id(
                request.model
            )
        if resolved_model is None:
            resolved_model = request.model

    if (
        resolved_model is not None
        and isinstance(deps.current_user, UserIdentity)
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

    try:
        loop_state = SearchLoopState(
            conversation_id=conversation_id,
            messages=messages,
            sources=sources,
            seen_titles=seen_titles,
            assistant_reply=assistant_reply,
        )
        async for event in _run_ai_search_loop(
            loop_state,
            deps,
            tool_registry,
            model=resolved_model,
        ):
            yield event
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    if is_new_conversation and assistant_reply:
        title_task = asyncio.create_task(
            deps.conversation_service.generate_title_async(
                conversation_id,
                user_id,
                request.query,
                "".join(assistant_reply),
                deps.llm_service,
            )
        )
        _background_tasks.add(title_task)
        title_task.add_done_callback(_background_tasks.discard)


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
    model: str | None = None,
) -> AsyncIterator[str]:
    max_iterations = 5
    for _iteration in range(max_iterations):
        response = await deps.llm_service.complete_with_tools(
            messages=typing.cast(list[dict[str, str]], state.messages),
            tools=tool_registry.get_all_tools(),
            model=model,
        )

        assistant_message = response.choices[0].message

        if not assistant_message.tool_calls:
            await deps.conversation_service.add_message(
                state.conversation_id, "assistant", assistant_message.content
            )

            if assistant_message.content:
                state.assistant_reply.append(assistant_message.content)
                yield f"event: answer_chunk\ndata: {json.dumps({'content': assistant_message.content})}\n\n"

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
        async for status_event in sink.drain():
            yield f"event: status\ndata: {json.dumps({'message': status_event.message})}\n\n"
        await process_task

    async for token in deps.llm_service.stream_complete(
        messages=typing.cast(list[dict[str, str]], state.messages), model=model
    ):
        state.assistant_reply.append(token)
        yield f"event: answer_chunk\ndata: {json.dumps({'content': token})}\n\n"

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
            audit_log_service.record_search({
                "user_id": user_id,
                "query": request.query,
                "language": None,
                "result_count": None,
                "latency_ms": latency_ms,
                "tokens": None,
                "mode": "ai",
            })
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
