from __future__ import annotations


def _bool(val: str | None, *, default: bool) -> bool:
    if not val:
        return default
    return val.lower() in {"true", "1", "yes"}


def test_bool_empty_string_returns_default() -> None:
    assert _bool("", default=True) is True


def test_bool_none_returns_default() -> None:
    assert _bool(None, default=True) is True


def test_bool_true_string() -> None:
    assert _bool("true", default=False) is True


def test_bool_false_string() -> None:
    assert _bool("false", default=True) is False
