from __future__ import annotations

from kv_search import (
    KeywordSearchBackend,
    SemanticResult,
    SemanticSearchBackend,
    VectorSearchBackend,
)
from kv_search._interfaces import LLMCompletionFn


class HarmonySemanticBackend(SemanticSearchBackend):
    async def semantic_search(  # noqa: PLR0913
        self,
        query: str,
        *,
        keyword_backend: KeywordSearchBackend | None = None,
        vector_backend: VectorSearchBackend | None = None,
        llm: LLMCompletionFn | None = None,
        system_prompt: str | None = None,
        top_n: int = 10,
    ) -> list[SemanticResult]:
        msg = "Semantic search is not yet implemented"
        raise NotImplementedError(msg)
