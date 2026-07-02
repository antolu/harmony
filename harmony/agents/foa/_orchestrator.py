from __future__ import annotations

import asyncio
import dataclasses
import json
import time
import typing
import uuid
from collections.abc import AsyncIterator

import pydantic
import structlog
from pydantic import BaseModel

from harmony.authz import AuthorizationContext
from harmony.models import (
    StatusSinkProtocol,
    StreamEvent,
    answer_chunk_status,
    lean_sources_for_trace,
    search_status,
    status_event_to_wire,
    thinking_status,
)
from harmony.services import StatusSink, null_sink
from harmony.services._external_search import ExternalSearchContext

from .._source_pool import SourcePool
from ._base import AgentResult
from ._critic import CriticAgent
from ._models import (
    CriticTask,
    CritiqueDict,
    PlannedQueries,
    QueryPlannerTask,
    SearcherTask,
    Source,
    SynthesizerTask,
)
from ._query_planner import QueryPlannerAgent
from ._searcher import SearcherAgent
from ._synthesizer import SynthesizerAgent

_CRITIQUE_FIELDS = {f.name for f in dataclasses.fields(CritiqueDict)}

logger = structlog.get_logger(__name__)


@dataclasses.dataclass
class AgentSuite:
    query_planner: QueryPlannerAgent
    searcher: SearcherAgent
    critic: CriticAgent
    synthesizer: SynthesizerAgent


@dataclasses.dataclass
class SearchInputs:
    """Request-scoped search context threaded through the refinement loop."""

    authz_context: AuthorizationContext | None = None
    external_context: ExternalSearchContext | None = None
    sources: list[str] | None = None


class AgenticSearchResponse(BaseModel):
    answer: str
    sources: list[Source]
    refinement_rounds: int
    query_variants: list[str]


