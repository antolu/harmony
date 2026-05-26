from __future__ import annotations

import asyncio
import json
import typing
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass, field

from fastapi import APIRouter, Depends
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
    get_tool_registry,
)
from harmony.api.models.user import AnonymousIdentity, UserIdentity
from harmony.api.services import (
    ConversationService,
    LLMService,
    PromptManager,
    SearchService,
)
from harmony.api.services._conversation import ToolCallDict
from harmony.api.services._external_search import ExternalSearchContext
from harmony.api.services.admin import ModelPolicyStore
from harmony.api.tools import SearchDocumentsTool, ToolRegistry

router = APIRouter(prefix="/ai-search", tags=["ai-search"])

_background_tasks: set[asyncio.Task[None]] = set()


@dataclass
class ToolCallContext:
    conversation_id: str
    messages: list[dict[str, JsonValue]]
    sources: list[dict[str, JsonValue]]
    conversation_service: ConversationService
    seen_titles: set[str] = field(default_factory=set)


class AISearchRequest(BaseModel):
    query: str
    conversation_id: str | None = None
    use_external_search: bool = False
    model: str | None = None


def _prepare_system_message(
    pm: PromptManager, tool_registry: ToolRegistry
) -> dict[str, str]:
    tools_data = []
    for tool_def in tool_registry.get_all_tools():
        func = tool_def["function"]
        tools_data.append({
            "name": func["name"],
            "description": func["description"],
            "parameters": func["parameters"],
        })

    system_prompt = pm.render_system_prompt("chat", {"tools": tools_data})
    return {"role": "system", "content": system_prompt}


def _build_tool_call_dicts(tool_calls: list[typing.Any]) -> list[ToolCallDict]:
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


async def _process_tool_calls(
    tool_calls: list[typing.Any],
    tool_registry: ToolRegistry,
    ctx: ToolCallContext,
) -> AsyncGenerator[str, None]:
    """Process and execute tool calls, yielding SSE events."""
    tool_call_dicts = _build_tool_call_dicts(tool_calls)
    await ctx.conversation_service.add_tool_call(ctx.conversation_id, tool_call_dicts)
    ctx.messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": tool_call_dicts,
    })

    for tool_call in tool_calls:
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)

        yield f"event: tool_call\ndata: {json.dumps({'function': function_name, 'arguments': function_args})}\n\n"

        tool_response = await tool_registry.execute(function_name, function_args)

        if function_name == "search_documents":
            for source in _extract_search_sources(tool_response):
                ctx.sources.append(source)
                title = source.get("title", "")
                url = source.get("url", "")
                if title and title not in ctx.seen_titles:
                    ctx.seen_titles.add(str(title))
                    yield f"event: reading_page\ndata: {json.dumps({'title': title, 'url': url})}\n\n"

        await ctx.conversation_service.add_tool_response(
            ctx.conversation_id, tool_call.id, function_name, tool_response
        )
        ctx.messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": function_name,
            "content": tool_response,
        })


def _make_request_tool_registry(
    base_registry: ToolRegistry,
    search_service: SearchService,
    authz_context: AuthorizationContext,
    external_context: ExternalSearchContext | None = None,
) -> ToolRegistry:
    request_registry = ToolRegistry()
    for name, tool in base_registry.tools.items():
        if name == "search_documents":
            request_registry.register(
                SearchDocumentsTool(
                    search_service=search_service,
                    authz_context=authz_context,
                    external_context=external_context,
                )
            )
        else:
            request_registry.register(tool)
    return request_registry


