from __future__ import annotations

import inspect

import harmony.indexer.cli as cli_module


def test_stats_writer_return_value_is_used() -> None:
    """_make_stats_writer() result must be assigned and not discarded."""
    source = inspect.getsource(cli_module)
    bare_lines = [
        line.strip()
        for line in source.splitlines()
        if "_make_stats_writer()" in line
        and not line.strip().startswith("def ")
        and "=" not in line
    ]
    assert not bare_lines, (
        f"_make_stats_writer() return value is discarded on lines: {bare_lines}"
    )


def test_stats_writer_passed_to_detect_languages() -> None:
    """_detect_languages_if_missing must receive stats_writer."""
    source = inspect.getsource(cli_module)
    assert "_detect_languages_if_missing(all_entries, console, stats_writer" in source


def test_stats_writer_passed_to_bulk_indexing() -> None:
    """_perform_bulk_indexing must receive stats_writer."""
    source = inspect.getsource(cli_module)
    idx = source.find("success_count, error_count = _perform_bulk_indexing(")
    assert idx != -1
    call_block = source[idx : idx + 300]
    assert "stats_writer" in call_block
