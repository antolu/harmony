"""
title: Harmony AI Search
author: Harmony Team
version: 0.1.0
"""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field


class Valves(BaseModel):
    harmony_api_url: str = Field(
        default="http://harmony-api:8000",
        description="Harmony API base URL",
    )


class Tools:
    def __init__(self) -> None:
        self.citation = False
        self.valves = Valves()

    async def harmony_search(
        self,
        query: str,
        __event_emitter__: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> str:
        """
        Search for information using Harmony's AI-powered search.
        This tool performs intelligent searches across the indexed documents
        and returns synthesized answers with source citations.

        :param query: The search query or question
        :return: AI-generated answer with citations
        """
        if not __event_emitter__:
            return "Event emitter not available - citations cannot be displayed."

        # Emit status message
        await __event_emitter__({
            "type": "status",
            "data": {"description": "Searching...", "done": False},
        })

        # Call Harmony API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.valves.harmony_api_url}/ai-search",
                    json={"query": query},
                    timeout=60.0,
                )
                response.raise_for_status()
                data = response.json()

        except httpx.HTTPError as e:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "Search failed", "done": True},
            })
            return f"Search failed: {e}"

        # Extract response data
        answer = data.get("answer", "No answer provided")
        sources = data.get("sources", [])

        # Emit citations for each source
        for source in sources:
            await __event_emitter__({
                "type": "citation",
                "data": {
                    "document": [source.get("snippet", "")],
                    "metadata": [
                        {
                            "date_accessed": datetime.now().isoformat(),
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

        # Update status
        await __event_emitter__({
            "type": "status",
            "data": {
                "description": f"Found {len(sources)} sources",
                "done": True,
            },
        })

        return answer
