"""
title: Harmony FoA Search
author: Harmony Team
version: 0.1.0
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, Field


class Pipeline:
    class Valves(BaseModel):
        harmony_api_url: str = Field(
            default="http://harmony-api:8000",
            description="Harmony API base URL",
        )
        max_refinement_rounds: int = Field(
            default=3,
            ge=1,
            le=5,
            description="Maximum k-round refinement iterations",
        )

    def __init__(self) -> None:
        self.type = "manifold"
        self.id = "harmony_foa_search"
        self.name = "Harmony"
        self.valves = self.Valves()

    def pipelines(self) -> list[dict[str, str]]:  # noqa: PLR6301
        return [{"id": "harmony_foa_search", "name": "FoA Search"}]

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict],
        body: dict,
    ) -> str:
        """Process chat messages with multi-agent FoA search."""
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.valves.harmony_api_url}/foa-search",
                    json={
                        "query": user_message,
                        "max_refinement_rounds": self.valves.max_refinement_rounds,
                    },
                    timeout=120.0,
                )
                response.raise_for_status()
                data = response.json()

        except httpx.HTTPError as e:
            return f"FoA Search failed: {e}"

        answer = data.get("answer", "No answer provided")
        sources = data.get("sources", [])
        refinement_rounds = data.get("refinement_rounds", 0)
        query_variants = data.get("query_variants", [])

        result = answer

        if sources:
            result += "\n\n---\n\n**Sources:**\n"
            for i, src in enumerate(sources[:5], 1):
                title = src.get("title", "Untitled")
                url = src.get("url", "")
                result += f"{i}. [{title}]({url})\n"

        result += f"\n\n*Refined through {refinement_rounds} iteration(s) using {len(query_variants)} query variant(s)*"

        return result
