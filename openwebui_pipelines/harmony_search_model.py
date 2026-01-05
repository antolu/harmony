"""
title: Harmony AI Search
author: Harmony Team
version: 0.1.0
"""

import httpx
from pydantic import BaseModel, Field


class Pipeline:
    class Valves(BaseModel):
        harmony_api_url: str = Field(
            default="http://harmony-api:8000",
            description="Harmony API base URL",
        )

    def __init__(self) -> None:
        self.type = "manifold"
        self.id = "harmony_search"
        self.name = "Harmony"
        self.valves = self.Valves()

    def pipelines(self) -> list[dict[str, str]]:  # noqa: PLR6301
        return [{"id": "harmony_ai_search", "name": "AI Search (Gemini)"}]

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict],
        body: dict,
    ) -> str:
        """Process chat messages and return AI search results."""
        # Call harmony-api AI search endpoint
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.valves.harmony_api_url}/ai-search",
                    json={"query": user_message},
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()

        except httpx.HTTPError as e:
            return f"Search failed: {e}"

        # Extract response
        return data.get("answer", "No answer provided")
