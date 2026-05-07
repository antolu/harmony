from __future__ import annotations

from harmony.core.parsers import CorruptDocumentError, ParserRegistry, default_registry


def test_parsers_importable_from_core() -> None:
    assert isinstance(default_registry, ParserRegistry)


def test_default_registry_has_pdf_parser() -> None:
    assert any(p.can_parse("application/pdf", ".pdf") for p in default_registry.parsers)


def test_default_registry_has_docx_parser() -> None:
    assert any(
        p.can_parse(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".docx",
        )
        for p in default_registry.parsers
    )


def test_corrupt_document_error_importable() -> None:
    assert issubclass(CorruptDocumentError, Exception)
