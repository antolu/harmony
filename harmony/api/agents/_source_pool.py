from __future__ import annotations

import dataclasses
import urllib.parse
from collections.abc import Iterable

from harmony.api.agents._models import Source

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


DEFAULT_CONSENSUS_BOOST = 0.05


@dataclasses.dataclass
class _PoolEntry:
    source: Source
    score: float
    seen_count: int = 1
    effective_score: float = 0.0

    def __post_init__(self) -> None:
        if not self.effective_score:
            self.effective_score = self.score


class SourcePool:
    """Score-ranked, normalized-URL-deduped pool of sources feeding a char budget.

    The pool is the single place agentic search accumulates sources. It dedupes by
    normalized URL (keeping the higher score), orders by score, and selects the
    highest-ranked sources that fit a total character budget — so the budget, not a
    fixed source count, governs what reaches the synthesizer and critic.
    """

    def __init__(self) -> None:
        self._entries: dict[str, _PoolEntry] = {}

    def add(self, source: Source) -> None:
        key = normalize_url(source.url)
        existing = self._entries.get(key)
        if existing is None or source.score > existing.score:
            self._entries[key] = _PoolEntry(source=source, score=source.score)

    def add_all(self, sources: Iterable[Source]) -> None:
        for source in sources:
            self.add(source)

    def ranked(self) -> list[Source]:
        entries = sorted(
            self._entries.values(), key=lambda e: e.effective_score, reverse=True
        )
        return [e.source for e in entries]

    def merge_round(
        self,
        sources: list[Source],
        *,
        consensus_boost: float = DEFAULT_CONSENSUS_BOOST,
    ) -> None:
        """Merge a later refinement round's search results into the pool.

        Cross-round scoring is genuinely hard and this is a deliberate, imperfect
        resolution. Reranker/cross-encoder scores are QUERY-RELATIVE: a 0.8 against
        round 2's refined query is not the same relevance as a 0.8 against round 1's
        query, so raw scores from different rounds are NOT directly comparable. We
        therefore min-max normalize each round's scores to 0-1 before merging. On a
        duplicate (same normalized URL) we take the LATEST round's normalized score,
        not the max, because the latest refined query is the most context-aware probe
        and a re-surfaced source is itself a relevance signal. We deliberately do NOT
        anchor scoring to the original user query: it was issued before any source
        context existed (uninformed), whereas the refined per-round queries better
        capture what relevance means at that point. A small consensus boost rewards
        sources that surface across multiple rounds.
        """
        if not sources:
            return
        scores = [s.score for s in sources]
        lo, hi = min(scores), max(scores)
        span = hi - lo
        for source in sources:
            norm = 1.0 if span == 0 else (source.score - lo) / span
            key = normalize_url(source.url)
            existing = self._entries.get(key)
            if existing is None:
                entry = _PoolEntry(
                    source=source, score=norm, seen_count=1, effective_score=norm
                )
                self._entries[key] = entry
            else:
                existing.score = norm
                existing.seen_count += 1
                existing.source = source
                existing.effective_score = norm + consensus_boost * (
                    existing.seen_count - 1
                )

    def select_within_budget(
        self,
        total_char_budget: int = DEFAULT_CHAR_BUDGET,
        per_source_fraction: float = DEFAULT_PER_SOURCE_FRACTION,
    ) -> list[Source]:
        per_source_cap = int(total_char_budget * per_source_fraction)
        selected: list[Source] = []
        used = 0
        for source in self.ranked():
            content = source.content or source.snippet or ""
            clipped = content[:per_source_cap]
            if selected and used + len(clipped) > total_char_budget:
                break
            selected.append(source.model_copy(update={"content": clipped}))
            used += len(clipped)
        return selected
