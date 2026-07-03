from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import typing
from collections.abc import AsyncIterator

import pydantic
from pydantic import JsonValue

from harmony.authz import AuthorizationContext
from harmony.models import (
    AnonymousIdentity,
    Source,
    StreamEvent,
    UserIdentity,
    lean_sources_for_trace,
    search_status,
    status_event_to_wire,
    tool_call_status,
)
from harmony.services import (
    ConversationService,
    ExternalSearchContext,
    LLMService,
    PipelineConfig,
    PromptManager,
    SearchService,
    StatusSink,
    ToolCallDict,
    use_model,
)
from harmony.services.admin import (
    ConfigProvider,
    ModelPolicyStore,
    ModelRegistryService,
)
from harmony.tools import SearchDocumentsTool, ToolRegistry

from .._source_pool import SourcePool


class LiteLLMFunctionProtocol(typing.Protocol):
    name: str
    arguments: str


class LiteLLMToolCallProtocol(typing.Protocol):
    id: str
    function: LiteLLMFunctionProtocol


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ToolCallContext:
    conversation_id: str
    messages: list[dict[str, JsonValue]]
    source_pool: SourcePool
    conversation_service: ConversationService
    sink: StatusSink


@dataclasses.dataclass
class AISearchDeps:
    llm_service: LLMService
    conversation_service: ConversationService
    base_tool_registry: ToolRegistry
    prompt_manager: PromptManager
    search_service: SearchService
    authz_context: AuthorizationContext
    current_user: UserIdentity | AnonymousIdentity
    model_policy_store: ModelPolicyStore
    service_config_store: ConfigProvider


@dataclasses.dataclass
class AISearchContext:
    query: str
    conversation_id: str | None
    resolved_model: str
    is_new_conversation: bool
    user_id: str


@dataclasses.dataclass
class SearchLoopState:
    conversation_id: str
    messages: list[dict[str, JsonValue]]
    source_pool: SourcePool
    assistant_reply: list[str]
    source_token_budget: int
    max_iterations: int
    trace_events: list[dict[str, JsonValue]] = dataclasses.field(default_factory=list)


def _flatten_for_synthesis(
    messages: list[dict[str, JsonValue]],
    instruction: str,
) -> list[dict[str, JsonValue]]:
    """Drop tool-call turns and fold tool results into a single user turn.

    The synthesis turn offers no tools, but providers like Gemini mirror
    function-call context from history and keep emitting tool_calls instead of
    an answer. We remove the assistant tool_call turns entirely (they only say
    *that* a tool was called, which is noise and re-primes tool use) and fold
    the tool *results* plus the synthesis instruction into the trailing user
    message.

    Gemini also rejects/stalls on consecutive same-role turns, so we collapse
    any run of adjacent user turns (the original query, the retrieved material,
    and the instruction) into one, keeping strict role alternation.
    """
    cleaned: list[dict[str, JsonValue]] = []
    tool_results: list[str] = []
    for message in messages:
        role = message.get("role")
        if role == "assistant" and message.get("tool_calls"):
            continue
        if role == "tool":
            name = message.get("name", "")
            content = message.get("content", "")
            tool_results.append(f"Result from {name}:\n{content}")
            continue
        cleaned.append(message)

    trailing = instruction
    if tool_results:
        trailing = (
            "Retrieved material:\n\n" + "\n\n".join(tool_results) + f"\n\n{instruction}"
        )
    cleaned.append({"role": "user", "content": trailing})

    merged: list[dict[str, JsonValue]] = []
    for message in cleaned:
        if (
            merged
            and merged[-1].get("role") == message.get("role")
            and message.get("role") in {"user", "assistant"}
        ):
            prev = merged[-1].get("content")
            cur = message.get("content")
            prev_text = prev if isinstance(prev, str) else ""
            cur_text = cur if isinstance(cur, str) else ""
            merged[-1] = {
                "role": message.get("role"),
                "content": f"{prev_text}\n\n{cur_text}".strip(),
            }
        else:
            merged.append(message)
    return merged


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


def _extract_search_sources(tool_response: str) -> list[Source]:
    try:
        search_results = json.loads(tool_response)
        if "results" in search_results:
            return [
                Source(
                    title=result.get("title", ""),
                    url=result.get("url", ""),
                    snippet=str(result.get("content", result.get("snippet", "")))[
                        :_SOURCE_SNIPPET_CHARS
                    ],
                    score=result.get("score", 0.0),
                    source_type=result.get("source_type", "indexed"),
                )
                for result in search_results["results"]
            ]
    except json.JSONDecodeError:
        pass
    return []


_CHARS_PER_TOKEN = 4


