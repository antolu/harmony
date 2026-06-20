from __future__ import annotations

from unittest.mock import MagicMock

from harmony.api.agents import CriticAgent, QueryPlannerAgent, SynthesizerAgent
from harmony.api.agents._models import (  # noqa: PLC2701
    CriticTask,
    QueryPlannerTask,
    SynthesizerTask,
)


def _make_prompt_manager() -> MagicMock:
    pm = MagicMock()
    pm.render_system_prompt.return_value = "system"
    pm.render_user_prompt.return_value = "user"
    return pm


def _make_llm_service(content: str) -> tuple[MagicMock, list[dict]]:
    captured: list[dict] = []
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = content

    async def _complete(messages: list, **kwargs: object) -> MagicMock:
        captured.append(dict(kwargs))
        return mock_resp

    svc = MagicMock()
    svc.complete = _complete
    return svc, captured


async def test_agent_step_attribution_preserved_through_chain() -> None:
    """TOKEN-03: Each agent passes agent_step to LLMService.complete."""
    pm = _make_prompt_manager()

    planner_svc, planner_calls = _make_llm_service('["variant"]')
    planner = QueryPlannerAgent(llm_service=planner_svc, prompt_manager=pm)
    await planner.execute(QueryPlannerTask(user_query="test"))  # type: ignore
    assert any(
        c.get("ctx") and getattr(c.get("ctx"), "agent_step", None) == "query_planner"
        for c in planner_calls
    )  # type: ignore

    critic_content = '{"factual_accuracy": 0.9, "completeness": 0.9, "hallucination_risk": 0.1, "issues": [], "suggestions": [], "consensus_reached": true}'
    critic_svc, critic_calls = _make_llm_service(critic_content)
    critic = CriticAgent(llm_service=critic_svc, prompt_manager=pm)
    await critic.execute(
        CriticTask(draft="draft answer", user_query="test", sources=[])
    )  # type: ignore
    assert any(
        c.get("ctx") and getattr(c.get("ctx"), "agent_step", None) == "critic"
        for c in critic_calls
    )  # type: ignore

    synth_svc, synth_calls = _make_llm_service("synthesized answer")
    synth = SynthesizerAgent(llm_service=synth_svc, prompt_manager=pm)
    await synth.execute(
        SynthesizerTask(
            sources=[{"url": "source1", "title": "test", "content": "test"}],
            user_query="test",
        )
    )  # type: ignore
    assert any(
        c.get("ctx") and getattr(c.get("ctx"), "agent_step", None) == "synthesizer"
        for c in synth_calls
    )  # type: ignore
