"""
title: Harmony AI Search
author: Harmony Team
version: 0.1.0
"""

from collections.abc import AsyncGenerator

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

    async def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict],
        body: dict,
    ) -> AsyncGenerator[str, None] | str:
        """Process chat messages and return AI search results."""
        # Get event emitter from body if available
        __event_emitter__ = body.get("__event_emitter__")

        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "Searching...", "done": False},
            })

        # Call harmony-api AI search endpoint
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.valves.harmony_api_url}/ai-search",
                    json={"query": user_message},
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()

        except httpx.HTTPError as e:
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": "Search failed", "done": True},
                })
            yield f"Search failed: {e}"
            return

        # Extract response
        answer = data.get("answer", "No answer provided")
        sources = data.get("sources", [])

        # Emit citations
        if __event_emitter__:
            for source in sources:
                await __event_emitter__({
                    "type": "citation",
                    "data": {
                        "document": [source.get("snippet", "")],
                        "metadata": [
                            {
                                "source": source.get("title", "Unknown"),
                                "url": source.get("url", ""),
                            }
                        ],
                        "source": {
                            "name": source.get("title", "Unknown"),
                            "url": source.get("url", ""),
                        },
                    },
                })

            await __event_emitter__({
                "type": "status",
                "data": {
                    "description": f"Found {len(sources)} sources",
                    "done": True,
                },
            })

        yield answer
