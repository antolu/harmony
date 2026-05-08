from __future__ import annotations

import json
import typing

from harmony.api.agents._base import AgentCapability, AgentResult, BaseAgent
from harmony.api.services import SearchService


class SearcherAgent(BaseAgent):
    def __init__(self, search_service: SearchService) -> None:
        super().__init__()
        self._search_service = search_service
        self.name = "searcher"
        self.capability = AgentCapability(
            name="searcher",
            description="Execute hybrid search and retrieve relevant documents from the knowledge base",
            cost=0.5,
        )

    async def execute(self, task: dict[str, typing.Any]) -> AgentResult:
        query = task.get("query", "")
        language = task.get("language")
        top_k = task.get("top_k", 10)

        if not query:
            return AgentResult(
                content=json.dumps([]),
                metadata={"total": 0, "error": "Empty query"},
                confidence=0.0,
            )

        try:
            hits = await self._search_service.search(
                query,
                language=language,
                top_k=top_k,
            )

            formatted_results = [
                {
                    "title": h.metadata.get("title", "Untitled"),
                    "url": h.path,
                    "domain": h.metadata.get("domain", ""),
                    "content": h.metadata.get("content", ""),
                    "snippet": str(h.metadata.get("content", ""))[:300],
                    "score": h.score,
                }
                for h in hits
            ]

            confidence = min(1.0, len(hits) / 10.0) if hits else 0.0

            return AgentResult(
                content=json.dumps(formatted_results),
                metadata={
                    "total": len(hits),
                    "returned": len(hits),
                    "query": query,
                    "language": language,
                },
                confidence=confidence,
            )

        except Exception as e:
            return AgentResult(
                content=json.dumps([]),
                metadata={"error": str(e), "query": query},
                confidence=0.0,
            )