async def stream_ai_search_events(  # noqa: PLR0913
    request: AISearchRequest,
    llm_service: LLMService,
    conversation_service: ConversationService,
    tool_registry: ToolRegistry,
    prompt_manager: PromptManager,
    current_user: UserIdentity | AnonymousIdentity | None = None,
    model_policy_store: ModelPolicyStore | None = None,
) -> AsyncIterator[str]:
    """Generate SSE events for AI search streaming."""
    if (
        request.model is not None
        and isinstance(current_user, UserIdentity)
        and model_policy_store is not None
    ):
        allowed_roles = await model_policy_store.get_allowed_roles(request.model)
        if allowed_roles and current_user.harmony_role not in allowed_roles:
            yield f"event: error\ndata: {json.dumps({'message': 'Model not permitted for your role'})}\n\n"
            return

    user_id = current_user.id if isinstance(current_user, UserIdentity) else None
    is_new_conversation = request.conversation_id is None
    conversation_id = request.conversation_id or await conversation_service.create(
        user_id, mode="search"
    )
    await conversation_service.add_message(conversation_id, "user", request.query)
    raw_messages = await conversation_service.get_messages(conversation_id)
    messages: list[dict[str, JsonValue]] = raw_messages or []

    if len(messages) == 1:
        system_message = _prepare_system_message(prompt_manager, tool_registry)
        messages.insert(0, system_message)

    sources: list[dict[str, JsonValue]] = []
    seen_titles: set[str] = set()
    assistant_reply: list[str] = []

    try:
        async for event in _run_ai_search_loop(
            conversation_id,
            messages,
            sources,
            seen_titles,
            assistant_reply,
            llm_service,
            conversation_service,
            tool_registry,
            model=request.model,
        ):
            yield event
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
    else:
        yield f"event: error\ndata: {json.dumps({'message': 'Max tool call iterations reached'})}\n\n"
        return

    if is_new_conversation and assistant_reply:
        title_task = asyncio.create_task(
            conversation_service.generate_title_async(
                conversation_id,
                user_id,
                request.query,
                "".join(assistant_reply),
                llm_service,
            )
        )
        _background_tasks.add(title_task)
        title_task.add_done_callback(_background_tasks.discard)


async def _run_ai_search_loop(  # noqa: PLR0913
    conversation_id: str,
    messages: list[dict[str, JsonValue]],
    sources: list[dict[str, JsonValue]],
    seen_titles: set[str],
    assistant_reply: list[str],
    llm_service: LLMService,
    conversation_service: ConversationService,
    tool_registry: ToolRegistry,
    model: str | None = None,
) -> AsyncIterator[str]:
    max_iterations = 5
    for _iteration in range(max_iterations):
        response = await llm_service.complete_with_tools(
            messages=messages,
            tools=tool_registry.get_all_tools(),
            model=model,
        )

        assistant_message = response.choices[0].message

        if not assistant_message.tool_calls:
            await conversation_service.add_message(
                conversation_id, "assistant", assistant_message.content
            )

            if assistant_message.content:
                async for token in llm_service.stream_complete(
                    messages=messages, model=model
                ):
                    assistant_reply.append(token)
                    yield f"event: answer_chunk\ndata: {json.dumps({'content': token})}\n\n"

            yield f"event: done\ndata: {json.dumps({'sources': sources, 'conversation_id': conversation_id})}\n\n"
            return

        ctx = ToolCallContext(
            conversation_id=conversation_id,
            messages=messages,
            sources=sources,
            seen_titles=seen_titles,
            conversation_service=conversation_service,
        )
        async for event in _process_tool_calls(
            assistant_message.tool_calls,
            tool_registry,
            ctx,
        ):
            yield event

    async for token in llm_service.stream_complete(messages=messages, model=model):
        assistant_reply.append(token)
        yield f"event: answer_chunk\ndata: {json.dumps({'content': token})}\n\n"

    await conversation_service.add_message(conversation_id, "assistant", "")
    yield f"event: done\ndata: {json.dumps({'sources': sources, 'conversation_id': conversation_id})}\n\n"


@router.post("")
async def ai_search(  # noqa: PLR0913
    request: AISearchRequest,
    llm_service: LLMService = Depends(get_llm_service),
    conversation_service: ConversationService = Depends(get_conversation_service),
    base_tool_registry: ToolRegistry = Depends(get_tool_registry),
    prompt_manager: PromptManager = Depends(get_prompt_manager),
    search_service: SearchService = Depends(get_search_service),
    authz_context: AuthorizationContext = Depends(get_authz_context),
    current_user: UserIdentity | AnonymousIdentity = Depends(
        get_current_user_or_anonymous
    ),
    model_policy_store: ModelPolicyStore = Depends(get_model_policy_store),
) -> StreamingResponse:
    """LLM-orchestrated search with streaming events."""
    ext_ctx = ExternalSearchContext(request_toggle=request.use_external_search)
    tool_registry = _make_request_tool_registry(
        base_tool_registry, search_service, authz_context, ext_ctx
    )
    return StreamingResponse(
        stream_ai_search_events(
            request,
            llm_service,
            conversation_service,
            tool_registry,
            prompt_manager,
            current_user=current_user,
            model_policy_store=model_policy_store,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
