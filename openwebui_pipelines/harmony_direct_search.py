"""
title: Harmony Direct Search
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
        self.id = "harmony_direct_search"
        self.name = "Harmony"
        self.valves = self.Valves()

    def pipelines(self) -> list[dict[str, str]]:  # noqa: PLR6301
        return [{"id": "harmony_direct_search", "name": "Direct Search"}]

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict],
        body: dict,
    ) -> str:
        """Process chat messages and return direct Elasticsearch results."""
        # Call harmony-api direct search endpoint
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.valves.harmony_api_url}/search",
                    params={"q": user_message},
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

        except httpx.HTTPError as e:
            return f"Search failed: {e}"

        # Extract results
        total = data.get("total", 0)
        hits = data.get("hits", [])

        if total == 0:
            return "No results found for your query."

        # Format results
        result_text = f"Found {total} results:\n\n"

        for i, hit in enumerate(hits[:5], 1):
            title = hit.get("title", "Untitled")
            url = hit.get("url", "")
            snippet = hit.get("snippet", "")
            score = hit.get("score", 0)

            result_text += f"**{i}. {title}**\n"
            result_text += f"Score: {score:.2f}\n"
            if snippet:
                result_text += f"{snippet[:200]}...\n"
            result_text += f"URL: {url}\n\n"

        return result_text
