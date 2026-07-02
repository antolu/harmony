# ruff: noqa
from __future__ import annotations

from harmony._mod_replace import replace_modname
from .foa import (
    AgentCapability,
    AgenticOrchestrator,
    AgenticSearchResponse,
    AgentResult,
    AgentSuite,
    BaseAgent,
    CriticAgent,
    CriticTask,
    QueryPlannerAgent,
    QueryPlannerTask,
    SearcherAgent,
    SynthesizerAgent,
    SynthesizerTask,
)

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
