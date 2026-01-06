from __future__ import annotations

import json
from typing import Any

from harmony.api.agents.base import AgentCapability, AgentResult, BaseAgent
from harmony.api.services.elasticsearch import ElasticsearchService


class SearcherAgent(BaseAgent):
    def __init__(self, es_service: ElasticsearchService) -> None:
        super().__init__()
        self.es_service = es_service
        self.name = "searcher"
        self.capability = AgentCapability(
            name="searcher",
            description="Execute Elasticsearch queries and retrieve relevant documents from the knowledge base",
            cost=0.5,
        )

    async def execute(self, task: dict[str, Any]) -> AgentResult:
        """Execute Elasticsearch search and format results."""
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
            response = await self.es_service.search(
                query=query,
                language=language,
            )

            hits = response.get("hits", [])[:top_k]

            formatted_results = [
                {
                    "title": hit.get("title", "Untitled"),
                    "url": hit.get("url", ""),
                    "domain": hit.get("domain", ""),
                    "content": hit.get("content", ""),
                    "snippet": hit.get("snippet", ""),
                    "highlights": hit.get("highlights", {}),
                    "score": hit.get("score", 0.0),
                }
                for hit in hits
            ]

            total = response.get("total", 0)
            confidence = min(1.0, total / 10.0) if total > 0 else 0.0

            return AgentResult(
                content=json.dumps(formatted_results),
                metadata={
                    "total": total,
                    "returned": len(formatted_results),
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
