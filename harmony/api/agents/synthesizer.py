from __future__ import annotations

import typing

from harmony.api.agents.base import AgentCapability, AgentResult, BaseAgent
from harmony.api.services.llm import LLMService


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

        if critique and previous_draft:
            prompt = self._build_refinement_prompt(
                user_query, previous_draft, critique, sources
            )
        else:
            prompt = self._build_synthesis_prompt(user_query, sources)

        messages = [
            {
                "role": "system",
                "content": "You are a research synthesizer who generates accurate, well-cited answers from source documents.",
            },
            {"role": "user", "content": prompt},
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

    def _build_synthesis_prompt(  # noqa: PLR6301
        self, user_query: str, sources: list[dict[str, typing.Any]]
    ) -> str:
        """Build prompt for initial synthesis."""
        sources_text = "\n\n".join([
            f"[{i + 1}] {src.get('title', 'Untitled')} ({src.get('url', 'no URL')})\n{src.get('content', src.get('snippet', ''))[:800]}"
            for i, src in enumerate(sources[:10])
        ])

        return f"""Answer this question using the provided source documents.

User question: {user_query}

Source documents:
{sources_text}

Write a clear, accurate answer that:
- Directly addresses the user's question
- Cites sources using [1], [2], etc. notation
- Only makes claims supported by the sources
- Provides sufficient detail without being verbose
- Uses natural, conversational language

Your answer:"""

    def _build_refinement_prompt(  # noqa: PLR6301
        self,
        user_query: str,
        previous_draft: str,
        critique: dict[str, typing.Any],
        sources: list[dict[str, typing.Any]],
    ) -> str:
        """Build prompt for refinement based on critique."""
        sources_text = "\n\n".join([
            f"[{i + 1}] {src.get('title', 'Untitled')} ({src.get('url', 'no URL')})\n{src.get('content', src.get('snippet', ''))[:800]}"
            for i, src in enumerate(sources[:10])
        ])

        issues = "\n- ".join(critique.get("issues", []))
        suggestions = "\n- ".join(critique.get("suggestions", []))

        return f"""Improve this draft answer based on the critique feedback.

User question: {user_query}

Previous draft:
{previous_draft}

Critique:
Issues identified:
- {issues}

Suggestions for improvement:
- {suggestions}

Factual accuracy: {critique.get("factual_accuracy", 0.5):.1%}
Completeness: {critique.get("completeness", 0.5):.1%}
Hallucination risk: {critique.get("hallucination_risk", 0.5):.1%}

Source documents:
{sources_text}

Write an improved answer that:
- Addresses all issues raised in the critique
- Incorporates the suggestions
- Maintains or improves factual accuracy
- Cites sources appropriately using [1], [2], etc.
- Is grounded only in the provided documents

Your improved answer:"""
