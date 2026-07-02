from __future__ import annotations

import dataclasses

from pydantic import BaseModel

from harmony.authz import AuthorizationContext
from harmony.models import Source
from harmony.services._external_search import ExternalSearchContext


class QueryPlannerTask(BaseModel):
    user_query: str
    context: str | None = None


@dataclasses.dataclass
class PlannedQueries:
    semantic_query: str
    keyword_variants: list[str] = dataclasses.field(default_factory=list)


class SearcherTask(BaseModel):
    query: str
    keyword_variants: list[str] | None = None
    top_k: int = 10
    language: str | None = None
    authz_context: AuthorizationContext | None = None
    external_context: ExternalSearchContext | None = None
    sources: list[str] | None = None


@dataclasses.dataclass
class CritiqueDict:
    factual_accuracy: float = 0.5
    completeness: float = 0.5
    hallucination_risk: float = 0.5
    issues: list[str] = dataclasses.field(default_factory=list)
    suggestions: list[str] = dataclasses.field(default_factory=list)
    consensus_reached: bool = False
    missing_information: list[str] = dataclasses.field(default_factory=list)


class CriticTask(BaseModel):
    user_query: str
    draft: str
    sources: list[Source]


class SynthesizerTask(BaseModel):
    user_query: str
    sources: list[Source]
    critique: CritiqueDict | None = None
    previous_draft: str | None = None
