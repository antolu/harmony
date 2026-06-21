from __future__ import annotations

import logging
from pathlib import Path

import pydantic

from harmony.core import StatsWriter, language_detector

from ._core import extract_text_from_html, process_document, publish_stats

logger = logging.getLogger(__name__)


def detect_languages_if_missing(
    all_entries: list[dict[str, pydantic.JsonValue]],
    stats_writer: StatsWriter | None = None,
    total_documents: int = 0,
) -> None:
    missing_count = sum(1 for e in all_entries if not e.get("language"))
    if missing_count == 0:
        return

    logger.info("detecting language for %d documents...", missing_count)

    detected = 0
    for entry in all_entries:
        if entry.get("language"):
            continue

        base_dir_val = entry.get("_base_dir")
        if not base_dir_val:
            continue

        file_path_val = entry.get("file_path")
        if not file_path_val:
            continue

        file_path = Path(str(base_dir_val)) / str(file_path_val)

        if not file_path.exists():
            continue

        doc_type = entry.get("type", "html")
        content = None

        if doc_type == "document":
            _, content = process_document(entry, file_path)
        else:
            try:
                html = file_path.read_bytes()
                _, content = extract_text_from_html(html)
            except Exception:
                logger.exception("failed to extract text from %s", file_path)

        if content:
            lang = language_detector.detect_language(content)
            if lang:
                entry["language"] = lang

        detected += 1
        if detected % 10 == 0:
            publish_stats(
                stats_writer,
                phase="language_detection",
                indexed=detected,
                total=total_documents,
            )
