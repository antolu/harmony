from __future__ import annotations

import json
import typing
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from harmony.api.services.conversation import conversation_service
from harmony.api.services.llm import llm_service
from harmony.api.services.prompts import get_prompt_manager
from harmony.api.tools.registry import tool_registry

router = APIRouter(prefix="/ai-search", tags=["ai-search"])


class AISearchRequest(BaseModel):
    query: str
    conversation_id: str | None = None


async def stream_ai_search_events(  # noqa: PLR0912, PLR0914, PLR0915
    request: AISearchRequest,
) -> AsyncIterator[str]:
    """Generate SSE events for AI search streaming."""
    # Get or create conversation
    conversation_id = request.conversation_id or conversation_service.create()

    # Add user message
    conversation_service.add_message(conversation_id, "user", request.query)

    # Get conversation history
    messages = conversation_service.get_messages(conversation_id)

    # Add system message if this is a new conversation
    if len(messages) == 1:
        pm = get_prompt_manager()

        # Prepare tool data for template - get_all_tools() returns dicts
        tools_data = []
        for tool_def in tool_registry.get_all_tools():
            func = tool_def["function"]
            tools_data.append({
                "name": func["name"],
                "description": func["description"],
                "parameters": func["parameters"],
            })

        system_prompt = pm.render_system_prompt("chat", {"tools": tools_data})

        system_message = {
            "role": "system",
            "content": system_prompt,
        }
        messages.insert(0, system_message)

    # Track sources and seen titles
    sources: list[dict[str, typing.Any]] = []
    seen_titles: set[str] = set()

    try:  # noqa: PLR1702
        # LLM loop with tool calling (max 5 iterations)
        max_iterations = 5
        for _iteration in range(max_iterations):
            # Call LLM with all registered tools
            response = llm_service.complete_with_tools(
                messages=messages,
                tools=tool_registry.get_all_tools(),
            )

            assistant_message = response.choices[0].message

            # Check if we're done (no tool calls)
            if not assistant_message.tool_calls:
                # Add final answer to conversation
                conversation_service.add_message(
                    conversation_id, "assistant", assistant_message.content
                )

                # Stream answer token-by-token
                if assistant_message.content:
                    for char in assistant_message.content:
                        yield f"event: answer_chunk\ndata: {json.dumps({'content': char})}\n\n"

                # Done event with metadata
                yield f"event: done\ndata: {json.dumps({'sources': sources, 'conversation_id': conversation_id})}\n\n"
                return

            # Process tool calls
            tool_calls = assistant_message.tool_calls

            # Add assistant message with tool calls to conversation
            conversation_service.add_tool_call(
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

            # Add tool calls to messages for next iteration
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

            # Execute each tool call
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                # Emit tool call event
                yield f"event: tool_call\ndata: {json.dumps({'function': function_name, 'arguments': function_args})}\n\n"

                # Execute tool via registry
                tool_response = await tool_registry.execute(
                    function_name, function_args
                )

                # Track sources from search results and emit reading events
                if function_name == "search_documents":
                    try:
                        search_results = json.loads(tool_response)
                        if "results" in search_results:
                            # Top 5 results
                            for result in search_results["results"][:5]:
                                title = result.get("title", "")
                                url = result.get("url", "")

                                # Add to sources
                                sources.append({
                                    "title": title,
                                    "url": url,
                                    "snippet": result.get("snippet", ""),
                                })

                                # Emit reading event once per unique title
                                if title and title not in seen_titles:
                                    seen_titles.add(title)
                                    yield f"event: reading_page\ndata: {json.dumps({'title': title, 'url': url})}\n\n"
                    except json.JSONDecodeError:
                        pass

                # Add tool response to conversation
                conversation_service.add_tool_response(
                    conversation_id, tool_call.id, function_name, tool_response
                )

                # Add tool response to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": tool_response,
                })

        # If we hit max iterations, return final answer
        final_response = llm_service.complete(messages=messages)
        final_answer = (
            final_response.choices[0].message.content
            or "I apologize, but I couldn't complete the search in time."
        )

        conversation_service.add_message(conversation_id, "assistant", final_answer)

        # Stream final answer
        for char in final_answer:
            yield f"event: answer_chunk\ndata: {json.dumps({'content': char})}\n\n"

        # Done event
        yield f"event: done\ndata: {json.dumps({'sources': sources, 'conversation_id': conversation_id})}\n\n"

    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"


@router.post("")
async def ai_search(request: AISearchRequest) -> StreamingResponse:
    """LLM-orchestrated search with streaming events.

    The LLM can:
    1. Search for documents using natural language queries
    2. Retrieve detailed document content
    3. Perform follow-up searches based on initial results
    4. Synthesize information from multiple sources

    Events:
        - tool_call: Tool execution (search_documents, get_document_details)
        - reading_page: Once per unique page title during search
        - answer_chunk: Token-by-token answer streaming
        - done: Final metadata (sources, conversation_id)
        - error: Error messages

    Args:
        request: Search request with query and optional conversation_id

    Returns:
        StreamingResponse with Server-Sent Events
    """
    return StreamingResponse(
        stream_ai_search_events(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
