from __future__ import annotations

import pytest

from harmony.agents._source_pool import (
    DEFAULT_CHAR_BUDGET,
    SourcePool,
    normalize_url,
)
from harmony.models import Source


def _src(url: str, score: float, content: str = "x") -> Source:
    return Source(title="t", url=url, content=content, score=score)


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


def test_merge_round_normalizes_and_ranks_new_source() -> None:
    pool = SourcePool()
    pool.merge_round([
        _src("https://a.com/1", 10.0),
        _src("https://a.com/2", 30.0),
    ])
    # raw scores differ but normalization puts the higher one on top
    assert [s.url for s in pool.ranked()] == ["https://a.com/2", "https://a.com/1"]


def test_merge_round_takes_latest_not_max_on_collision() -> None:
    pool = SourcePool()
    # round 1: url X normalizes to 1.0 (top of its round)
    pool.merge_round([_src("https://a.com/x", 100.0), _src("https://a.com/y", 0.0)])
    # round 2: url X is the LOW end (normalizes to 0.0), not the max
    pool.merge_round([_src("https://a.com/x", 0.0), _src("https://a.com/z", 100.0)])
    entry = pool._entries[normalize_url("https://a.com/x")]
    # take-latest: round-2 normalized score (0.0) + consensus boost for seen twice
    assert entry.score == pytest.approx(0.0)
    assert entry.seen_count == 2
    assert entry.effective_score == pytest.approx(0.05)


def test_merge_round_all_equal_scores_no_zero_division() -> None:
    pool = SourcePool()
    pool.merge_round([
        _src("https://a.com/1", 5.0),
        _src("https://a.com/2", 5.0),
    ])
    assert len(pool.ranked()) == 2


def test_merge_round_consensus_boost_orders_multi_round_source() -> None:
    pool = SourcePool()
    pool.merge_round([_src("https://a.com/shared", 1.0), _src("https://a.com/r1", 0.0)])
    pool.merge_round([_src("https://a.com/shared", 1.0), _src("https://a.com/r2", 1.0)])
    # 'shared' seen twice gets norm 1.0 + boost; ranks at/above single-round 1.0s
    assert pool.ranked()[0].url == "https://a.com/shared"
