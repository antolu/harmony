from __future__ import annotations

import inspect

import pytest

from harmony.tools import _documents as documents  # noqa: PLC2701
from harmony.tools._documents import FetchDocumentTool  # noqa: PLC2701


def test_no_dead_bytesio_call() -> None:
    """io.BytesIO must not be called with a discarded result."""
    source = inspect.getsource(documents)
    assert "io.BytesIO(response.content)" not in source


def test_io_not_imported() -> None:
    """io module must not be imported since it has no remaining uses."""
    source = inspect.getsource(documents)
    assert "import io\n" not in source


@pytest.mark.parametrize(
    ("content_type", "extension", "expected"),
    [
        ("application/pdf", ".pdf", "pdf"),
        ("", ".pdf", "pdf"),
        ("application/pdf", ".txt", "pdf"),
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".docx",
            "docx",
        ),
        ("application/vnd.ms-word", ".doc", "docx"),
        (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xlsx",
            "xlsx",
        ),
        ("application/vnd.ms-excel", ".xls", "xlsx"),
        ("application/vnd.oasis.opendocument.text", ".odt", "odt"),
        ("", ".md", "markdown"),
        ("", ".markdown", "markdown"),
        ("text/markdown", ".txt", "markdown"),
        ("text/plain", ".txt", "txt"),
        ("text/csv", ".csv", "csv"),
        ("", ".unknown", "unknown"),
        ("application/octet-stream", ".bin", "unknown"),
    ],
)
def test_detect_document_type(content_type: str, extension: str, expected: str) -> None:
    assert FetchDocumentTool._detect_document_type(content_type, extension) == expected
