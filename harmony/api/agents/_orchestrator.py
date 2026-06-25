from __future__ import annotations

import asyncio
import dataclasses
import json
import typing
import uuid
from collections.abc import AsyncIterator

import pydantic
from pydantic import BaseModel

from harmony.api._status import StatusSinkProtocol
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
from harmony.api.services import StatusSink, null_sink

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
        query_variants = await self._plan_queries(user_query, null_sink)
        all_results = await self._parallel_search(
            query_variants, null_sink, authz_context, external_context, sources
        )
        answer, rounds = await self._refine_answer(
            user_query,
            all_results,
            null_sink,
            max_refinement_rounds=max_refinement_rounds,
        )
        return self._build_response(answer, all_results, rounds, query_variants)

    async def _plan_queries(
        self, user_query: str, sink: StatusSinkProtocol
    ) -> list[str]:
        result = await self.query_planner.execute(
            QueryPlannerTask(user_query=user_query), sink
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
        sink: StatusSinkProtocol,
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
                sink,
            )
            for query in query_variants
        ]

        all_sources: list[SourceDict] = []
        seen_urls: set[str] = set()

        for coro in asyncio.as_completed(search_tasks):
            try:
                result = await coro
            except Exception:
                continue
            variant_sources: list[SourceDict] = []
            self._collect_sources(result, variant_sources, seen_urls)
            all_sources.extend(variant_sources)
            variant_query = str(result.metadata.get("query", ""))
            sink.emit(
                f"Searching: {variant_query}" if variant_query else "Searching",
                kind="search",
                step_id=str(uuid.uuid4()),
                query=variant_query,
                sources=[dataclasses.asdict(s) for s in variant_sources],
            )

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
        sink: StatusSinkProtocol,
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
            sink,
        )
        draft = draft_result.content

        rounds = (
            max_refinement_rounds
            if max_refinement_rounds is not None
            else self.max_refinement_rounds
        )
        for round_num in range(rounds):
            sink.emit(
                f"Refining answer (round {round_num + 1})",
                kind="refining",
                round=round_num + 1,
                status="started",
            )

            critique_result = await self.critic.execute(
                CriticTask(
                    draft=draft,
                    sources=sources,
                    user_query=user_query,
                ),
                sink,
            )

            try:
                raw_critique = json.loads(critique_result.content)
            except json.JSONDecodeError:
                raw_critique = critique_result.metadata
            critique = CritiqueDict(**{
                k: v for k, v in raw_critique.items() if k in _CRITIQUE_FIELDS
            })

            sink.emit(
                f"Refining answer (round {round_num + 1})",
                kind="refining",
                round=round_num + 1,
                status="completed",
                consensus_reached=critique.consensus_reached,
            )

            if critique.consensus_reached:
                return draft, round_num + 1

            improved_result = await self.synthesizer.execute(
                SynthesizerTask(
                    sources=sources,
                    user_query=user_query,
                    critique=critique,
                    previous_draft=draft,
                ),
                sink,
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
            async for event in self._stream_search_events(
                user_query,
                authz_context,
                external_context,
                max_refinement_rounds,
                sources,
            ):
                yield event
        except Exception as e:
            yield {"event": "error", "data": {"message": str(e)}}

    async def _stream_search_events(
        self,
        user_query: str,
        authz_context: AuthorizationContext | None,
        external_context: ExternalSearchContext | None,
        max_refinement_rounds: int | None,
        sources: list[str] | None,
    ) -> AsyncIterator[dict[str, pydantic.JsonValue]]:
        sink = StatusSink()

        async def _run_workflow() -> tuple[list[SourceDict], int, list[str]]:
            query_variants = await self._plan_queries(user_query, sink)
            all_results = await self._parallel_search(
                query_variants, sink, authz_context, external_context, sources
            )
            _answer, rounds = await self._refine_and_stream_final_answer(
                user_query,
                all_results,
                sink,
                max_refinement_rounds=max_refinement_rounds,
            )
            return all_results, rounds, query_variants

        workflow_task = asyncio.ensure_future(_run_workflow())
        workflow_task.add_done_callback(lambda _task: sink.close())

        async for status_event in sink.drain():
            if status_event.metadata.get("kind") == "answer_chunk":
                yield {
                    "event": "answer_chunk",
                    "data": {"content": status_event.message},
                }
            else:
                yield {
                    "event": "status",
                    "data": {
                        "message": status_event.message,
                        **status_event.metadata,
                    },
                }

        all_results, rounds_completed, query_variants = await workflow_task

        done_data: dict[str, pydantic.JsonValue] = {
            "sources": [
                dataclasses.asdict(s) for s in self._format_sources(all_results)
            ],
            "refinement_rounds": rounds_completed,
            "query_variants": typing.cast(list[pydantic.JsonValue], query_variants),
        }
        yield {"event": "done", "data": done_data}

    async def _refine_and_stream_final_answer(
        self,
        user_query: str,
        sources: list[SourceDict],
        sink: StatusSinkProtocol,
        *,
        max_refinement_rounds: int | None = None,
    ) -> tuple[str, int]:
        """Run the refinement loop, streaming the final answer token-by-token.

        Mirrors _refine_answer's branching exactly, except the no-consensus
        exhausted-rounds fallback streams tokens via stream_execute instead
        of a single non-streaming completion, since stream_search must
        deliver answer_chunk tokens incrementally.
        """
        if not sources:
            sink.emit("No relevant sources found for this query.", kind="answer_chunk")
            return "No relevant sources found for this query.", 0

        draft_result = await self.synthesizer.execute(
            SynthesizerTask(
                sources=sources,
                user_query=user_query,
            ),
            sink,
        )
        draft = draft_result.content

        rounds = (
            max_refinement_rounds
            if max_refinement_rounds is not None
            else self.max_refinement_rounds
        )
        for round_num in range(rounds):
            sink.emit(
                f"Refining answer (round {round_num + 1})",
                kind="refining",
                round=round_num + 1,
                status="started",
            )

            critique_result = await self.critic.execute(
                CriticTask(
                    draft=draft,
                    sources=sources,
                    user_query=user_query,
                ),
                sink,
            )

            try:
                raw_critique = json.loads(critique_result.content)
            except json.JSONDecodeError:
                raw_critique = critique_result.metadata
            critique = CritiqueDict(**{
                k: v for k, v in raw_critique.items() if k in _CRITIQUE_FIELDS
            })

            sink.emit(
                f"Refining answer (round {round_num + 1})",
                kind="refining",
                round=round_num + 1,
                status="completed",
                consensus_reached=critique.consensus_reached,
            )

            if critique.consensus_reached:
                sink.emit(draft, kind="answer_chunk")
                return draft, round_num + 1

            improved_result = await self.synthesizer.execute(
                SynthesizerTask(
                    sources=sources,
                    user_query=user_query,
                    critique=critique,
                    previous_draft=draft,
                ),
                sink,
            )
            draft = improved_result.content

        final_tokens: list[str] = []
        async for token in self.synthesizer.stream_execute(
            SynthesizerTask(
                sources=sources,
                user_query=user_query,
            )
        ):
            final_tokens.append(token)
            sink.emit(token, kind="answer_chunk")

        return "".join(final_tokens), self.max_refinement_rounds

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
