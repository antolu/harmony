from __future__ import annotations

import dataclasses
import json

import pydantic

from harmony.agents._base import (
    AgentCapability,
    AgentResult,
    BaseAgent,
    StatusSinkProtocol,
)
from harmony.agents._models import PlannedQueries, QueryPlannerTask
from harmony.services import LLMContext, LLMService, PromptManager


class QueryPlannerAgent(BaseAgent[QueryPlannerTask]):
    def __init__(self, llm_service: LLMService, prompt_manager: PromptManager) -> None:
        super().__init__()
        self.llm_service = llm_service
        self._prompt_manager = prompt_manager
        self.name = "query_planner"
        self.capability = AgentCapability(
            name="query_planner",
            description="Decompose user queries into diverse search variants to improve information retrieval coverage",
            cost=1.0,
        )

    async def execute(
        self, task: QueryPlannerTask, sink: StatusSinkProtocol
    ) -> AgentResult:
        """Generate 2-4 diverse search query variants from user query."""
        user_query = task.user_query
        context = task.context

        if not user_query:
            return AgentResult(
                content="[]",
                metadata={"error": "Empty query"},
                confidence=0.0,
            )

        system_prompt = self._prompt_manager.render_system_prompt("query_planner")
        user_prompt = self._prompt_manager.render_user_prompt(
            "query_plan",
            {
                "user_query": user_query,
                "context": context,
            },
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            return await self._parse_variants_response(messages, user_query)
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            return self._fallback(user_query, error=str(e))

    def _fallback(self, user_query: str, *, error: str | None = None) -> AgentResult:
        planned = PlannedQueries(
            semantic_query=user_query, keyword_variants=[user_query]
        )
        metadata: dict[str, pydantic.JsonValue] = {
            "fallback": True,
            "num_variants": 1,
        }
        if error is not None:
            metadata["error"] = error
        return AgentResult(
            content=json.dumps(dataclasses.asdict(planned)),
            metadata=metadata,
            confidence=0.5,
        )

    async def _parse_variants_response(
        self, messages: list[dict[str, str]], user_query: str
    ) -> AgentResult:
        response = await self.llm_service.complete(
            messages=messages, ctx=LLMContext(agent_step="query_planner")
        )
        content = response.choices[0].message.content
        if not content:
            return self._fallback(user_query)

        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return self._fallback(user_query)

        semantic_query = parsed.get("semantic_query") or user_query
        variants = parsed.get("keyword_variants") or [user_query]
        if not isinstance(variants, list):
            variants = [user_query]
        # No cap here: the orchestrator applies the runtime-tunable
        # agentic_max_query_variants (PipelineConfig) as the single source of truth.
        variants = [str(v) for v in variants]

        planned = PlannedQueries(
            semantic_query=str(semantic_query), keyword_variants=variants
        )
        return AgentResult(
            content=json.dumps(dataclasses.asdict(planned)),
            metadata={"num_variants": len(variants)},
            confidence=1.0,
        )
