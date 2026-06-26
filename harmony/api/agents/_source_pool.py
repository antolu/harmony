from __future__ import annotations

import dataclasses
import urllib.parse
from collections.abc import Iterable

from harmony.api.agents._models import SourceDict

DEFAULT_CHAR_BUDGET = 50_000
DEFAULT_PER_SOURCE_FRACTION = 0.4


def normalize_url(url: str) -> str:
    """Normalize a URL for dedup: lowercase host, strip trailing slash + fragment.

    Keeps the query string. Used both for pool dedup and cross-round merge so the
    same document under slightly different paths collapses to one key.
    """
    if not url:
        return ""
    parts = urllib.parse.urlsplit(url)
    host = parts.netloc.lower()
    path = parts.path.rstrip("/")
    return urllib.parse.urlunsplit((parts.scheme.lower(), host, path, parts.query, ""))


@dataclasses.dataclass
class _PoolEntry:
    source: SourceDict
    score: float
    seen_count: int = 1


class SourcePool:
    """Score-ranked, normalized-URL-deduped pool of sources feeding a char budget.

    The pool is the single place agentic search accumulates sources. It dedupes by
    normalized URL (keeping the higher score), orders by score, and selects the
    highest-ranked sources that fit a total character budget — so the budget, not a
    fixed source count, governs what reaches the synthesizer and critic.
    """

    def __init__(self) -> None:
        self._entries: dict[str, _PoolEntry] = {}

    def add(self, source: SourceDict) -> None:
        key = normalize_url(source.url)
        existing = self._entries.get(key)
        if existing is None or source.score > existing.score:
            self._entries[key] = _PoolEntry(source=source, score=source.score)

    def add_all(self, sources: Iterable[SourceDict]) -> None:
        for source in sources:
            self.add(source)

    def ranked(self) -> list[SourceDict]:
        entries = sorted(self._entries.values(), key=lambda e: e.score, reverse=True)
        return [e.source for e in entries]

    def select_within_budget(
        self,
        total_char_budget: int = DEFAULT_CHAR_BUDGET,
        per_source_fraction: float = DEFAULT_PER_SOURCE_FRACTION,
    ) -> list[SourceDict]:
        per_source_cap = int(total_char_budget * per_source_fraction)
        selected: list[SourceDict] = []
        used = 0
        for source in self.ranked():
            content = source.content or source.snippet or ""
            clipped = content[:per_source_cap]
            if selected and used + len(clipped) > total_char_budget:
                break
            selected.append(dataclasses.replace(source, content=clipped))
            used += len(clipped)
        return selected
