"""
title: Harmony AI Search
author: Harmony Team
version: 0.4.0
"""

from __future__ import annotations

import json
from collections.abc import Generator

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

    def pipe(  # noqa: PLR0912
        self,
        user_message: str,
        model_id: str,
        messages: list[dict],
        body: dict,
    ) -> Generator[str, None, None]:
        """Process chat messages and return AI search results (streaming)."""
        try:  # noqa: PLR1702
            with (
                httpx.Client(timeout=120.0) as client,
                client.stream(
                    "POST",
                    f"{self.valves.harmony_api_url}/ai-search",
                    json={"query": user_message},
                ) as response,
            ):
                response.raise_for_status()

                # Track sources for final summary
                sources: list[dict] = []
                event_type = None

                # Parse SSE stream
                for line in response.iter_lines():
                    if not line or line.startswith(":"):
                        continue

                    if line.startswith("event: "):
                        event_type = line[7:].strip()
                        continue

                    if line.startswith("data: ") and event_type:
                        data = json.loads(line[6:])

                        # Handle different event types
                        if event_type == "tool_call":
                            function = data.get("function", "")
                            if function == "search_documents":
                                query = data.get("arguments", {}).get("query", "")
                                yield f"🔍 Searching: {query}\n\n"

                        elif event_type == "reading_page":
                            yield f"📖 Reading: {data['title']}\n\n"

                        elif event_type == "answer_chunk":
                            yield data["content"]

                        elif event_type == "done":
                            sources = data.get("sources", [])

                            # Add sources footer
                            if sources:
                                footer = "\n\n---\n\n**Sources:**\n"
                                for i, src in enumerate(sources[:5], 1):
                                    title = src.get("title", "Untitled")
                                    url = src.get("url", "")
                                    footer += f"{i}. [{title}]({url})\n"
                                yield footer

                        elif event_type == "error":
                            yield f"\n\n⚠️ Error: {data['message']}"

        except httpx.HTTPError as e:
            yield f"Search failed: {e}"
