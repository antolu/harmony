"""
title: Harmony Direct Search
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
        self.id = "harmony_direct_search"
        self.name = "Harmony"
        self.valves = self.Valves()

    def pipelines(self) -> list[dict[str, str]]:  # noqa: PLR6301
        return [{"id": "harmony_direct_search", "name": "Direct Search"}]

    async def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict],
        body: dict,
    ) -> AsyncGenerator[str, None] | str:
        """Process chat messages and return direct Elasticsearch results."""
        # Get event emitter from body if available
        __event_emitter__ = body.get("__event_emitter__")

        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "Searching...", "done": False},
            })

        # Call harmony-api direct search endpoint
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.valves.harmony_api_url}/search",
                    params={"q": user_message},
                    timeout=30.0,
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

        # Extract results
        total = data.get("total", 0)
        hits = data.get("hits", [])

        if total == 0:
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": "No results found", "done": True},
                })
            yield "No results found for your query."
            return

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

            # Emit citation
            if __event_emitter__:
                await __event_emitter__({
                    "type": "citation",
                    "data": {
                        "document": [snippet],
                        "metadata": [
                            {
                                "source": title,
                                "url": url,
                                "score": score,
                            }
                        ],
                        "source": {"name": title, "url": url},
                    },
                })

        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {
                    "description": f"Found {len(hits)} results",
                    "done": True,
                },
            })

        yield result_text
