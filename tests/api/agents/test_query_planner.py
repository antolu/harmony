from __future__ import annotations

import json
from unittest import mock

import pytest

from harmony.api.agents._models import QueryPlannerTask  # noqa: PLC2701
from harmony.api.agents._query_planner import QueryPlannerAgent  # noqa: PLC2701


def _agent_with_response(content: str | None) -> QueryPlannerAgent:
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
    return QueryPlannerAgent(llm_service=llm, prompt_manager=prompts)


@pytest.mark.asyncio
async def test_planner_emits_object_shape() -> None:
    agent = _agent_with_response(
        json.dumps({
            "semantic_query": "How does pyda access CERN devices?",
            "keyword_variants": ["pyda CERN device", "pyda controls"],
        })
    )
    result = await agent.execute(QueryPlannerTask(user_query="pyda?"), mock.Mock())
    parsed = json.loads(result.content)
    assert parsed["semantic_query"] == "How does pyda access CERN devices?"
    assert parsed["keyword_variants"] == ["pyda CERN device", "pyda controls"]


@pytest.mark.asyncio
async def test_planner_fallback_on_non_object() -> None:
    agent = _agent_with_response(json.dumps(["just", "an", "array"]))
    result = await agent.execute(QueryPlannerTask(user_query="my query"), mock.Mock())
    parsed = json.loads(result.content)
    assert parsed == {"semantic_query": "my query", "keyword_variants": ["my query"]}
    assert result.metadata.get("fallback") is True


@pytest.mark.asyncio
async def test_planner_fallback_on_empty_content() -> None:
    agent = _agent_with_response(None)
    result = await agent.execute(QueryPlannerTask(user_query="q"), mock.Mock())
    parsed = json.loads(result.content)
    assert parsed == {"semantic_query": "q", "keyword_variants": ["q"]}


@pytest.mark.asyncio
async def test_planner_caps_variants() -> None:
    agent = _agent_with_response(
        json.dumps({
            "semantic_query": "s",
            "keyword_variants": ["a", "b", "c", "d", "e", "f"],
        })
    )
    result = await agent.execute(QueryPlannerTask(user_query="q"), mock.Mock())
    parsed = json.loads(result.content)
    assert len(parsed["keyword_variants"]) == 4
