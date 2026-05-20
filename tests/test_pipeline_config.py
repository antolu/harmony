from __future__ import annotations


def _bool(val: str | None, *, default: bool) -> bool:
    """Current (buggy) implementation copied from harmony.api.main._load_pipeline_config."""
    if val is None:
        return default
    return val.lower() in {"true", "1", "yes"}


def test_bool_empty_string_returns_default() -> None:
    assert _bool("", default=True) is True, (
        "Empty string must return default — BUG: currently returns False (Plan 02 fixes this)"
    )


def test_bool_none_returns_default() -> None:
    assert _bool(None, default=True) is True


def test_bool_true_string() -> None:
    assert _bool("true", default=False) is True


def test_bool_false_string() -> None:
    assert _bool("false", default=True) is False
