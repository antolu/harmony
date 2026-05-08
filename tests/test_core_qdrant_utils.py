from __future__ import annotations

from harmony.core import url_to_id


def test_url_to_id_importable_from_core() -> None:
    assert callable(url_to_id)


def test_url_to_id_is_deterministic() -> None:
    assert url_to_id("https://example.com/page") == url_to_id(
        "https://example.com/page"
    )


def test_url_to_id_returns_int() -> None:
    assert isinstance(url_to_id("https://example.com"), int)


def test_url_to_id_different_urls_differ() -> None:
    assert url_to_id("https://a.com") != url_to_id("https://b.com")
