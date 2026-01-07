from __future__ import annotations

import json
import typing

from harmony.api.agents.base import AgentCapability, AgentResult, BaseAgent
from harmony.api.services.llm import LLMService
from harmony.api.services.prompts import get_prompt_manager


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

    async def execute(self, task: dict[str, typing.Any]) -> AgentResult:
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

        pm = get_prompt_manager()

        system_prompt = pm.render_system_prompt("critic")
        user_prompt = pm.render_user_prompt(
            "critique",
            {
                "user_query": user_query,
                "draft": draft,
                "sources": sources,
            },
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
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
