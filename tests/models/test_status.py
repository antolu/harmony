from __future__ import annotations

from harmony.models import (
    Source,
    lean_sources_for_trace,
    search_status,
    status_event_to_wire,
    thinking_status,
)


def test_lean_sources_strips_indexed_presentation_fields() -> None:
    sources = [
        Source(
            url="https://idx/a",
            title="Indexed A",
            snippet="body",
            score=0.7,
            source_type="indexed",
        )
    ]
    lean = lean_sources_for_trace(sources)
    assert lean == [{"url": "https://idx/a", "score": 0.7, "source_type": "indexed"}]


def test_lean_sources_keeps_external_snapshot() -> None:
    external = Source(
        url="https://ext/a",
        title="External A",
        snippet="body",
        score=0.0,
        source_type="external",
    )
    [lean] = lean_sources_for_trace([external])
    assert lean["source_type"] == "external"
    assert lean["title"] == "External A"
    assert lean["snippet"] == "body"
    assert lean["url"] == "https://ext/a"


def test_lean_sources_treats_missing_type_as_indexed() -> None:
    lean = lean_sources_for_trace([Source(url="u", title="T", snippet="s", score=0.1)])
    assert "title" not in lean[0]
    assert lean[0]["source_type"] == "indexed"


def test_lean_sources_does_not_alias_input() -> None:
    external = Source(url="https://ext/a", score=0.0, source_type="external")
    [lean] = lean_sources_for_trace([external])
    lean["title"] = "mutated"
    assert not external.title


def test_status_event_to_wire_dumps_sources_and_leans_trace() -> None:
    event = search_status(
        "Searching",
        query="vacation policy",
        sources=[Source(url="u", title="T", snippet="s", score=0.5)],
    )
    wire, lean = status_event_to_wire(event)
    assert wire["kind"] == "search"
    assert wire["query"] == "vacation policy"
    assert wire["sources"] == [
        {
            "title": "T",
            "url": "u",
            "domain": "",
            "content": "",
            "snippet": "s",
            "score": 0.5,
            "source_type": "indexed",
        }
    ]
    assert lean == [{"url": "u", "score": 0.5, "source_type": "indexed"}]


def test_status_event_to_wire_without_sources_returns_none_lean() -> None:
    wire, lean = status_event_to_wire(
        thinking_status("Refining", step_id="refine-1", status="running")
    )
    assert wire == {
        "kind": "thinking",
        "message": "Refining",
        "step_id": "refine-1",
        "status": "running",
    }
    assert lean is None
