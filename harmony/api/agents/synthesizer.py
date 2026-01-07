from __future__ import annotations

import typing

from harmony.api.agents.base import AgentCapability, AgentResult, BaseAgent
from harmony.api.services.llm import LLMService
from harmony.api.services.prompts import get_prompt_manager


class SynthesizerAgent(BaseAgent):
    def __init__(self, llm_service: LLMService) -> None:
        super().__init__()
        self.llm_service = llm_service
        self.name = "synthesizer"
        self.capability = AgentCapability(
            name="synthesizer",
            description="Generate answers from search results and incorporate critique feedback for iterative refinement",
            cost=2.0,
        )

    async def execute(self, task: dict[str, typing.Any]) -> AgentResult:
        """Generate or refine answer from sources."""
        sources = task.get("sources", [])
        user_query = task.get("user_query", "")
        critique = task.get("critique")
        previous_draft = task.get("previous_draft")

        if not sources:
            return AgentResult(
                content="No sources available to answer the question.",
                metadata={"error": "No sources"},
                confidence=0.0,
            )

        if not user_query:
            return AgentResult(
                content="No query provided.",
                metadata={"error": "No query"},
                confidence=0.0,
            )

        pm = get_prompt_manager()

        system_prompt = pm.render_system_prompt("synthesizer")

        if critique and previous_draft:
            user_prompt = pm.render_user_prompt(
                "synthesize_refine",
                {
                    "user_query": user_query,
                    "previous_draft": previous_draft,
                    "critique": critique,
                    "sources": sources,
                },
            )
        else:
            user_prompt = pm.render_user_prompt(
                "synthesize",
                {
                    "user_query": user_query,
                    "sources": sources,
                },
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = self.llm_service.complete(messages=messages)
            answer = response.choices[0].message.content

            confidence = 0.9 if critique else 0.7

            return AgentResult(
                content=answer,
                metadata={
                    "num_sources": len(sources),
                    "refined": bool(critique),
                },
                confidence=confidence,
            )

        except (KeyError, AttributeError) as e:
            return AgentResult(
                content=f"Error synthesizing answer: {e}",
                metadata={"error": str(e)},
                confidence=0.0,
            )
