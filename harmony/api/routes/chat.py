from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from harmony.api.services.conversation import conversation_service
from harmony.api.services.llm import llm_service
from harmony.api.tools.search import SEARCH_TOOLS, execute_tool

router = APIRouter(prefix="/ai-search", tags=["ai-search"])


class AISearchRequest(BaseModel):
    query: str
    conversation_id: str | None = None


class AISearchResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]]
    conversation_id: str


@router.post("", response_model=AISearchResponse)
async def ai_search(request: AISearchRequest) -> AISearchResponse:
    """
    LLM-orchestrated search with agentic capabilities.

    The LLM can:
    1. Search for documents using natural language queries
    2. Retrieve detailed document content
    3. Perform follow-up searches based on initial results
    4. Synthesize information from multiple sources

    Args:
        request: Search request with query and optional conversation_id

    Returns:
        AI-generated answer with sources
    """
    # Get or create conversation
    conversation_id = request.conversation_id or conversation_service.create()

    # Add user message
    conversation_service.add_message(conversation_id, "user", request.query)

    # Get conversation history
    messages = conversation_service.get_messages(conversation_id)

    # Add system message if this is a new conversation
    if len(messages) == 1:
        system_message = {
            "role": "system",
            "content": (
                "You are a helpful research assistant with access to a document search system. "
                "Your job is to help users find information by:\n"
                "1. Understanding their question\n"
                "2. Searching for relevant documents using the search_documents tool\n"
                "3. Reading detailed content if needed using get_document_details\n"
                "4. Synthesizing information from multiple sources\n"
                "5. Providing accurate, well-cited answers\n\n"
                "Always cite your sources by mentioning document titles and URLs. "
                "If you can't find relevant information, say so clearly."
            ),
        }
        messages.insert(0, system_message)

    # Track sources
    sources: list[dict[str, Any]] = []

    # LLM loop with tool calling (max 5 iterations)
    max_iterations = 5
    for iteration in range(max_iterations):
        # Call LLM
        response = llm_service.complete_with_tools(
            messages=messages,
            tools=SEARCH_TOOLS,
        )

        assistant_message = response.choices[0].message

        # Check if we're done (no tool calls)
        if not assistant_message.tool_calls:
            # Add final answer to conversation
            conversation_service.add_message(
                conversation_id, "assistant", assistant_message.content
            )
            return AISearchResponse(
                answer=assistant_message.content or "",
                sources=sources,
                conversation_id=conversation_id,
            )

        # Process tool calls
        tool_calls = assistant_message.tool_calls

        # Add assistant message with tool calls to conversation
        conversation_service.add_tool_call(
            conversation_id,
            [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ],
        )

        # Add tool calls to messages for next iteration
        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
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
            }
        )

        # Execute each tool call
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            # Execute tool
            tool_response = await execute_tool(function_name, function_args)

            # Track sources from search results
            if function_name == "search_documents":
                try:
                    search_results = json.loads(tool_response)
                    if "results" in search_results:
                        for result in search_results["results"][:5]:  # Top 5 results
                            sources.append(
                                {
                                    "title": result.get("title", ""),
                                    "url": result.get("url", ""),
                                    "snippet": result.get("snippet", ""),
                                }
                            )
                except json.JSONDecodeError:
                    pass

            # Add tool response to conversation
            conversation_service.add_tool_response(
                conversation_id, tool_call.id, function_name, tool_response
            )

            # Add tool response to messages
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": tool_response,
                }
            )

    # If we hit max iterations, return what we have
    final_response = llm_service.complete(messages=messages)
    final_answer = final_response.choices[0].message.content

    conversation_service.add_message(conversation_id, "assistant", final_answer)

    return AISearchResponse(
        answer=final_answer or "I apologize, but I couldn't complete the search in time.",
        sources=sources,
        conversation_id=conversation_id,
    )
