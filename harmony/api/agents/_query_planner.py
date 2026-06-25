from __future__ import annotations

import json

from harmony.api._status_sink import StatusSink
from harmony.api.agents._base import AgentCapability, AgentResult, BaseAgent
from harmony.api.agents._models import QueryPlannerTask
from harmony.api.services import LLMContext, LLMService, PromptManager


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

    async def execute(self, task: QueryPlannerTask, sink: StatusSink) -> AgentResult:
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
            return await self._parse_variants_response(messages)
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            return AgentResult(
                content=json.dumps([user_query]),
                metadata={"error": str(e), "fallback": True},
                confidence=0.5,
            )

    async def _parse_variants_response(
        self, messages: list[dict[str, str]]
    ) -> AgentResult:
        response = await self.llm_service.complete(
            messages=messages, ctx=LLMContext(agent_step="query_planner")
        )
        content = response.choices[0].message.content
        if not content:
            return AgentResult(
                content="[]", metadata={"num_variants": 0}, confidence=1.0
            )
        query_variants = json.loads(content)

        if not isinstance(query_variants, list):
            query_variants = [query_variants]

        query_variants = query_variants[:4]

        return AgentResult(
            content=json.dumps(query_variants),
            metadata={"num_variants": len(query_variants)},
            confidence=1.0,
        )
