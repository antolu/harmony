from __future__ import annotations

import pytest

from harmony.api.agents._models import SourceDict  # noqa: PLC2701
from harmony.api.agents._source_pool import (  # noqa: PLC2701
    DEFAULT_CHAR_BUDGET,
    SourcePool,
    normalize_url,
)


def _src(url: str, score: float, content: str = "x") -> SourceDict:
    return SourceDict(title="t", url=url, content=content, score=score)


def test_normalize_url_collapses_host_slash_and_fragment() -> None:
    assert normalize_url("https://A.com/x/") == normalize_url("https://a.com/x#f")


def test_normalize_url_keeps_query() -> None:
    assert normalize_url("https://a.com/p?q=1") == "https://a.com/p?q=1"


def test_dedup_keeps_higher_score() -> None:
    pool = SourcePool()
    pool.add(_src("https://a.com/x", 0.3))
    pool.add(_src("https://A.com/x/", 0.9))
    ranked = pool.ranked()
    assert len(ranked) == 1
    assert ranked[0].score == pytest.approx(0.9)


def test_ranked_orders_by_score_desc() -> None:
    pool = SourcePool()
    pool.add_all([
        _src("https://a.com/1", 0.2),
        _src("https://a.com/2", 0.8),
        _src("https://a.com/3", 0.5),
    ])
    assert [s.url for s in pool.ranked()] == [
        "https://a.com/2",
        "https://a.com/3",
        "https://a.com/1",
    ]


def test_select_within_budget_stops_at_budget() -> None:
    pool = SourcePool()
    for i in range(100):
        pool.add(_src(f"https://a.com/{i}", 1.0 - i / 100, content="y" * 5_000))
    selected = pool.select_within_budget(total_char_budget=20_000)
    total = sum(len(s.content) for s in selected)
    assert total <= 20_000
    assert len(selected) < 100


def test_oversized_doc_is_clipped_not_dropped() -> None:
    pool = SourcePool()
    pool.add(_src("https://a.com/big", 0.9, content="z" * 1_000_000))
    selected = pool.select_within_budget(
        total_char_budget=50_000, per_source_fraction=0.4
    )
    assert len(selected) == 1
    assert len(selected[0].content) == 20_000


def test_spread_out_admits_many_small_sources() -> None:
    pool = SourcePool()
    for i in range(40):
        pool.add(_src(f"https://a.com/{i}", 1.0 - i / 100, content="w" * 1_000))
    selected = pool.select_within_budget(total_char_budget=DEFAULT_CHAR_BUDGET)
    assert len(selected) >= 30
