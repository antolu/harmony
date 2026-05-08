from __future__ import annotations

import asyncio
import json
import typing
from collections.abc import AsyncIterator
from dataclasses import dataclass

from pydantic import BaseModel

from harmony.api.agents._critic import CriticAgent
from harmony.api.agents._query_planner import QueryPlannerAgent
from harmony.api.agents._searcher import SearcherAgent
from harmony.api.agents._synthesizer import SynthesizerAgent
from harmony.api.config import settings


@dataclass
class AgentSuite:
    query_planner: QueryPlannerAgent
    searcher: SearcherAgent
    critic: CriticAgent
    synthesizer: SynthesizerAgent


class AgenticSearchResponse(BaseModel):
    answer: str
    sources: list[dict[str, typing.Any]]
    refinement_rounds: int
    query_variants: list[str]


class AgenticOrchestrator:
    def __init__(
        self,
        agents: AgentSuite,
        max_refinement_rounds: int = 3,
        max_query_variants: int = 4,
    ) -> None:
        self.query_planner = agents.query_planner
        self.searcher = agents.searcher
        self.critic = agents.critic
        self.synthesizer = agents.synthesizer
        self.max_refinement_rounds = max_refinement_rounds
        self.max_query_variants = max_query_variants

    async def search(self, user_query: str) -> AgenticSearchResponse:
        """Execute full Agentic search workflow."""
        query_variants = await self._plan_queries(user_query)
        all_results = await self._parallel_search(query_variants)
        answer, rounds = await self._refine_answer(user_query, all_results)
        return self._build_response(answer, all_results, rounds, query_variants)

    async def _plan_queries(self, user_query: str) -> list[str]:
        result = await self.query_planner.execute({"user_query": user_query})
        try:
            variants = json.loads(result.content)
            if not isinstance(variants, list):
                variants = [user_query]
        except (json.JSONDecodeError, TypeError):
            variants = [user_query]
        return variants[: self.max_query_variants]

    async def _parallel_search(
        self, query_variants: list[str]
    ) -> list[dict[str, typing.Any]]:
        search_tasks = [
            self.searcher.execute({
                "query": query,
                "top_k": settings.agentic_search_top_k,
            })
            for query in query_variants
        ]

        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        all_sources = []
        seen_urls: set[str] = set()

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
        self, user_query: str, sources: list[dict[str, typing.Any]]
    ) -> tuple[str, int]:
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

    def _build_response(
        self,
        answer: str,
        sources: list[dict[str, typing.Any]],
        rounds: int,
        query_variants: list[str],
    ) -> AgenticSearchResponse:
        return AgenticSearchResponse(
            answer=answer,
            sources=self._format_sources(sources),
            refinement_rounds=rounds,
            query_variants=query_variants,
        )

    async def stream_search(
        self, user_query: str
    ) -> AsyncIterator[dict[str, typing.Any]]:
        """Execute Agentic search workflow with streaming events."""
        try:
            query_variants = []
            async for variant in self._stream_plan_queries(user_query):
                query_variants.append(variant)
                yield {
                    "event": "query_variant",
                    "data": {"index": len(query_variants) - 1, "variant": variant},
                }

            seen_titles: set[str] = set()
            all_results: list[dict[str, typing.Any]] = []

            async for result in self._stream_parallel_search(query_variants):
                all_results.append(result)
                title = result.get("title", "Untitled")
                if title not in seen_titles:
                    seen_titles.add(title)
                    yield {
                        "event": "reading_page",
                        "data": {"title": title, "url": result.get("url", "")},
                    }

            final_answer = ""
            rounds_completed = 0

            async for event in self._stream_refine_answer(user_query, all_results):
                if event["type"] == "round_start":
                    rounds_completed = event["round"]
                    yield {
                        "event": "refinement_round",
                        "data": {"round": rounds_completed, "status": "started"},
                    }
                elif event["type"] == "round_complete":
                    yield {
                        "event": "refinement_round",
                        "data": {
                            "round": event["round"],
                            "status": "completed",
                            "consensus_reached": event.get("consensus_reached", False),
                        },
                    }
                elif event["type"] == "answer_chunk":
                    final_answer += event["content"]
                    yield {
                        "event": "answer_chunk",
                        "data": {"content": event["content"]},
                    }

            yield {
                "event": "done",
                "data": {
                    "sources": self._format_sources(all_results),
                    "refinement_rounds": rounds_completed,
                    "query_variants": query_variants,
                },
            }

        except Exception as e:
            yield {"event": "error", "data": {"message": str(e)}}

    async def _stream_plan_queries(self, user_query: str) -> AsyncIterator[str]:
        result = await self.query_planner.execute({"user_query": user_query})
        try:
            variants = json.loads(result.content)
            if not isinstance(variants, list):
                variants = [user_query]
        except (json.JSONDecodeError, TypeError):
            variants = [user_query]
        for variant in variants[: self.max_query_variants]:
            yield variant

    async def _stream_parallel_search(
        self, query_variants: list[str]
    ) -> AsyncIterator[dict[str, typing.Any]]:
        search_tasks = [
            self.searcher.execute({
                "query": query,
                "top_k": settings.agentic_search_top_k,
            })
            for query in query_variants
        ]

        seen_urls: set[str] = set()
        for coro in asyncio.as_completed(search_tasks):
            result = await coro
            if isinstance(result, BaseException):
                continue
            try:
                sources = json.loads(result.content)
                if isinstance(sources, list):
                    for source in sources:
                        url = source.get("url", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            yield source
            except (json.JSONDecodeError, TypeError):
                continue

    async def _stream_refine_answer(
        self, user_query: str, sources: list[dict[str, typing.Any]]
    ) -> AsyncIterator[dict[str, typing.Any]]:
        if not sources:
            yield {
                "type": "answer_chunk",
                "content": "No relevant sources found for this query.",
            }
            return

        draft_result = await self.synthesizer.execute({
            "sources": sources,
            "user_query": user_query,
        })
        draft = draft_result.content

        for round_num in range(self.max_refinement_rounds):
            yield {"type": "round_start", "round": round_num + 1}

            critique_result = await self.critic.execute({
                "draft": draft,
                "sources": sources,
                "user_query": user_query,
            })

            try:
                critique = json.loads(critique_result.content)
            except json.JSONDecodeError:
                critique = critique_result.metadata

            yield {
                "type": "round_complete",
                "round": round_num + 1,
                "consensus_reached": critique.get("consensus_reached", False),
            }

            if critique.get("consensus_reached", False):
                async for token in self.synthesizer.stream_execute({
                    "sources": sources,
                    "user_query": user_query,
                    "critique": critique,
                    "previous_draft": draft,
                }):
                    yield {"type": "answer_chunk", "content": token}
                return

            improved_result = await self.synthesizer.execute({
                "sources": sources,
                "user_query": user_query,
                "critique": critique,
                "previous_draft": draft,
            })
            draft = improved_result.content

        async for token in self.synthesizer.stream_execute({
            "sources": sources,
            "user_query": user_query,
        }):
            yield {"type": "answer_chunk", "content": token}

    def _format_sources(
        self, sources: list[dict[str, typing.Any]]
    ) -> list[dict[str, typing.Any]]:
        return [
            {
                "title": source.get("title", "Untitled"),
                "url": source.get("url", ""),
                "domain": source.get("domain", ""),
                "snippet": source.get("snippet", source.get("content", ""))[:300],
            }
            for source in sources[: settings.agentic_max_sources_returned]
        ]
