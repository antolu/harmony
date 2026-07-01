from __future__ import annotations

from harmony.tools._search import (  # noqa: PLC2701
    _TRUNCATION_MARKER,
    _allocate_content_budget,
)


def test_short_docs_returned_whole() -> None:
    contents = ["abc", "defg", "hi"]
    allocated = _allocate_content_budget(contents, char_budget=100)
    assert allocated == contents
    assert all(_TRUNCATION_MARKER not in c for c in allocated)


def test_strong_first_hit_claims_large_slice() -> None:
    contents = ["x" * 1000, "y" * 1000]
    allocated = _allocate_content_budget(contents, char_budget=600)
    assert allocated[0].startswith("x" * 300)
    assert _TRUNCATION_MARKER in allocated[0]
    assert _TRUNCATION_MARKER in allocated[1]


def test_unused_budget_flows_to_later_hits() -> None:
    contents = ["short", "z" * 1000]
    allocated = _allocate_content_budget(contents, char_budget=400)
    assert allocated[0] == "short"
    body = allocated[1].replace(_TRUNCATION_MARKER, "")
    assert len(body) > 200


def test_truncation_marker_points_to_get_document_details() -> None:
    allocated = _allocate_content_budget(["a" * 100], char_budget=10)
    assert "get_document_details" in allocated[0]


def test_zero_budget_truncates_everything() -> None:
    allocated = _allocate_content_budget(["abc", "def"], char_budget=0)
    assert all(not c.replace(_TRUNCATION_MARKER, "") for c in allocated)


def test_empty_input() -> None:
    assert _allocate_content_budget([], char_budget=100) == []
