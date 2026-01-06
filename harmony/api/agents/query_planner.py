from __future__ import annotations

import json
from typing import Any

from harmony.api.agents.base import AgentCapability, AgentResult, BaseAgent
from harmony.api.services.llm import LLMService


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

    async def execute(self, task: dict[str, Any]) -> AgentResult:
        """Generate 2-4 diverse search query variants from user query."""
        user_query = task.get("user_query", "")
        context = task.get("context")

        if not user_query:
            return AgentResult(
                content="[]",
                metadata={"error": "Empty query"},
                confidence=0.0,
            )

        prompt = self._build_prompt(user_query, context)

        messages = [
            {
                "role": "system",
                "content": "You are a search query planner. Your task is to generate diverse search queries that help find relevant information.",
            },
            {"role": "user", "content": prompt},
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

    def _build_prompt(  # noqa: PLR6301
        self, user_query: str, context: str | None = None
    ) -> str:
        """Build the LLM prompt for query planning."""
        prompt = f"""Given this user question, generate 2-4 diverse search queries that would help find relevant information.

User question: {user_query}"""

        if context:
            prompt += f"\n\nContext: {context}"

        prompt += """

Output a JSON array of search queries, each targeting different aspects of the question. Include:
- A direct query matching the user's words
- A rephrased query using synonyms
- A more specific query focusing on key entities
- (Optional) A broader contextual query

Example output: ["direct query", "rephrased version", "specific query", "contextual query"]

Output only the JSON array, no additional text."""

        return prompt