def _budgeted_sources(pool: SourcePool, token_budget: int) -> list[Source]:
    """Score-ordered sources whose cumulative snippet size fits the token budget.

    Token budget is enforced via a chars-per-token approximation rather than a live
    tokenizer to keep the search path cheap.
    """
    char_budget = token_budget * _CHARS_PER_TOKEN
    selected: list[Source] = []
    used = 0
    for source in pool.ranked():
        size = len(source.snippet)
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
        ctx.sink.emit(tool_call_status(narration, tool_name=function_name))

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
            ctx.source_pool.add_all(s for s in extracted_sources if s.url)
            ctx.sink.emit(
                search_status(
                    narration,
                    query=str(function_args.get("query", "")),
                    sources=extracted_sources,
                )
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


def make_request_tool_registry(  # noqa: PLR0913
    base_registry: ToolRegistry,
    search_service: SearchService,
    service_config: ConfigProvider,
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
    ctx: AISearchContext,
    deps: AISearchDeps,
    tool_registry: ToolRegistry,
    pipeline_config: PipelineConfig,
    model_registry_service: ModelRegistryService | None = None,
) -> AsyncIterator[StreamEvent]:
    """Generate SSE events for AI search streaming."""
    # Resolve the model string: the client sends a litellm_model_id from the registry.
    # We look it up server-side to guarantee the full provider/model_id form is used,
    # regardless of what legacy bare strings may exist in older registry rows.
    conversation_id = ctx.conversation_id or await deps.conversation_service.create(
        ctx.user_id, mode="search"
    )
    if ctx.is_new_conversation:
        await deps.conversation_service.add_message(conversation_id, "user", ctx.query)
    else:
        try:
            await deps.conversation_service.add_message_scoped(
                conversation_id, ctx.user_id, "user", ctx.query
            )
        except PermissionError as e:
            raise PermissionError(str(e)) from e
        except ValueError as e:
            raise ValueError(str(e)) from e

    raw_messages = await deps.conversation_service.get_messages(
        conversation_id, ctx.user_id
    )
    if raw_messages is None and not ctx.is_new_conversation:
        msg = "Conversation not found"
        raise ValueError(msg)
    messages: list[dict[str, JsonValue]] = raw_messages or []

    if len(messages) == 1:
        system_message = _prepare_system_message(deps.prompt_manager, tool_registry)
        messages.insert(0, typing.cast(dict[str, JsonValue], system_message))

    assistant_reply: list[str] = []
    loop_state = SearchLoopState(
        conversation_id=conversation_id,
        messages=messages,
        source_pool=SourcePool(),
        assistant_reply=assistant_reply,
        source_token_budget=pipeline_config.ai_search_source_token_budget,
        max_iterations=pipeline_config.ai_search_max_iterations,
    )

    with use_model(ctx.resolved_model):
        try:
            async for event in _run_ai_search_loop(loop_state, deps, tool_registry):
                yield event
        except Exception as e:
            logger.exception(
                "ai-search loop failed for conversation %s", conversation_id
            )
            yield {"event": "error", "data": {"message": str(e)}}
        finally:
            if loop_state.trace_events:
                await deps.conversation_service.add_trace(
                    conversation_id, loop_state.trace_events
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


async def _run_ai_search_loop(  # noqa: PLR0914, PLR0915
    state: SearchLoopState,
    deps: AISearchDeps,
    tool_registry: ToolRegistry,
) -> AsyncIterator[StreamEvent]:
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
            synthesis_messages = _flatten_for_synthesis(
                state.messages,
                "Search budget exhausted. Answer now using the results "
                "above. If nothing relevant was found, say so.",
            )
            chunk_count = 0
            try:
                async for token in deps.llm_service.stream_complete(
                    messages=typing.cast(list[dict[str, str]], synthesis_messages)
                ):
                    chunk_count += 1
                    state.assistant_reply.append(token)
                    yield {"event": "answer_chunk", "data": {"content": token}}
            except Exception as e:
                raise PermissionError(str(e)) from e
            if chunk_count == 0:
                logger.warning(
                    "Synthesis stream produced no content for conversation %s",
                    state.conversation_id,
                )

            await deps.conversation_service.add_message(
                state.conversation_id, "assistant", "".join(state.assistant_reply)
            )
            final_sources = _budgeted_sources(
                state.source_pool, state.source_token_budget
            )
            source_dicts = [s.model_dump() for s in final_sources]
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
            yield {
                "event": "done",
                "data": {
                    "sources": typing.cast(JsonValue, source_dicts),
                    "conversation_id": state.conversation_id,
                },
            }
            return

        try:
            response = await deps.llm_service.complete_with_tools(
                messages=typing.cast(list[dict[str, str]], state.messages),
                tools=tool_registry.get_all_tools(),
            )
        except Exception as e:
            raise PermissionError(str(e)) from e

        assistant_message = response.choices[0].message
        logger.info(
            "Iteration %d completion: tool_calls=%s content_len=%s",
            iteration + 1,
            bool(assistant_message.tool_calls),
            len(assistant_message.content) if assistant_message.content else 0,
        )

        if not assistant_message.tool_calls:
            if assistant_message.content:
                state.assistant_reply.append(assistant_message.content)
                yield {
                    "event": "answer_chunk",
                    "data": {"content": assistant_message.content},
                }
            else:
                logger.warning(
                    "Completion had no tool_calls and no content "
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
                state.source_pool, state.source_token_budget
            )
            source_dicts = [s.model_dump() for s in final_sources]
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
            yield {
                "event": "done",
                "data": {
                    "sources": typing.cast(JsonValue, source_dicts),
                    "conversation_id": state.conversation_id,
                },
            }
            return

        sink = StatusSink()
        ctx = ToolCallContext(
            conversation_id=state.conversation_id,
            messages=state.messages,
            source_pool=state.source_pool,
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
            wire_event, lean = status_event_to_wire(status_event)
            if lean is not None:
                trace_events.append({
                    **wire_event,
                    "sources": typing.cast(JsonValue, lean),
                })
            else:
                trace_events.append(wire_event)
            yield {"event": "status", "data": wire_event}
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