class AgenticOrchestrator:
    def __init__(
        self,
        agents: AgentSuite,
        max_refinement_rounds: int = 3,
        max_query_variants: int = 4,
        agentic_max_sources_returned: int = 10,
        agentic_search_top_k: int = 50,
    ) -> None:
        self.query_planner = agents.query_planner
        self.searcher = agents.searcher
        self.critic = agents.critic
        self.synthesizer = agents.synthesizer
        self.max_refinement_rounds = max_refinement_rounds
        self.max_query_variants = max_query_variants
        self.agentic_max_sources_returned = agentic_max_sources_returned
        # Pool-admission ceiling: how many candidates the combined search may return
        # into the SourcePool. The SourcePool char budget — not this count — is the
        # binding final cap on what reaches the synthesizer and critic.
        self.pool_admission_ceiling = agentic_search_top_k

    async def search(
        self,
        user_query: str,
        authz_context: AuthorizationContext | None = None,
        external_context: ExternalSearchContext | None = None,
        max_refinement_rounds: int | None = None,
        sources: list[str] | None = None,
    ) -> AgenticSearchResponse:
        """Execute full Agentic search workflow."""
        start = time.monotonic()
        inputs = SearchInputs(
            authz_context=authz_context,
            external_context=external_context,
            sources=sources,
        )
        planned = await self._plan_queries(user_query, null_sink)
        pool = SourcePool()
        pool.add_all(await self._combined_search(planned, inputs, null_sink))
        answer, rounds, cited_sources = await self._refine_answer(
            user_query,
            pool,
            inputs,
            null_sink,
            max_refinement_rounds=max_refinement_rounds,
        )
        logger.info(
            "agentic_search_complete",
            duration_ms=round((time.monotonic() - start) * 1000, 2),
            refinement_rounds=rounds,
            source_count=len(cited_sources),
        )
        return self._build_response(
            answer, cited_sources, rounds, planned.keyword_variants
        )

    async def _plan_queries(
        self, user_query: str, sink: StatusSinkProtocol, context: str | None = None
    ) -> PlannedQueries:
        start = time.monotonic()
        result = await self.query_planner.execute(
            QueryPlannerTask(user_query=user_query, context=context), sink
        )
        try:
            parsed = json.loads(result.content)
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        semantic_query = parsed.get("semantic_query") or user_query
        variants = parsed.get("keyword_variants") or [user_query]
        if not isinstance(variants, list):
            variants = [user_query]
        # The runtime-tunable cap lives here (single source of truth); the planner
        # agent no longer caps.
        variants = [str(v) for v in variants][: self.max_query_variants]
        logger.info(
            "agentic_plan_queries",
            duration_ms=round((time.monotonic() - start) * 1000, 2),
            is_followup=context is not None,
            semantic_query=semantic_query,
            keyword_variant_count=len(variants),
        )
        return PlannedQueries(
            semantic_query=str(semantic_query), keyword_variants=variants
        )

    async def _combined_search(
        self,
        planned: PlannedQueries,
        inputs: SearchInputs,
        sink: StatusSinkProtocol,
    ) -> list[Source]:
        """Run one combined search (keyword-variant union + single semantic vector).

        Returns the parsed Sources; callers add/merge them into a SourcePool.
        Passes the pool-admission ceiling as top_k so the SourcePool char budget is
        the final cap, rather than a small per-call slice.
        """
        start = time.monotonic()
        result = await self.searcher.execute(
            SearcherTask(
                query=planned.semantic_query,
                keyword_variants=planned.keyword_variants,
                top_k=self.pool_admission_ceiling,
                authz_context=inputs.authz_context,
                external_context=inputs.external_context,
                sources=inputs.sources,
            ),
            sink,
        )
        found = self._sources_from_result(result)
        logger.info(
            "agentic_combined_search",
            duration_ms=round((time.monotonic() - start) * 1000, 2),
            keyword_variant_count=len(planned.keyword_variants),
            result_count=len(found),
        )
        sink.emit(
            search_status(
                f"Searching: {planned.semantic_query}",
                step_id=str(uuid.uuid4()),
                query=planned.semantic_query,
                sources=found,
            )
        )
        return found

    def _sources_from_result(self, result: AgentResult) -> list[Source]:
        try:
            sources = json.loads(result.content)
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(sources, list):
            return []
        return [Source(**source) for source in sources if source.get("url")]

    async def _run_critique(
        self,
        user_query: str,
        draft: str,
        budgeted: list[Source],
        sink: StatusSinkProtocol,
    ) -> CritiqueDict:
        start = time.monotonic()
        critique_result = await self.critic.execute(
            CriticTask(draft=draft, sources=budgeted, user_query=user_query),
            sink,
        )
        try:
            raw_critique = json.loads(critique_result.content)
        except json.JSONDecodeError:
            raw_critique = critique_result.metadata
        critique = CritiqueDict(**{
            k: v for k, v in raw_critique.items() if k in _CRITIQUE_FIELDS
        })
        logger.info(
            "agentic_critique",
            duration_ms=round((time.monotonic() - start) * 1000, 2),
            consensus_reached=critique.consensus_reached,
            missing_information_count=len(critique.missing_information),
        )
        return critique

    @staticmethod
    def _gap_context(draft: str, critique: CritiqueDict) -> str:
        return (
            "Current draft:\n"
            + draft
            + "\n\nMissing information:\n"
            + "\n".join(critique.missing_information)
        )

    async def _followup_search(
        self,
        user_query: str,
        context: str,
        pool: SourcePool,
        inputs: SearchInputs,
        sink: StatusSinkProtocol,
    ) -> None:
        """Re-plan from the critic's gaps, search, and merge into the pool.

        The critic's natural-language gaps plus the current draft are fed to the
        query planner as context so it knows what to search for; the new results are
        merged (not appended) so the pool stays a fixed, ranked, deduped set.
        """
        pool_size_before = len(pool.ranked())
        planned = await self._plan_queries(user_query, sink, context=context)
        found = await self._combined_search(planned, inputs, sink)
        pool.merge_round(found)
        logger.info(
            "agentic_followup_search",
            pool_size_before=pool_size_before,
            pool_size_after=len(pool.ranked()),
        )

    async def _refine_answer(
        self,
        user_query: str,
        pool: SourcePool,
        inputs: SearchInputs,
        sink: StatusSinkProtocol,
        *,
        max_refinement_rounds: int | None = None,
    ) -> tuple[str, int, list[Source]]:
        # Capped to agentic_max_sources_returned so every citation index the
        # synthesizer/critic can emit maps to a source that actually ends up in
        # the returned sources list — citing beyond this list would otherwise
        # produce dead footnotes once the response truncates to that same cap.
        budgeted = pool.select_within_budget()[: self.agentic_max_sources_returned]
        if not budgeted:
            return "No relevant sources found for this query.", 0, []

        draft_result = await self.synthesizer.execute(
            SynthesizerTask(sources=budgeted, user_query=user_query),
            sink,
        )
        draft = draft_result.content

        rounds = (
            max_refinement_rounds
            if max_refinement_rounds is not None
            else self.max_refinement_rounds
        )
        for round_num in range(rounds):
            round_start = time.monotonic()
            sink.emit(
                thinking_status(
                    f"Refining answer (round {round_num + 1})",
                    step_id=f"refine-{round_num + 1}",
                    status="running",
                )
            )

            critique = await self._run_critique(user_query, draft, budgeted, sink)

            sink.emit(
                thinking_status(
                    f"Refined answer (round {round_num + 1})"
                    + (
                        " — consensus reached"
                        if critique.consensus_reached
                        else " — searching for more information"
                        if critique.missing_information
                        else ""
                    ),
                    step_id=f"refine-{round_num + 1}",
                    status="done",
                )
            )

            if critique.consensus_reached:
                logger.info(
                    "agentic_refinement_round",
                    round=round_num + 1,
                    duration_ms=round((time.monotonic() - round_start) * 1000, 2),
                    consensus_reached=True,
                    searched=False,
                )
                return draft, round_num + 1, budgeted

            searched = bool(critique.missing_information)
            if searched:
                context = self._gap_context(draft, critique)
                await self._followup_search(user_query, context, pool, inputs, sink)
                budgeted = pool.select_within_budget()[
                    : self.agentic_max_sources_returned
                ]

            improved_result = await self.synthesizer.execute(
                SynthesizerTask(
                    sources=budgeted,
                    user_query=user_query,
                    critique=critique,
                    previous_draft=draft,
                ),
                sink,
            )
            draft = improved_result.content

            logger.info(
                "agentic_refinement_round",
                round=round_num + 1,
                duration_ms=round((time.monotonic() - round_start) * 1000, 2),
                consensus_reached=False,
                searched=searched,
            )

        return draft, self.max_refinement_rounds, budgeted

    def _build_response(
        self,
        answer: str,
        sources: list[Source],
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
    ) -> AsyncIterator[StreamEvent]:
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
    ) -> AsyncIterator[StreamEvent]:
        sink = StatusSink()
        workflow_start = time.monotonic()

        inputs = SearchInputs(
            authz_context=authz_context,
            external_context=external_context,
            sources=sources,
        )

        async def _run_workflow() -> tuple[list[Source], int, list[str]]:
            planned = await self._plan_queries(user_query, sink)
            pool = SourcePool()
            pool.add_all(await self._combined_search(planned, inputs, sink))
            _answer, rounds, cited_sources = await self._refine_and_stream_final_answer(
                user_query,
                pool,
                inputs,
                sink,
                max_refinement_rounds=max_refinement_rounds,
            )
            logger.info(
                "agentic_search_complete",
                duration_ms=round((time.monotonic() - workflow_start) * 1000, 2),
                refinement_rounds=rounds,
                source_count=len(cited_sources),
            )
            return cited_sources, rounds, planned.keyword_variants

        workflow_task = asyncio.ensure_future(_run_workflow())
        workflow_task.add_done_callback(lambda _task: sink.close())

        async for status_event in sink.drain():
            if status_event["kind"] == "answer_chunk":
                yield {
                    "event": "answer_chunk",
                    "data": {"content": status_event["message"]},
                    "trace": None,
                }
            else:
                wire_event, lean = status_event_to_wire(status_event)
                trace_event: dict[str, pydantic.JsonValue] | None = None
                if lean is not None:
                    trace_event = {
                        **wire_event,
                        "sources": typing.cast(pydantic.JsonValue, lean),
                    }
                else:
                    trace_event = wire_event
                yield {"event": "status", "data": wire_event, "trace": trace_event}

        all_results, rounds_completed, query_variants = await workflow_task

        formatted = self._format_sources(all_results)
        done_data: dict[str, pydantic.JsonValue] = {
            "sources": [s.model_dump() for s in formatted],
            "refinement_rounds": rounds_completed,
            "query_variants": typing.cast(list[pydantic.JsonValue], query_variants),
        }
        done_trace: dict[str, pydantic.JsonValue] = {
            "kind": "done",
            "sources": typing.cast(
                pydantic.JsonValue, lean_sources_for_trace(formatted)
            ),
        }
        yield {"event": "done", "data": done_data, "trace": done_trace}

    async def _refine_and_stream_final_answer(
        self,
        user_query: str,
        pool: SourcePool,
        inputs: SearchInputs,
        sink: StatusSinkProtocol,
        *,
        max_refinement_rounds: int | None = None,
    ) -> tuple[str, int, list[Source]]:
        """Run the refinement loop, streaming the final answer token-by-token.

        Mirrors _refine_answer's branching exactly, except the no-consensus
        exhausted-rounds fallback streams tokens via stream_execute instead
        of a single non-streaming completion, since stream_search must
        deliver answer_chunk tokens incrementally.
        """
        # Capped to agentic_max_sources_returned — see _refine_answer for why.
        budgeted = pool.select_within_budget()[: self.agentic_max_sources_returned]
        if not budgeted:
            sink.emit(answer_chunk_status("No relevant sources found for this query."))
            return "No relevant sources found for this query.", 0, []

        draft_result = await self.synthesizer.execute(
            SynthesizerTask(sources=budgeted, user_query=user_query),
            sink,
        )
        draft = draft_result.content

        rounds = (
            max_refinement_rounds
            if max_refinement_rounds is not None
            else self.max_refinement_rounds
        )
        for round_num in range(rounds):
            round_start = time.monotonic()
            sink.emit(
                thinking_status(
                    f"Refining answer (round {round_num + 1})",
                    step_id=f"refine-{round_num + 1}",
                    status="running",
                )
            )

            critique = await self._run_critique(user_query, draft, budgeted, sink)

            sink.emit(
                thinking_status(
                    f"Refined answer (round {round_num + 1})"
                    + (
                        " — consensus reached"
                        if critique.consensus_reached
                        else " — searching for more information"
                        if critique.missing_information
                        else ""
                    ),
                    step_id=f"refine-{round_num + 1}",
                    status="done",
                )
            )

            if critique.consensus_reached:
                sink.emit(answer_chunk_status(draft))
                logger.info(
                    "agentic_refinement_round",
                    round=round_num + 1,
                    duration_ms=round((time.monotonic() - round_start) * 1000, 2),
                    consensus_reached=True,
                    searched=False,
                )
                return draft, round_num + 1, budgeted

            searched = bool(critique.missing_information)
            if searched:
                context = self._gap_context(draft, critique)
                await self._followup_search(user_query, context, pool, inputs, sink)
                budgeted = pool.select_within_budget()[
                    : self.agentic_max_sources_returned
                ]

            improved_result = await self.synthesizer.execute(
                SynthesizerTask(
                    sources=budgeted,
                    user_query=user_query,
                    critique=critique,
                    previous_draft=draft,
                ),
                sink,
            )
            draft = improved_result.content

            logger.info(
                "agentic_refinement_round",
                round=round_num + 1,
                duration_ms=round((time.monotonic() - round_start) * 1000, 2),
                consensus_reached=False,
                searched=searched,
            )

        final_tokens: list[str] = []
        async for token in self.synthesizer.stream_execute(
            SynthesizerTask(sources=budgeted, user_query=user_query)
        ):
            final_tokens.append(token)
            sink.emit(answer_chunk_status(token))

        return "".join(final_tokens), self.max_refinement_rounds, budgeted

    def _format_sources(self, sources: list[Source]) -> list[Source]:
        return [
            Source(
                title=source.title or "Untitled",
                url=source.url,
                domain=source.domain,
                snippet=(source.snippet or source.content)[:300],
                source_type=source.source_type,
            )
            for source in sources[: self.agentic_max_sources_returned]
        ]
