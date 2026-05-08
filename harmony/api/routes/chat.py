from __future__ import annotations

import json
import typing
from collections.abc import AsyncGenerator, AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from harmony.api.dependencies import (
    get_conversation_service,
    get_llm_service,
    get_prompt_manager,
    get_tool_registry,
)
from harmony.api.services import ConversationService, LLMService, PromptManager
from harmony.api.tools import ToolRegistry

router = APIRouter(prefix="/ai-search", tags=["ai-search"])


class AISearchRequest(BaseModel):
    query: str
    conversation_id: str | None = None


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


async def _process_tool_calls(  # noqa: PLR0913
    tool_calls: list[typing.Any],
    conversation_id: str,
    messages: list[dict[str, typing.Any]],
    sources: list[dict[str, typing.Any]],
    seen_titles: set[str],
    conversation_service: ConversationService,
    tool_registry: ToolRegistry,
) -> AsyncGenerator[str, None]:
    """Process and execute tool calls, yielding SSE events."""
    await conversation_service.add_tool_call(
        conversation_id,
        [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in tool_calls
        ],
    )

    tool_call_dicts: list[dict[str, typing.Any]] = [
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
    messages.append({
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
            try:
                search_results = json.loads(tool_response)
                if "results" in search_results:
                    for result in search_results["results"][:5]:
                        title = result.get("title", "")
                        url = result.get("url", "")
                        sources.append({
                            "title": title,
                            "url": url,
                            "snippet": result.get("snippet", ""),
                        })
                        if title and title not in seen_titles:
                            seen_titles.add(title)
                            yield f"event: reading_page\ndata: {json.dumps({'title': title, 'url': url})}\n\n"
            except json.JSONDecodeError:
                pass

        await conversation_service.add_tool_response(
            conversation_id, tool_call.id, function_name, tool_response
        )
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": function_name,
            "content": tool_response,
        })


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

    sources: list[dict[str, typing.Any]] = []
    seen_titles: set[str] = set()

    try:
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

            async for event in _process_tool_calls(
                assistant_message.tool_calls,
                conversation_id,
                messages,
                sources,
                seen_titles,
                conversation_service,
                tool_registry,
            ):
                yield event

        async for token in llm_service.stream_complete(messages=messages):
            yield f"event: answer_chunk\ndata: {json.dumps({'content': token})}\n\n"

        await conversation_service.add_message(conversation_id, "assistant", "")
        yield f"event: done\ndata: {json.dumps({'sources': sources, 'conversation_id': conversation_id})}\n\n"

    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"


@router.post("")
async def ai_search(
    request: AISearchRequest,
    llm_service: LLMService = Depends(get_llm_service),
    conversation_service: ConversationService = Depends(get_conversation_service),
    tool_registry: ToolRegistry = Depends(get_tool_registry),
    prompt_manager: PromptManager = Depends(get_prompt_manager),
) -> StreamingResponse:
    """LLM-orchestrated search with streaming events."""
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
