from __future__ import annotations

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
    get_llm_service,
    get_prompt_manager,
    get_search_service,
    get_tool_registry,
)
from harmony.api.services import (
    ConversationService,
    LLMService,
    PromptManager,
    SearchService,
)
from harmony.api.services._conversation import ToolCallDict
from harmony.api.services._external_search import ExternalSearchContext
from harmony.api.tools import SearchDocumentsTool, ToolRegistry

router = APIRouter(prefix="/ai-search", tags=["ai-search"])


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


async def stream_ai_search_events(
    request: AISearchRequest,
    llm_service: LLMService,
    conversation_service: ConversationService,
    tool_registry: ToolRegistry,
    prompt_manager: PromptManager,
) -> AsyncIterator[str]:
    """Generate SSE events for AI search streaming."""
    conversation_id = request.conversation_id or await conversation_service.create()
    await conversation_service.add_message(conversation_id, "user", request.query)
    messages = await conversation_service.get_messages(conversation_id)

    if len(messages) == 1:
        system_message = _prepare_system_message(prompt_manager, tool_registry)
        messages.insert(0, system_message)

    sources: list[dict[str, JsonValue]] = []
    seen_titles: set[str] = set()

    try:
        async for event in _run_ai_search_loop(
            conversation_id,
            messages,
            sources,
            seen_titles,
            llm_service,
            conversation_service,
            tool_registry,
        ):
            yield event
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
    else:
        yield f"event: error\ndata: {json.dumps({'message': 'Max tool call iterations reached'})}\n\n"


async def _run_ai_search_loop(  # noqa: PLR0913
    conversation_id: str,
    messages: list[dict[str, JsonValue]],
    sources: list[dict[str, JsonValue]],
    seen_titles: set[str],
    llm_service: LLMService,
    conversation_service: ConversationService,
    tool_registry: ToolRegistry,
) -> AsyncIterator[str]:
    max_iterations = 5
    for _iteration in range(max_iterations):
        response = await llm_service.complete_with_tools(
            messages=messages,
            tools=tool_registry.get_all_tools(),
        )

        assistant_message = response.choices[0].message

        if not assistant_message.tool_calls:
            await conversation_service.add_message(
                conversation_id, "assistant", assistant_message.content
            )

            if assistant_message.content:
                async for token in llm_service.stream_complete(messages=messages):
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

    async for token in llm_service.stream_complete(messages=messages):
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
) -> StreamingResponse:
    """LLM-orchestrated search with streaming events."""
    ext_ctx = ExternalSearchContext(request_toggle=request.use_external_search)
    tool_registry = _make_request_tool_registry(
        base_tool_registry, search_service, authz_context, ext_ctx
    )
    return StreamingResponse(
        stream_ai_search_events(
            request, llm_service, conversation_service, tool_registry, prompt_manager
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
