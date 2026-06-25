from __future__ import annotations

import asyncio
import dataclasses
import json
import typing
from collections.abc import AsyncIterator

import pydantic
from pydantic import BaseModel

from harmony.api.agents._base import AgentResult
from harmony.api.agents._critic import CriticAgent
from harmony.api.agents._models import (
    CriticTask,
    CritiqueDict,
    QueryPlannerTask,
    SearcherTask,
    SourceDict,
    SynthesizerTask,
)
from harmony.api.agents._query_planner import QueryPlannerAgent
from harmony.api.agents._searcher import SearcherAgent
from harmony.api.agents._synthesizer import SynthesizerAgent
from harmony.api.authz import AuthorizationContext
from harmony.api.services import null_sink

_SOURCE_FIELDS = {f.name for f in dataclasses.fields(SourceDict)}
_CRITIQUE_FIELDS = {f.name for f in dataclasses.fields(CritiqueDict)}

if typing.TYPE_CHECKING:
    from harmony.api.services._external_search import ExternalSearchContext


@dataclasses.dataclass
class AgentSuite:
    query_planner: QueryPlannerAgent
    searcher: SearcherAgent
    critic: CriticAgent
    synthesizer: SynthesizerAgent


class AgenticSearchResponse(BaseModel):
    answer: str
    sources: list[SourceDict]
    refinement_rounds: int
    query_variants: list[str]


