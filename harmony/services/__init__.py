# ruff: noqa
from __future__ import annotations

from harmony._mod_replace import replace_modname
from ._secret_service import SecretValueService

replace_modname(SecretValueService, __name__)

__all__ = [
    "SecretValueService",
]

from ._conversation import ConversationService, ToolCallDict
from ._document_cache import (
    CacheEntry,
    DocumentCache,
    DocumentCacheProtocol,
    RedisDocumentCache,
    make_document_cache,
)
from ._external_search import (
    ExternalSearchContext,
    ExternalSearchService,
)
from ._llm import LLMContext, LLMService, use_model
from ._pipeline_config import PipelineConfig
from ._prompts import PromptManager
from ._search import SearchContext, SearchService
from ._status_sink import NullSink, StatusSink, null_sink

replace_modname(ConversationService, __name__)
replace_modname(ToolCallDict, __name__)
replace_modname(CacheEntry, __name__)
replace_modname(DocumentCache, __name__)
replace_modname(DocumentCacheProtocol, __name__)
replace_modname(RedisDocumentCache, __name__)
replace_modname(make_document_cache, __name__)
replace_modname(ExternalSearchContext, __name__)
replace_modname(ExternalSearchService, __name__)
replace_modname(LLMContext, __name__)
replace_modname(LLMService, __name__)
replace_modname(PipelineConfig, __name__)
replace_modname(PromptManager, __name__)
replace_modname(SearchContext, __name__)
replace_modname(SearchService, __name__)
replace_modname(NullSink, __name__)
replace_modname(StatusSink, __name__)
replace_modname(null_sink, __name__)

__all__.extend([
    "CacheEntry",
    "ConversationService",
    "ToolCallDict",
    "DocumentCache",
    "DocumentCacheProtocol",
    "ExternalSearchContext",
    "ExternalSearchService",
    "LLMContext",
    "LLMService",
    "NullSink",
    "PipelineConfig",
    "PromptManager",
    "RedisDocumentCache",
    "SearchContext",
    "SearchService",
    "StatusSink",
    "make_document_cache",
    "null_sink",
    "use_model",
])
