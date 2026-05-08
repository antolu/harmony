from __future__ import annotations

import inspect

from harmony.api.tools import _documents as documents  # noqa: PLC2701


def test_no_dead_bytesio_call() -> None:
    """io.BytesIO must not be called with a discarded result."""
    source = inspect.getsource(documents)
    assert "io.BytesIO(response.content)" not in source


def test_io_not_imported() -> None:
    """io module must not be imported since it has no remaining uses."""
    source = inspect.getsource(documents)
    assert "import io\n" not in source
