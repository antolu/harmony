"""
title: Harmony Direct Search
author: Harmony Team
version: 0.1.0
"""

from __future__ import annotations

import os
import typing

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
        self.id = "harmony_direct_search"
        self.name = "Harmony"
        self.valves = self.Valves()

    def pipelines(self) -> list[dict[str, str]]:
        return [{"id": "harmony_direct_search", "name": "Direct Search"}]

    def _fetch_search_results(
        self, user_message: str, headers: dict[str, str]
    ) -> dict[str, typing.Any]:
        with httpx.Client() as client:
            response = client.get(
                f"{self.valves.harmony_api_url}/search",
                params={"q": user_message},
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict[str, typing.Any]],
        body: dict[str, typing.Any],
    ) -> str:
        """Process chat messages and return direct Elasticsearch results."""
        headers: dict[str, str] = {}
        if self.valves.service_api_key:
            headers["X-API-Key"] = self.valves.service_api_key
        try:
            data = self._fetch_search_results(user_message, headers)
        except httpx.HTTPError as e:
            return f"Search failed: {e}"

        total = data.get("total", 0)
        hits = data.get("hits", [])

        if total == 0:
            return "No results found for your query."

        max_highlight_length = 400
        max_snippet_length = 300
        result_text = f"Found {total} results:\n\n"

        for i, hit in enumerate(hits[:5], 1):
            title = hit.get("title", "Untitled")
            url = hit.get("url", "")
            domain = hit.get("domain", "")

            highlights = hit.get("highlights", {})
            highlighted_content = highlights.get("content", [])

            if highlighted_content:
                # Use first 2 highlighted passages for better context
                snippet = " ".join(highlighted_content[:2])
                # Limit to reasonable length
                if len(snippet) > max_highlight_length:
                    snippet = snippet[:max_highlight_length] + "..."
            else:
                # Fallback to raw snippet
                snippet = hit.get("snippet", "")[:max_snippet_length]
                if len(snippet) == max_snippet_length:
                    snippet += "..."

            # Convert Elasticsearch <mark> tags to markdown bold
            snippet = snippet.replace("<mark>", "**").replace("</mark>", "**")

            # Format as markdown with clickable link
            result_text += f"### {i}. [{title}]({url})\n"
            if domain:
                result_text += f"**{domain}**\n\n"
            result_text += f"{snippet}\n\n"
            result_text += "---\n\n"

        return result_text
