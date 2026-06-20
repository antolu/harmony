from __future__ import annotations

import json
import typing

import pydantic

from harmony.api.agents._base import AgentCapability, AgentResult, BaseAgent
from harmony.api.agents._models import CriticTask, CritiqueDict
from harmony.api.services import LLMContext, LLMService, PromptManager


class CriticAgent(BaseAgent[CriticTask]):
    def __init__(self, llm_service: LLMService, prompt_manager: PromptManager) -> None:
        super().__init__()
        self.llm_service = llm_service
        self._prompt_manager = prompt_manager
        self.name = "critic"
        self.capability = AgentCapability(
            name="critic",
            description="Evaluate draft answers for factual accuracy, completeness, and hallucination risks against source documents",
            cost=1.5,
        )

    async def execute(self, task: CriticTask) -> AgentResult:
        """Review draft answer and provide critique."""
        draft = task.draft
        sources = task.sources
        user_query = task.user_query

        if not draft:
            return AgentResult(
                content=json.dumps({"error": "Empty draft"}),
                metadata={"consensus_reached": False},
                confidence=0.0,
            )

        system_prompt = self._prompt_manager.render_system_prompt("critic")
        user_prompt = self._prompt_manager.render_user_prompt(
            "critique",
            typing.cast(
                dict[str, pydantic.JsonValue],
                {
                    "user_query": user_query,
                    "draft": draft,
                    "sources": sources,
                },
            ),
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            return await self._parse_critique_response(messages)
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

    async def _parse_critique_response(
        self, messages: list[dict[str, str]]
    ) -> AgentResult:
        response = await self.llm_service.complete(
            messages=messages, ctx=LLMContext(agent_step="critic")
        )
        content = response.choices[0].message.content
        if not content:
            critique: CritiqueDict = {}
        else:
            critique = typing.cast(CritiqueDict, json.loads(content))

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
            critique.get("factual_accuracy", 0.5) + critique.get("completeness", 0.5)
        ) / 2.0

        return AgentResult(
            content=json.dumps(critique),
            metadata=typing.cast(dict[str, pydantic.JsonValue], critique),
            confidence=confidence,
        )
