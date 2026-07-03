from __future__ import annotations

import json
from unittest import mock

import pytest

from harmony.agents.foa._base import AgentResult
from harmony.agents.foa._orchestrator import (
    AgenticOrchestrator,
    AgentSuite,
)


def _result(content: str) -> AgentResult:
    return AgentResult(content=content, metadata={}, confidence=1.0)


def _planner_result() -> AgentResult:
    return _result(
        json.dumps({"semantic_query": "sem", "keyword_variants": ["kw1", "kw2"]})
    )


def _search_result(urls: list[str]) -> AgentResult:
    return _result(
        json.dumps([
            {"title": f"t{u}", "url": u, "content": "c" * 100, "score": 1.0}
            for u in urls
        ])
    )


def _critique(*, consensus: bool, missing: list[str] | None = None) -> AgentResult:
    return _result(
        json.dumps({
            "factual_accuracy": 0.9,
            "completeness": 0.9,
            "hallucination_risk": 0.1,
            "issues": [],
            "suggestions": [],
            "consensus_reached": consensus,
            "missing_information": missing or [],
        })
    )


def _make_orchestrator(
    *, search_results: list[AgentResult], critiques: list[AgentResult]
) -> tuple[AgenticOrchestrator, dict[str, mock.AsyncMock]]:
    planner = mock.Mock()
    planner.execute = mock.AsyncMock(return_value=_planner_result())
    searcher = mock.Mock()
    searcher.execute = mock.AsyncMock(side_effect=search_results)
    critic = mock.Mock()
    critic.execute = mock.AsyncMock(side_effect=critiques)
    synthesizer = mock.Mock()
    synthesizer.execute = mock.AsyncMock(return_value=_result("draft answer"))

    suite = AgentSuite(
        query_planner=planner,
        searcher=searcher,
        critic=critic,
        synthesizer=synthesizer,
    )
    orch = AgenticOrchestrator(suite, max_refinement_rounds=3)
    return orch, {
        "planner": planner.execute,
        "searcher": searcher.execute,
        "critic": critic.execute,
        "synthesizer": synthesizer.execute,
    }


@pytest.mark.asyncio
async def test_consensus_round_one_runs_no_followup_search() -> None:
    orch, mocks = _make_orchestrator(
        search_results=[_search_result(["https://a/1", "https://a/2"])],
        critiques=[_critique(consensus=True)],
    )
    await orch.search("q")
    # only the initial combined search ran — no follow-up
    assert mocks["searcher"].await_count == 1


@pytest.mark.asyncio
async def test_non_consensus_with_gaps_triggers_followup_search() -> None:
    orch, mocks = _make_orchestrator(
        search_results=[
            _search_result(["https://a/1"]),
            _search_result(["https://a/2", "https://a/3"]),
        ],
        critiques=[
            _critique(consensus=False, missing=["need more on X"]),
            _critique(consensus=True),
        ],
    )
    await orch.search("q")
    # initial search + one follow-up search
    assert mocks["searcher"].await_count == 2


@pytest.mark.asyncio
async def test_non_consensus_without_gaps_does_not_search_again() -> None:
    orch, mocks = _make_orchestrator(
        search_results=[_search_result(["https://a/1"])],
        critiques=[
            _critique(consensus=False, missing=[]),
            _critique(consensus=True),
        ],
    )
    await orch.search("q")
    assert mocks["searcher"].await_count == 1


@pytest.mark.asyncio
async def test_synth_and_critic_get_same_budgeted_sources() -> None:
    orch, mocks = _make_orchestrator(
        search_results=[_search_result(["https://a/1", "https://a/2"])],
        critiques=[_critique(consensus=True)],
    )
    await orch.search("q")
    synth_task = mocks["synthesizer"].await_args_list[0].args[0]
    critic_task = mocks["critic"].await_args_list[0].args[0]
    synth_urls = [s.url for s in synth_task.sources]
    critic_urls = [s.url for s in critic_task.sources]
    assert synth_urls == critic_urls


@pytest.mark.asyncio
async def test_one_combined_search_per_round() -> None:
    orch, mocks = _make_orchestrator(
        search_results=[
            _search_result(["https://a/1"]),
            _search_result(["https://a/2"]),
            _search_result(["https://a/3"]),
        ],
        critiques=[
            _critique(consensus=False, missing=["g1"]),
            _critique(consensus=False, missing=["g2"]),
            _critique(consensus=True),
        ],
    )
    await orch.search("q")
    # initial + 2 follow-ups (one per non-consensus round with gaps)
    assert mocks["searcher"].await_count == 3
    # the planner is re-invoked for each follow-up (initial + 2)
    assert mocks["planner"].await_count == 3
