from __future__ import annotations

import typing

from harmony.agents import (
    AgenticOrchestrator,
    AgentSuite,
    CriticAgent,
    QueryPlannerAgent,
    SearcherAgent,
    SynthesizerAgent,
)

if typing.TYPE_CHECKING:
    from harmony.services import (
        LLMService,
        PipelineConfig,
        PromptManager,
        SearchService,
    )


def init_orchestrator(
    llm_service: LLMService,
    prompt_manager: PromptManager,
    search_service: SearchService,
    pipeline_config: PipelineConfig,
) -> AgenticOrchestrator:
    agents = AgentSuite(
        query_planner=QueryPlannerAgent(
            llm_service=llm_service, prompt_manager=prompt_manager
        ),
        searcher=SearcherAgent(search_service=search_service),
        critic=CriticAgent(llm_service=llm_service, prompt_manager=prompt_manager),
        synthesizer=SynthesizerAgent(
            llm_service=llm_service, prompt_manager=prompt_manager
        ),
    )
    return AgenticOrchestrator(
        agents=agents,
        max_refinement_rounds=pipeline_config.agentic_max_refinement_rounds,
        max_query_variants=pipeline_config.agentic_max_query_variants,
        agentic_max_sources_returned=pipeline_config.agentic_max_sources_returned,
        agentic_search_top_k=pipeline_config.agentic_search_top_k,
    )
