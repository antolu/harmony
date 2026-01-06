from __future__ import annotations

import asyncio
import json
from typing import Any

from pydantic import BaseModel

from harmony.api.agents.critic import CriticAgent
from harmony.api.agents.query_planner import QueryPlannerAgent
from harmony.api.agents.searcher import SearcherAgent
from harmony.api.agents.synthesizer import SynthesizerAgent
from harmony.api.config import settings


class AgenticSearchResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]]
    refinement_rounds: int
    query_variants: list[str]


class AgenticOrchestrator:
    def __init__(  # noqa: PLR0913, PLR0917
        self,
        query_planner: QueryPlannerAgent,
        searcher: SearcherAgent,
        critic: CriticAgent,
        synthesizer: SynthesizerAgent,
        max_refinement_rounds: int = 3,
        max_query_variants: int = 4,
    ) -> None:
        self.query_planner = query_planner
        self.searcher = searcher
        self.critic = critic
        self.synthesizer = synthesizer
        self.max_refinement_rounds = max_refinement_rounds
        self.max_query_variants = max_query_variants

    async def search(self, user_query: str) -> AgenticSearchResponse:
        """Execute full Agentic search workflow."""
        query_variants = await self._plan_queries(user_query)

        all_results = await self._parallel_search(query_variants)

        answer, rounds = await self._refine_answer(user_query, all_results)

        return self._build_response(answer, all_results, rounds, query_variants)

    async def _plan_queries(self, user_query: str) -> list[str]:
        """Phase 1: Query planning."""
        result = await self.query_planner.execute({"user_query": user_query})

        try:
            variants = json.loads(result.content)
            if not isinstance(variants, list):
                variants = [user_query]
        except (json.JSONDecodeError, TypeError):
            variants = [user_query]

        return variants[: self.max_query_variants]

    async def _parallel_search(self, query_variants: list[str]) -> list[dict[str, Any]]:
        """Phase 2: Parallel search execution."""
        search_tasks = [
            self.searcher.execute({
                "query": query,
                "top_k": settings.agentic_search_top_k,
            })
            for query in query_variants
        ]

        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        all_sources = []
        seen_urls = set()

        for result in results:
            if isinstance(result, BaseException):
                continue

            try:
                sources = json.loads(result.content)
                if isinstance(sources, list):
                    for source in sources:
                        url = source.get("url", "")
                        if url and url not in seen_urls:
                            all_sources.append(source)
                            seen_urls.add(url)
            except (json.JSONDecodeError, TypeError):
                continue

        return all_sources

    async def _refine_answer(
        self, user_query: str, sources: list[dict[str, Any]]
    ) -> tuple[str, int]:
        """Phase 3: K-round refinement with critic feedback."""
        if not sources:
            return "No relevant sources found for this query.", 0

        draft_result = await self.synthesizer.execute({
            "sources": sources,
            "user_query": user_query,
        })
        draft = draft_result.content

        for round_num in range(self.max_refinement_rounds):
            critique_result = await self.critic.execute({
                "draft": draft,
                "sources": sources,
                "user_query": user_query,
            })

            try:
                critique = json.loads(critique_result.content)
            except json.JSONDecodeError:
                critique = critique_result.metadata

            if critique.get("consensus_reached", False):
                return draft, round_num + 1

            improved_result = await self.synthesizer.execute({
                "sources": sources,
                "user_query": user_query,
                "critique": critique,
                "previous_draft": draft,
            })
            draft = improved_result.content

        return draft, self.max_refinement_rounds

    def _build_response(  # noqa: PLR6301
        self,
        answer: str,
        sources: list[dict[str, Any]],
        rounds: int,
        query_variants: list[str],
    ) -> AgenticSearchResponse:
        """Phase 4: Build final response."""
        formatted_sources = [
            {
                "title": source.get("title", "Untitled"),
                "url": source.get("url", ""),
                "domain": source.get("domain", ""),
                "snippet": source.get("snippet", source.get("content", ""))[:300],
            }
            for source in sources[: settings.agentic_max_sources_returned]
        ]

        return AgenticSearchResponse(
            answer=answer,
            sources=formatted_sources,
            refinement_rounds=rounds,
            query_variants=query_variants,
        )
