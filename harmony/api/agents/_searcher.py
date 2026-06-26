from __future__ import annotations

import json
import typing

from harmony.api.agents._base import (
    AgentCapability,
    AgentResult,
    BaseAgent,
    StatusSinkProtocol,
)
from harmony.api.agents._models import SearcherTask
from harmony.api.authz import AuthorizationContext
from harmony.api.services import SearchService
from harmony.api.services._search import SearchContext

if typing.TYPE_CHECKING:
    pass


class SearcherAgent(BaseAgent[SearcherTask]):
    def __init__(
        self,
        search_service: SearchService,
        authz_context: AuthorizationContext | None = None,
    ) -> None:
        super().__init__()
        self._search_service = search_service
        self._authz_context = authz_context
        self.name = "searcher"
        self.capability = AgentCapability(
            name="searcher",
            description="Execute hybrid search and retrieve relevant documents from the knowledge base",
            cost=0.5,
        )

    async def execute(
        self, task: SearcherTask, sink: StatusSinkProtocol
    ) -> AgentResult:
        query = task.query
        keyword_variants = task.keyword_variants
        language = task.language
        top_k = task.top_k
        authz_context = task.authz_context or self._authz_context
        external_context = task.external_context
        sources = task.sources

        if not query:
            return AgentResult(
                content=json.dumps([]),
                metadata={"total": 0, "error": "Empty query"},
                confidence=0.0,
            )

        try:
            hits = await self._search_service.search(
                SearchContext(
                    query=query,
                    primary_query=query,
                    keyword_variants=keyword_variants,
                    language=language,
                    top_k=top_k,
                    authz_context=authz_context,
                    external_context=external_context,
                    sources=sources,
                )
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
