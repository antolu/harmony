from __future__ import annotations

import typing

from pydantic import BaseModel

from harmony.api.authz import AuthorizationContext
from harmony.api.services._external_search import ExternalSearchContext


class QueryPlannerTask(BaseModel):
    user_query: str
    context: str | None = None


class SearcherTask(BaseModel):
    query: str
    top_k: int = 10
    language: str | None = None
    authz_context: AuthorizationContext | None = None
    external_context: ExternalSearchContext | None = None
    sources: list[str] | None = None


class SourceDict(typing.TypedDict, total=False):
    title: str
    url: str
    domain: str
    content: str
    snippet: str
    score: float


class CritiqueDict(typing.TypedDict, total=False):
    factual_accuracy: float
    completeness: float
    hallucination_risk: float
    issues: list[str]
    suggestions: list[str]
    consensus_reached: bool


class CriticTask(BaseModel):
    user_query: str
    draft: str
    sources: list[SourceDict]


class SynthesizerTask(BaseModel):
    user_query: str
    sources: list[SourceDict]
    critique: CritiqueDict | None = None
    previous_draft: str | None = None
