from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from harmony.api.agents.critic import CriticAgent
from harmony.api.agents.orchestrator import AgenticOrchestrator, AgenticSearchResponse
from harmony.api.agents.query_planner import QueryPlannerAgent
from harmony.api.agents.searcher import SearcherAgent
from harmony.api.agents.synthesizer import SynthesizerAgent
from harmony.api.config import settings
from harmony.api.services.elasticsearch import es_service
from harmony.api.services.llm import llm_service

router = APIRouter(tags=["agentic-search"])


class AgenticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User's search query")
    max_refinement_rounds: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum number of critic-synthesizer refinement rounds",
    )


_orchestrator: AgenticOrchestrator | None = None


def get_orchestrator() -> AgenticOrchestrator:
    """Get or create the Agentic orchestrator singleton."""
    global _orchestrator  # noqa: PLW0603
    if _orchestrator is None:
        query_planner = QueryPlannerAgent(llm_service)
        searcher = SearcherAgent(es_service)
        critic = CriticAgent(llm_service)
        synthesizer = SynthesizerAgent(llm_service)

        _orchestrator = AgenticOrchestrator(
            query_planner=query_planner,
            searcher=searcher,
            critic=critic,
            synthesizer=synthesizer,
            max_refinement_rounds=settings.agentic_max_refinement_rounds,
            max_query_variants=settings.agentic_max_query_variants,
        )

    return _orchestrator


@router.post("/agentic-search", response_model=AgenticSearchResponse)
async def agentic_search(request: AgenticSearchRequest) -> AgenticSearchResponse:
    """Multi-agent search with k-round refinement.

    This endpoint implements the Agentic Search architecture for
    AI-powered search:

    1. Query Planning: Decomposes user query into 2-4 search variants
    2. Parallel Search: Executes all variants concurrently
    3. K-Round Refinement: Iterative critic-synthesizer loop (default k=3)
    4. Final Answer: Returns synthesized answer with sources

    Args:
        request: Agentic search request with query and optional parameters

    Returns:
        AgenticSearchResponse with answer, sources, refinement stats
    """
    orchestrator = get_orchestrator()

    if hasattr(orchestrator, "max_refinement_rounds"):
        orchestrator.max_refinement_rounds = request.max_refinement_rounds

    return await orchestrator.search(request.query)
