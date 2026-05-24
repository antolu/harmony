"""
title: Harmony AI Search
author: Harmony Team
version: 0.4.0
"""

from __future__ import annotations

import json
import os
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
        service_api_key: str = Field(
            default_factory=lambda: os.getenv("SERVICE_API_KEY", ""),
            description="API key for authenticating with Harmony API",
        )

    def __init__(self) -> None:
        self.type = "manifold"
        self.id = "harmony_search"
        self.name = "Harmony"
        self.valves = self.Valves()

    def pipelines(self) -> list[dict[str, str]]:
        return [{"id": "harmony_ai_search", "name": "AI Search (Gemini)"}]

    def _handle_tool_call_event(self, data: dict[str, typing.Any]) -> str:
        """Handle tool_call event."""
        function = data.get("function", "")
        if function == "search_documents":
            query = data.get("arguments", {}).get("query", "")
            return f"🔍 Searching: {query}\n\n"
        return ""

    def _handle_reading_page_event(self, data: dict[str, typing.Any]) -> str:
        """Handle reading_page event."""
        return f"📖 Reading: {data['title']}\n\n"

    def _handle_answer_chunk_event(self, data: dict[str, typing.Any]) -> str:
        """Handle answer_chunk event."""
        return data["content"]

    def _handle_done_event(self, data: dict[str, typing.Any]) -> str:
        """Handle done event and generate sources footer."""
        sources = data.get("sources", [])
        if sources:
            footer = "\n\n---\n\n**Sources:**\n"
            for i, src in enumerate(sources[:5], 1):
                title = src.get("title", "Untitled")
                url = src.get("url", "")
                footer += f"{i}. [{title}]({url})\n"
            return footer
        return ""

    def _handle_error_event(self, data: dict[str, typing.Any]) -> str:
        """Handle error event."""
        return f"\n\n⚠️ Error: {data['message']}"

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict],
        body: dict,
    ) -> Generator[str, None, None]:
        """Process chat messages and return AI search results (streaming)."""
        headers = {}
        if self.valves.service_api_key:
            headers["X-API-Key"] = self.valves.service_api_key
        try:
            yield from self._stream_ai_search(user_message, headers)
        except httpx.HTTPError as e:
            yield f"Search failed: {e}"

    def _stream_ai_search(
        self,
        user_message: str,
        headers: dict[str, str],
    ) -> Generator[str, None, None]:
        with (
            httpx.Client(timeout=120.0) as client,
            client.stream(
                "POST",
                f"{self.valves.harmony_api_url}/ai-search",
                json={"query": user_message},
                headers=headers,
            ) as response,
        ):
            response.raise_for_status()

            event_type = None

            for line in response.iter_lines():
                if not line or line.startswith(":"):
                    continue

                if line.startswith("event: "):
                    event_type = line[7:].strip()
                    continue

                if line.startswith("data: ") and event_type:
                    data = json.loads(line[6:])

                    result = ""
                    if event_type == "tool_call":
                        result = self._handle_tool_call_event(data)
                    elif event_type == "reading_page":
                        result = self._handle_reading_page_event(data)
                    elif event_type == "answer_chunk":
                        result = self._handle_answer_chunk_event(data)
                    elif event_type == "done":
                        result = self._handle_done_event(data)
                    elif event_type == "error":
                        result = self._handle_error_event(data)

                    if result:
                        yield result
