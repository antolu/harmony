from __future__ import annotations

import collections.abc
import typing

from harmony.api.agents._base import AgentCapability, AgentResult, BaseAgent
from harmony.api.services import LLMService, PromptManager


class SynthesizerAgent(BaseAgent):
    def __init__(self, llm_service: LLMService, prompt_manager: PromptManager) -> None:
        super().__init__()
        self.llm_service = llm_service
        self._prompt_manager = prompt_manager
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

        system_prompt = self._prompt_manager.render_system_prompt("synthesizer")

        if critique and previous_draft:
            user_prompt = self._prompt_manager.render_user_prompt(
                "synthesize_refine",
                {
                    "user_query": user_query,
                    "previous_draft": previous_draft,
                    "critique": critique,
                    "sources": sources,
                },
            )
        else:
            user_prompt = self._prompt_manager.render_user_prompt(
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
            response = await self.llm_service.complete(messages=messages)
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

    async def stream_execute(
        self, task: dict[str, typing.Any]
    ) -> collections.abc.AsyncGenerator[str, None]:
        """Stream answer tokens as they arrive."""
        sources = task.get("sources", [])
        user_query = task.get("user_query", "")
        critique = task.get("critique")
        previous_draft = task.get("previous_draft")

        if not sources or not user_query:
            yield "No sources or query provided."
            return

        system_prompt = self._prompt_manager.render_system_prompt("synthesizer")

        if critique and previous_draft:
            user_prompt = self._prompt_manager.render_user_prompt(
                "synthesize_refine",
                {
                    "user_query": user_query,
                    "previous_draft": previous_draft,
                    "critique": critique,
                    "sources": sources,
                },
            )
        else:
            user_prompt = self._prompt_manager.render_user_prompt(
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

        async for token in self.llm_service.stream_complete(messages=messages):
            yield token
