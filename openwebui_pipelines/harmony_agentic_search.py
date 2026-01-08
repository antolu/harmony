"""
title: Harmony Agentic Search
author: Harmony Team
version: 0.4.0
"""

from __future__ import annotations

import json
import typing
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

    def pipelines(self) -> list[dict[str, str]]:
        return [{"id": "harmony_agentic_search", "name": "Agentic Search"}]

    def _handle_query_variant_event(
        self, data: dict[str, typing.Any], query_variants: list[str]
    ) -> str:
        """Handle query_variant event."""
        query_variants.append(data["variant"])
        return f"🔍 Searching: {data['variant']}\n\n"

    def _handle_reading_page_event(self, data: dict[str, typing.Any]) -> str:
        """Handle reading_page event."""
        return f"📖 Reading: {data['title']}\n\n"

    def _handle_refinement_round_event(self, data: dict[str, typing.Any]) -> str:
        """Handle refinement_round event."""
        if data["status"] == "completed" and data.get("consensus_reached"):
            return f"✅ Consensus reached (Round {data['round']})\n\n"
        return ""

    def _handle_answer_chunk_event(self, data: dict[str, typing.Any]) -> str:
        """Handle answer_chunk event."""
        return data["content"]

    def _handle_done_event(
        self,
        data: dict[str, typing.Any],
        sources: list[dict],
        refinement_rounds_ref: list[int],
        query_variants_ref: list[str],
    ) -> str:
        """Handle done event and generate footer."""
        sources.clear()
        sources.extend(data["sources"])
        refinement_rounds_ref[0] = data["refinement_rounds"]
        query_variants_ref.clear()
        query_variants_ref.extend(data["query_variants"])

        if sources:
            footer = "\n\n---\n\n**Sources:**\n"
            for i, src in enumerate(sources[:5], 1):
                title = src.get("title", "Untitled")
                url = src.get("url", "")
                footer += f"{i}. [{title}]({url})\n"

            footer += f"\n\n*Refined through {refinement_rounds_ref[0]} iteration(s) using {len(query_variants_ref)} query variant(s)*"
            return footer
        return ""

    def _handle_error_event(self, data: dict[str, typing.Any]) -> str:
        """Handle error event."""
        return f"\n\n⚠️ Error: {data['message']}"

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict[str, typing.Any]],
        body: dict[str, typing.Any],
    ) -> Generator[str, None, None]:
        """Process chat messages with multi-agent Agentic search (streaming)."""
        try:
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
                refinement_rounds_ref = [0]  # Use list to allow modification in handler
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

                        # Dispatch to appropriate handler
                        result = ""
                        if event_type == "query_variant":
                            result = self._handle_query_variant_event(
                                data, query_variants
                            )
                        elif event_type == "reading_page":
                            result = self._handle_reading_page_event(data)
                        elif event_type == "refinement_round":
                            result = self._handle_refinement_round_event(data)
                        elif event_type == "answer_chunk":
                            result = self._handle_answer_chunk_event(data)
                        elif event_type == "done":
                            result = self._handle_done_event(
                                data, sources, refinement_rounds_ref, query_variants
                            )
                        elif event_type == "error":
                            result = self._handle_error_event(data)

                        if result:
                            yield result

        except httpx.HTTPError as e:
            yield f"Agentic Search failed: {e}"
