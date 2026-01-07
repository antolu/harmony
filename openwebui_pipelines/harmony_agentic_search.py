"""
title: Harmony Agentic Search
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
        max_refinement_rounds: int = Field(
            default=3,
            ge=1,
            le=5,
            description="Maximum k-round refinement iterations",
        )

    def __init__(self) -> None:
        self.type = "manifold"
        self.id = "harmony_agentic_search"
        self.name = "Harmony"
        self.valves = self.Valves()

    def pipelines(self) -> list[dict[str, str]]:  # noqa: PLR6301
        return [{"id": "harmony_agentic_search", "name": "Agentic Search"}]

    def pipe(  # noqa: PLR0912
        self,
        user_message: str,
        model_id: str,
        messages: list[dict],
        body: dict,
    ) -> Generator[str, None, None]:
        """Process chat messages with multi-agent Agentic search (streaming)."""
        try:  # noqa: PLR1702
            with (
                httpx.Client(timeout=120.0) as client,
                client.stream(
                    "POST",
                    f"{self.valves.harmony_api_url}/agentic-search",
                    json={
                        "query": user_message,
                        "max_refinement_rounds": self.valves.max_refinement_rounds,
                    },
                ) as response,
            ):
                response.raise_for_status()

                # Track metadata for final summary
                sources: list[dict] = []
                refinement_rounds = 0
                query_variants: list[str] = []
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
                        if event_type == "query_variant":
                            query_variants.append(data["variant"])
                            yield f"🔍 Searching: {data['variant']}\n\n"

                        elif event_type == "reading_page":
                            yield f"📖 Reading: {data['title']}\n\n"

                        elif event_type == "refinement_round":
                            if data["status"] == "completed":
                                refinement_rounds = data["round"]
                                if data.get("consensus_reached"):
                                    yield f"✅ Consensus reached (Round {data['round']})\n\n"

                        elif event_type == "answer_chunk":
                            yield data["content"]

                        elif event_type == "done":
                            sources = data["sources"]
                            refinement_rounds = data["refinement_rounds"]
                            query_variants = data["query_variants"]

                            # Add sources footer
                            if sources:
                                footer = "\n\n---\n\n**Sources:**\n"
                                for i, src in enumerate(sources[:5], 1):
                                    title = src.get("title", "Untitled")
                                    url = src.get("url", "")
                                    footer += f"{i}. [{title}]({url})\n"

                                footer += f"\n\n*Refined through {refinement_rounds} iteration(s) using {len(query_variants)} query variant(s)*"
                                yield footer

                        elif event_type == "error":
                            yield f"\n\n⚠️ Error: {data['message']}"

        except httpx.HTTPError as e:
            yield f"Agentic Search failed: {e}"
