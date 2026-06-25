from __future__ import annotations

import dataclasses
import json
import typing

import pydantic

from harmony.api._status_sink import StatusSink
from harmony.api.agents._base import AgentCapability, AgentResult, BaseAgent
from harmony.api.agents._models import CriticTask, CritiqueDict
from harmony.api.services import LLMContext, LLMService, PromptManager

_CRITIQUE_FIELDS = {f.name for f in dataclasses.fields(CritiqueDict)}


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

    async def execute(self, task: CriticTask, sink: StatusSink) -> AgentResult:
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
            raw_critique: dict[str, typing.Any] = {}
            critique = CritiqueDict()
        else:
            raw_critique = json.loads(content)
            critique = CritiqueDict(**{
                k: v for k, v in raw_critique.items() if k in _CRITIQUE_FIELDS
            })

        required_fields = {
            "factual_accuracy",
            "completeness",
            "hallucination_risk",
            "issues",
            "suggestions",
            "consensus_reached",
        }
        missing = required_fields - set(raw_critique.keys())
        if missing:
            critique.issues.append(f"Missing critique fields: {missing}")
            critique.consensus_reached = False

        confidence = (critique.factual_accuracy + critique.completeness) / 2.0

        return AgentResult(
            content=json.dumps(dataclasses.asdict(critique)),
            metadata=dataclasses.asdict(critique),
            confidence=confidence,
        )
