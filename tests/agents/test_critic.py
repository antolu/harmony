from __future__ import annotations

import dataclasses
import json
from unittest import mock

import pydantic
import pytest

from harmony.agents.foa._critic import CriticAgent
from harmony.agents.foa._models import CriticTask, CritiqueDict


def test_critique_dict_has_missing_information() -> None:
    fields = {f.name for f in dataclasses.fields(CritiqueDict)}
    assert "missing_information" in fields


def test_missing_information_defaults_empty() -> None:
    assert CritiqueDict().missing_information == []


def test_missing_information_roundtrips() -> None:
    gaps = ["It is unclear which protocol pyda uses.", "No mention of auth."]
    critique = CritiqueDict(missing_information=gaps)
    assert critique.missing_information == gaps


def test_missing_information_survives_field_filter() -> None:
    critique_fields = {f.name for f in dataclasses.fields(CritiqueDict)}
    raw: dict[str, pydantic.JsonValue] = {
        "factual_accuracy": 0.9,
        "missing_information": ["gap one"],
        "unknown_key": "ignored",
    }
    critique = CritiqueDict(**{k: v for k, v in raw.items() if k in critique_fields})
    assert critique.missing_information == ["gap one"]


def _agent_with_response(content: str) -> CriticAgent:
    llm = mock.AsyncMock()
    message = mock.Mock()
    message.content = content
    choice = mock.Mock()
    choice.message = message
    response = mock.Mock()
    response.choices = [choice]
    llm.complete.return_value = response

    prompts = mock.Mock()
    prompts.render_system_prompt.return_value = "sys"
    prompts.render_user_prompt.return_value = "usr"
    return CriticAgent(llm_service=llm, prompt_manager=prompts)


@pytest.mark.asyncio
async def test_no_consensus_without_missing_information_gets_fallback_gap() -> None:
    agent = _agent_with_response(
        json.dumps({
            "factual_accuracy": 0.5,
            "completeness": 0.5,
            "hallucination_risk": 0.1,
            "issues": ["The answer is too vague."],
            "suggestions": ["Add more detail."],
            "consensus_reached": False,
            "missing_information": [],
        })
    )
    task = CriticTask(draft="draft", sources=[], user_query="q")
    result = await agent.execute(task, mock.Mock())
    parsed = json.loads(result.content)
    assert parsed["missing_information"] == ["The answer is too vague."]


@pytest.mark.asyncio
async def test_no_consensus_with_missing_information_is_untouched() -> None:
    agent = _agent_with_response(
        json.dumps({
            "factual_accuracy": 0.5,
            "completeness": 0.5,
            "hallucination_risk": 0.1,
            "issues": [],
            "suggestions": [],
            "consensus_reached": False,
            "missing_information": ["It is unclear which protocol pyda uses."],
        })
    )
    task = CriticTask(draft="draft", sources=[], user_query="q")
    result = await agent.execute(task, mock.Mock())
    parsed = json.loads(result.content)
    assert parsed["missing_information"] == ["It is unclear which protocol pyda uses."]


@pytest.mark.asyncio
async def test_consensus_reached_does_not_get_fallback_gap() -> None:
    agent = _agent_with_response(
        json.dumps({
            "factual_accuracy": 0.9,
            "completeness": 0.9,
            "hallucination_risk": 0.05,
            "issues": [],
            "suggestions": [],
            "consensus_reached": True,
            "missing_information": [],
        })
    )
    task = CriticTask(draft="draft", sources=[], user_query="q")
    result = await agent.execute(task, mock.Mock())
    parsed = json.loads(result.content)
    assert parsed["missing_information"] == []
