from __future__ import annotations

from harmony.tools import _documents  # noqa: PLC2701


def test_blocks_loopback_127() -> None:
    assert _documents._is_private_address("http://127.0.0.1/") is True  # type: ignore[attr-defined]


def test_blocks_loopback_localhost() -> None:
    assert _documents._is_private_address("http://localhost/") is True  # type: ignore[attr-defined]


def test_blocks_class_a_private() -> None:
    assert _documents._is_private_address("http://10.0.0.1/") is True  # type: ignore[attr-defined]


def test_blocks_class_b_private() -> None:
    assert _documents._is_private_address("http://172.16.0.1/") is True  # type: ignore[attr-defined]


def test_blocks_class_c_private() -> None:
    assert _documents._is_private_address("http://192.168.0.1/") is True  # type: ignore[attr-defined]


def test_blocks_link_local() -> None:
    assert _documents._is_private_address("http://169.254.0.1/") is True  # type: ignore[attr-defined]


def test_allows_public_ip() -> None:
    assert _documents._is_private_address("http://8.8.8.8/") is False  # type: ignore[attr-defined]


def test_blocks_on_resolution_failure() -> None:
    result = _documents._is_private_address("http://this-does-not-resolve.invalid/")  # type: ignore[attr-defined]
    assert result is True
