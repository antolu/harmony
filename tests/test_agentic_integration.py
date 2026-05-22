from __future__ import annotations

import pytest


@pytest.mark.skip(reason="not implemented — will be implemented in later plan")
def test_agent_step_attribution_preserved_through_chain() -> None:
    """TOKEN-03: Agentic search passes agent_step metadata through query_planner, critic, and synthesizer LLMService calls so token_usage rows can be attributed per agent."""