class AgenticOrchestrator:
    def __init__(
        self,
        agents: AgentSuite,
        max_refinement_rounds: int = 3,
        max_query_variants: int = 4,
        agentic_search_top_k: int = 10,
        agentic_max_sources_returned: int = 10,
    ) -> None:
        self.query_planner = agents.query_planner
        self.searcher = agents.searcher
        self.critic = agents.critic
        self.synthesizer = agents.synthesizer
        self.max_refinement_rounds = max_refinement_rounds
        self.max_query_variants = max_query_variants
        self.agentic_search_top_k = agentic_search_top_k
        self.agentic_max_sources_returned = agentic_max_sources_returned

    async def search(
        self,
        user_query: str,
        authz_context: AuthorizationContext | None = None,
        external_context: ExternalSearchContext | None = None,
        max_refinement_rounds: int | None = None,
        sources: list[str] | None = None,
    ) -> AgenticSearchResponse:
        """Execute full Agentic search workflow."""
        query_variants = await self._plan_queries(user_query)
        all_results = await self._parallel_search(
            query_variants, authz_context, external_context, sources
        )
        answer, rounds = await self._refine_answer(
            user_query, all_results, max_refinement_rounds=max_refinement_rounds
        )
        return self._build_response(answer, all_results, rounds, query_variants)

    async def _plan_queries(self, user_query: str) -> list[str]:
        result = await self.query_planner.execute(
            QueryPlannerTask(user_query=user_query), null_sink
        )
        try:
            variants = json.loads(result.content)
            if not isinstance(variants, list):
                variants = [user_query]
        except (json.JSONDecodeError, TypeError):
            variants = [user_query]
        return variants[: self.max_query_variants]

    async def _parallel_search(
        self,
        query_variants: list[str],
        authz_context: AuthorizationContext | None = None,
        external_context: ExternalSearchContext | None = None,
        sources: list[str] | None = None,
    ) -> list[SourceDict]:

        search_tasks = [
            self.searcher.execute(
                SearcherTask(
                    query=query,
                    top_k=self.agentic_search_top_k,
                    authz_context=authz_context,
                    external_context=external_context,
                    sources=sources,
                ),
                null_sink,
            )
            for query in query_variants
        ]

        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        all_sources: list[SourceDict] = []
        seen_urls: set[str] = set()

        for result in results:
            if isinstance(result, BaseException):
                continue
            self._collect_sources(result, all_sources, seen_urls)

        return all_sources

    def _collect_sources(
        self,
        result: AgentResult,
        all_sources: list[SourceDict],
        seen_urls: set[str],
    ) -> None:
        try:
            sources = json.loads(result.content)
        except (json.JSONDecodeError, TypeError):
            return
        if isinstance(sources, list):
            for source in sources:
                url = source.get("url", "")
                if url and url not in seen_urls:
                    all_sources.append(
                        SourceDict(**{
                            k: v for k, v in source.items() if k in _SOURCE_FIELDS
                        })
                    )
                    seen_urls.add(url)

    async def _refine_answer(
        self,
        user_query: str,
        sources: list[SourceDict],
        *,
        max_refinement_rounds: int | None = None,
    ) -> tuple[str, int]:
        if not sources:
            return "No relevant sources found for this query.", 0

        draft_result = await self.synthesizer.execute(
            SynthesizerTask(
                sources=sources,
                user_query=user_query,
            ),
            null_sink,
        )
        draft = draft_result.content

        rounds = (
            max_refinement_rounds
            if max_refinement_rounds is not None
            else self.max_refinement_rounds
        )
        for round_num in range(rounds):
            critique_result = await self.critic.execute(
                CriticTask(
                    draft=draft,
                    sources=sources,
                    user_query=user_query,
                ),
                null_sink,
            )

            try:
                raw_critique = json.loads(critique_result.content)
            except json.JSONDecodeError:
                raw_critique = critique_result.metadata
            critique = CritiqueDict(**{
                k: v for k, v in raw_critique.items() if k in _CRITIQUE_FIELDS
            })

            if critique.consensus_reached:
                return draft, round_num + 1

            improved_result = await self.synthesizer.execute(
                SynthesizerTask(
                    sources=sources,
                    user_query=user_query,
                    critique=critique,
                    previous_draft=draft,
                ),
                null_sink,
            )
            draft = improved_result.content

        return draft, self.max_refinement_rounds

    def _build_response(
        self,
        answer: str,
        sources: list[SourceDict],
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
        self,
        user_query: str,
        authz_context: AuthorizationContext | None = None,
        external_context: ExternalSearchContext | None = None,
        max_refinement_rounds: int | None = None,
        sources: list[str] | None = None,
    ) -> AsyncIterator[dict[str, pydantic.JsonValue]]:
        """Execute Agentic search workflow with streaming events."""
        try:
            async for event in self._stream_search_workflow(
                user_query,
                authz_context,
                external_context,
                max_refinement_rounds,
                sources,
            ):
                yield event
        except Exception as e:
            yield {"event": "error", "data": {"message": str(e)}}

    async def _stream_search_workflow(
        self,
        user_query: str,
        authz_context: AuthorizationContext | None = None,
        external_context: ExternalSearchContext | None = None,
        max_refinement_rounds: int | None = None,
        sources: list[str] | None = None,
    ) -> AsyncIterator[dict[str, pydantic.JsonValue]]:
        query_variants = []
        async for variant in self._stream_plan_queries(user_query):
            query_variants.append(variant)
            yield {
                "event": "query_variant",
                "data": {"index": len(query_variants) - 1, "variant": variant},
            }

        seen_titles: set[str] = set()
        all_results: list[SourceDict] = []

        async for result in self._stream_parallel_search(
            query_variants, authz_context, external_context, sources
        ):
            all_results.append(result)
            title = result.title or "Untitled"
            if title not in seen_titles:
                seen_titles.add(title)
                yield {
                    "event": "reading_page",
                    "data": {"title": title, "url": result.url},
                }

        rounds_completed = 0
        async for event in self._stream_refine_answer(
            user_query, all_results, max_refinement_rounds=max_refinement_rounds
        ):
            if event.get("type") == "round_start":
                rounds_completed = int(typing.cast(int, event.get("round", 0)))
                yield {
                    "event": "refinement_round",
                    "data": {"round": rounds_completed, "status": "started"},
                }
            elif event.get("type") == "round_complete":
                yield {
                    "event": "refinement_round",
                    "data": {
                        "round": int(typing.cast(int, event.get("round", 0))),
                        "status": "completed",
                        "consensus_reached": bool(
                            event.get("consensus_reached", False)
                        ),
                    },
                }
            elif event.get("type") == "answer_chunk":
                yield {
                    "event": "answer_chunk",
                    "data": {"content": str(event.get("content", ""))},
                }

        yield typing.cast(
            dict[str, pydantic.JsonValue],
            {
                "event": "done",
                "data": typing.cast(
                    pydantic.JsonValue,
                    {
                        "sources": typing.cast(
                            pydantic.JsonValue,
                            [
                                dataclasses.asdict(s)
                                for s in self._format_sources(all_results)
                            ],
                        ),
                        "refinement_rounds": rounds_completed,
                        "query_variants": typing.cast(
                            pydantic.JsonValue, query_variants
                        ),
                    },
                ),
            },
        )

    async def _stream_plan_queries(self, user_query: str) -> AsyncIterator[str]:
        result = await self.query_planner.execute(
            QueryPlannerTask(user_query=user_query), null_sink
        )
        try:
            variants = json.loads(result.content)
            if not isinstance(variants, list):
                variants = [user_query]
        except (json.JSONDecodeError, TypeError):
            variants = [user_query]
        for variant in variants[: self.max_query_variants]:
            yield variant

    async def _stream_parallel_search(
        self,
        query_variants: list[str],
        authz_context: AuthorizationContext | None = None,
        external_context: ExternalSearchContext | None = None,
        sources: list[str] | None = None,
    ) -> AsyncIterator[SourceDict]:

        search_tasks = [
            self.searcher.execute(
                SearcherTask(
                    query=query,
                    top_k=self.agentic_search_top_k,
                    authz_context=authz_context,
                    external_context=external_context,
                    sources=sources,
                ),
                null_sink,
            )
            for query in query_variants
        ]

        seen_urls: set[str] = set()
        for coro in asyncio.as_completed(search_tasks):
            result = await coro
            if isinstance(result, BaseException):
                continue
            try:
                result_sources = json.loads(result.content)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(result_sources, list):
                for source in result_sources:
                    url = source.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        yield SourceDict(**{
                            k: v for k, v in source.items() if k in _SOURCE_FIELDS
                        })

    async def _stream_refine_answer(
        self,
        user_query: str,
        sources: list[SourceDict],
        *,
        max_refinement_rounds: int | None = None,
    ) -> AsyncIterator[dict[str, pydantic.JsonValue]]:
        if not sources:
            yield {
                "type": "answer_chunk",
                "content": "No relevant sources found for this query.",
            }
            return

        draft_result = await self.synthesizer.execute(
            SynthesizerTask(
                sources=sources,
                user_query=user_query,
            ),
            null_sink,
        )
        draft = draft_result.content

        rounds = (
            max_refinement_rounds
            if max_refinement_rounds is not None
            else self.max_refinement_rounds
        )
        for round_num in range(rounds):
            yield {"type": "round_start", "round": round_num + 1}

            critique_result = await self.critic.execute(
                CriticTask(
                    draft=draft,
                    sources=sources,
                    user_query=user_query,
                ),
                null_sink,
            )

            try:
                raw_critique = json.loads(critique_result.content)
            except json.JSONDecodeError:
                raw_critique = critique_result.metadata
            critique = CritiqueDict(**{
                k: v for k, v in raw_critique.items() if k in _CRITIQUE_FIELDS
            })

            yield {
                "type": "round_complete",
                "round": round_num + 1,
                "consensus_reached": critique.consensus_reached,
            }

            if critique.consensus_reached:
                yield {"type": "answer_chunk", "content": draft}
                return

            improved_result = await self.synthesizer.execute(
                SynthesizerTask(
                    sources=sources,
                    user_query=user_query,
                    critique=critique,
                    previous_draft=draft,
                ),
                null_sink,
            )
            draft = improved_result.content

        async for token in self.synthesizer.stream_execute(
            SynthesizerTask(
                sources=sources,
                user_query=user_query,
            )
        ):
            yield {"type": "answer_chunk", "content": token}

    def _format_sources(self, sources: list[SourceDict]) -> list[SourceDict]:
        return [
            SourceDict(
                title=source.title or "Untitled",
                url=source.url,
                domain=source.domain,
                snippet=(source.snippet or source.content)[:300],
            )
            for source in sources[: self.agentic_max_sources_returned]
        ]
