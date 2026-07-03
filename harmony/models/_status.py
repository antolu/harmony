from __future__ import annotations

import typing

import pydantic

from ._search import Source


class StatusBase(typing.TypedDict):
    """Shared envelope for every status event.

    message is always shown to the user. step_id + status give a generic
    running->done lifecycle so a long-running step can be emitted as running
    and later re-emitted (same step_id) as done, coalesced by the consumer.
    """

    message: str
    step_id: typing.NotRequired[str]
    status: typing.NotRequired[typing.Literal["running", "done"]]


class SearchStatus(StatusBase):
    kind: typing.Literal["search"]
    query: typing.NotRequired[str]
    keyword_variants: typing.NotRequired[list[str]]
    sources: typing.NotRequired[list[Source]]


class ThinkingStatus(StatusBase):
    kind: typing.Literal["thinking"]
    sources: typing.NotRequired[list[Source]]


class ToolCallStatus(StatusBase):
    kind: typing.Literal["tool_call"]
    tool_name: typing.NotRequired[str]


class AnswerChunkStatus(StatusBase):
    kind: typing.Literal["answer_chunk"]


class ExtensionStatus(StatusBase):
    """Quarantined escape hatch for events outside the core vocabulary.

    The only member carrying an open payload. Reach for a first-class member
    before this; it exists so a future or third-party producer can stream an
    event the core vocabulary doesn't yet model without loosening every event.
    """

    kind: typing.Literal["extension"]
    name: str
    data: dict[str, pydantic.JsonValue]


StatusEvent = (
    SearchStatus | ThinkingStatus | ToolCallStatus | AnswerChunkStatus | ExtensionStatus
)


def search_status(  # noqa: PLR0913
    message: str,
    *,
    step_id: str | None = None,
    status: typing.Literal["running", "done"] | None = None,
    query: str | None = None,
    keyword_variants: list[str] | None = None,
    sources: list[Source] | None = None,
) -> SearchStatus:
    event: SearchStatus = {"kind": "search", "message": message}
    if step_id is not None:
        event["step_id"] = step_id
    if status is not None:
        event["status"] = status
    if query is not None:
        event["query"] = query
    if keyword_variants is not None:
        event["keyword_variants"] = keyword_variants
    if sources is not None:
        event["sources"] = sources
    return event


def thinking_status(
    message: str,
    *,
    step_id: str | None = None,
    status: typing.Literal["running", "done"] | None = None,
    sources: list[Source] | None = None,
) -> ThinkingStatus:
    event: ThinkingStatus = {"kind": "thinking", "message": message}
    if step_id is not None:
        event["step_id"] = step_id
    if status is not None:
        event["status"] = status
    if sources is not None:
        event["sources"] = sources
    return event


def tool_call_status(
    message: str,
    *,
    step_id: str | None = None,
    status: typing.Literal["running", "done"] | None = None,
    tool_name: str | None = None,
) -> ToolCallStatus:
    event: ToolCallStatus = {"kind": "tool_call", "message": message}
    if step_id is not None:
        event["step_id"] = step_id
    if status is not None:
        event["status"] = status
    if tool_name is not None:
        event["tool_name"] = tool_name
    return event


def answer_chunk_status(message: str) -> AnswerChunkStatus:
    return {"kind": "answer_chunk", "message": message}


def extension_status(
    message: str,
    *,
    name: str,
    data: dict[str, pydantic.JsonValue],
    step_id: str | None = None,
    status: typing.Literal["running", "done"] | None = None,
) -> ExtensionStatus:
    event: ExtensionStatus = {
        "kind": "extension",
        "message": message,
        "name": name,
        "data": data,
    }
    if step_id is not None:
        event["step_id"] = step_id
    if status is not None:
        event["status"] = status
    return event


class StreamEvent(typing.TypedDict):
    """Envelope yielded by the agentic stream: wire payload + optional trace.

    'data' is the SSE payload sent to the client; 'trace' is the leaned form
    persisted to the conversation trace (None when the event carries nothing
    worth persisting).
    """

    event: str
    data: dict[str, pydantic.JsonValue]
    trace: typing.NotRequired[dict[str, pydantic.JsonValue] | None]


class TraceSource(typing.TypedDict):
    url: str
    score: float
    source_type: str
    title: typing.NotRequired[str]
    snippet: typing.NotRequired[str]
    domain: typing.NotRequired[str]
    content: typing.NotRequired[str]


def lean_sources_for_trace(sources: list[Source]) -> list[TraceSource]:
    """Drop denormalized presentation fields from indexed sources before persisting.

    Indexed citations are hydrated from the index by URL on render, so storing their
    title/snippet would only go stale — keep just the pointer. External sources are not
    in the index, so their snapshot is preserved as the only recoverable copy.
    """
    lean: list[TraceSource] = []
    for source in sources:
        if source.source_type == "external":
            lean.append({
                "url": source.url,
                "score": source.score,
                "source_type": "external",
                "title": source.title,
                "snippet": source.snippet,
                "domain": source.domain,
                "content": source.content,
            })
        else:
            lean.append({
                "url": source.url,
                "score": source.score,
                "source_type": "indexed",
            })
    return lean


def status_event_to_wire(
    event: StatusEvent,
) -> tuple[dict[str, pydantic.JsonValue], list[TraceSource] | None]:
    """Serialize a typed status event for the SSE wire and the persisted trace.

    Returns the wire dict (Source objects dumped to plain dicts) and, when the
    event carries sources, their leaned trace form for persistence. Indexed
    citations are leaned to a pointer; external snapshots are kept whole.
    """
    sources = typing.cast("list[Source] | None", event.get("sources"))
    wire: dict[str, pydantic.JsonValue] = {
        key: typing.cast(pydantic.JsonValue, value)
        for key, value in event.items()
        if key != "sources"
    }
    if sources is None:
        return wire, None
    wire["sources"] = [s.model_dump() for s in sources]
    return wire, lean_sources_for_trace(sources)


class StatusSinkProtocol(typing.Protocol):
    """Structural contract for status reporting.

    Agents and tools depend on this, not on any concrete sink
    implementation, so they can run outside the Harmony API/web process
    (scripts, tests, other host services) without importing request/queue
    machinery they'll never use.
    """

    def emit(self, event: StatusEvent) -> None: ...
