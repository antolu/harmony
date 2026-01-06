from __future__ import annotations

import json
from typing import Any

from harmony.api.agents.base import AgentCapability, AgentResult, BaseAgent
from harmony.api.services.llm import LLMService


class CriticAgent(BaseAgent):
    def __init__(self, llm_service: LLMService) -> None:
        super().__init__()
        self.llm_service = llm_service
        self.name = "critic"
        self.capability = AgentCapability(
            name="critic",
            description="Evaluate draft answers for factual accuracy, completeness, and hallucination risks against source documents",
            cost=1.5,
        )

    async def execute(self, task: dict[str, Any]) -> AgentResult:
        """Review draft answer and provide critique."""
        draft = task.get("draft", "")
        sources = task.get("sources", [])
        user_query = task.get("user_query", "")

        if not draft:
            return AgentResult(
                content=json.dumps({"error": "Empty draft"}),
                metadata={"consensus_reached": False},
                confidence=0.0,
            )

        prompt = self._build_prompt(user_query, draft, sources)

        messages = [
            {
                "role": "system",
                "content": "You are a critical reviewer who evaluates answers against source documents for accuracy and completeness.",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = self.llm_service.complete(messages=messages)
            content = response.choices[0].message.content

            critique = json.loads(content)

            required_fields = {
                "factual_accuracy",
                "completeness",
                "hallucination_risk",
                "issues",
                "suggestions",
                "consensus_reached",
            }
            if not all(field in critique for field in required_fields):
                missing = required_fields - set(critique.keys())
                critique.setdefault("issues", []).append(
                    f"Missing critique fields: {missing}"
                )
                critique.setdefault("consensus_reached", False)

            confidence = (
                critique.get("factual_accuracy", 0.5)
                + critique.get("completeness", 0.5)
            ) / 2.0

            return AgentResult(
                content=json.dumps(critique),
                metadata=critique,
                confidence=confidence,
            )

        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            return AgentResult(
                content=json.dumps({
                    "factual_accuracy": 0.5,
                    "completeness": 0.5,
                    "hallucination_risk": 0.5,
                    "issues": [f"Critique parsing error: {e}"],
                    "suggestions": ["Review and improve answer quality"],
                    "consensus_reached": False,
                }),
                metadata={"error": str(e), "consensus_reached": False},
                confidence=0.3,
            )

    def _build_prompt(  # noqa: PLR6301
        self, user_query: str, draft: str, sources: list[dict[str, Any]]
    ) -> str:
        """Build the LLM prompt for critique."""
        sources_text = "\n\n".join([
            f"Source {i + 1}: {src.get('title', 'Untitled')}\n{src.get('content', src.get('snippet', ''))[:500]}"
            for i, src in enumerate(sources[:5])
        ])

        return f"""Evaluate this draft answer against the source documents.

User question: {user_query}

Draft answer:
{draft}

Source documents:
{sources_text}

Provide a JSON critique with these exact fields:
- "factual_accuracy": float (0-1) - Are claims supported by sources?
- "completeness": float (0-1) - Does it address the full question?
- "hallucination_risk": float (0-1) - Contains unsupported claims?
- "issues": list[str] - Specific problems found
- "suggestions": list[str] - Improvements to make
- "consensus_reached": bool - Is the answer good enough? (true if factual_accuracy > 0.8 and completeness > 0.7)

Output only the JSON object, no additional text."""
