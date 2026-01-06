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

            # Extract hits from nested Elasticsearch response structure
            es_hits = response.get("hits", {}).get("hits", [])[:top_k]

            formatted_results = []
            for hit in es_hits:
                source = hit.get("_source", {})
                formatted_results.append({
                    "title": source.get("title", "Untitled"),
                    "url": source.get("url", ""),
                    "domain": source.get("domain", ""),
                    "content": source.get("content", ""),
                    "snippet": source.get("content", "")[:300],
                    "highlights": hit.get("highlight", {}),
                    "score": hit.get("_score", 0.0),
                })

            total = response.get("hits", {}).get("total", {}).get("value", 0)
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
