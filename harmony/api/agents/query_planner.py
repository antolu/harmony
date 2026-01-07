from __future__ import annotations

import json
import typing

from harmony.api.agents.base import AgentCapability, AgentResult, BaseAgent
from harmony.api.services.llm import LLMService
from harmony.api.services.prompts import get_prompt_manager


class QueryPlannerAgent(BaseAgent):
    def __init__(self, llm_service: LLMService) -> None:
        super().__init__()
        self.llm_service = llm_service
        self.name = "query_planner"
        self.capability = AgentCapability(
            name="query_planner",
            description="Decompose user queries into diverse search variants to improve information retrieval coverage",
            cost=1.0,
        )

    async def execute(self, task: dict[str, typing.Any]) -> AgentResult:
        """Generate 2-4 diverse search query variants from user query."""
        user_query = task.get("user_query", "")
        context = task.get("context")

        if not user_query:
            return AgentResult(
                content="[]",
                metadata={"error": "Empty query"},
                confidence=0.0,
            )

        pm = get_prompt_manager()

        system_prompt = pm.render_system_prompt("query_planner")
        user_prompt = pm.render_user_prompt(
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
            response = self.llm_service.complete(messages=messages)
            content = response.choices[0].message.content

            query_variants = json.loads(content)

            if not isinstance(query_variants, list):
                query_variants = [query_variants]

            query_variants = query_variants[:4]

            return AgentResult(
                content=json.dumps(query_variants),
                metadata={"num_variants": len(query_variants)},
                confidence=1.0,
            )

        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            return AgentResult(
                content=json.dumps([user_query]),
                metadata={"error": str(e), "fallback": True},
                confidence=0.5,
            )
