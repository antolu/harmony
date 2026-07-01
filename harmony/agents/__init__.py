# ruff: noqa
from __future__ import annotations

from harmony._mod_replace import replace_modname
from harmony.agents._base import AgentCapability, AgentResult, BaseAgent
from harmony.agents._critic import CriticAgent
from harmony.agents._models import CriticTask, QueryPlannerTask, SynthesizerTask
from harmony.agents._orchestrator import (
    AgenticOrchestrator,
    AgenticSearchResponse,
    AgentSuite,
)
from harmony.agents._query_planner import QueryPlannerAgent
from harmony.agents._searcher import SearcherAgent
from harmony.agents._synthesizer import SynthesizerAgent

replace_modname(AgentCapability, __name__)
replace_modname(AgentResult, __name__)
replace_modname(AgenticOrchestrator, __name__)
replace_modname(AgenticSearchResponse, __name__)
replace_modname(AgentSuite, __name__)
replace_modname(BaseAgent, __name__)
replace_modname(CriticAgent, __name__)
replace_modname(CriticTask, __name__)
replace_modname(QueryPlannerAgent, __name__)
replace_modname(QueryPlannerTask, __name__)
replace_modname(SearcherAgent, __name__)
replace_modname(SynthesizerAgent, __name__)
replace_modname(SynthesizerTask, __name__)

__all__ = [
    "AgentCapability",
    "AgentResult",
    "AgentSuite",
    "AgenticOrchestrator",
    "AgenticSearchResponse",
    "BaseAgent",
    "CriticAgent",
    "CriticTask",
    "QueryPlannerAgent",
    "QueryPlannerTask",
    "SearcherAgent",
    "SynthesizerAgent",
    "SynthesizerTask",
]
