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


class CriticTask(BaseModel):
    user_query: str
    draft: str
    sources: list[dict[str, typing.Any]]


class SynthesizerTask(BaseModel):
    user_query: str
    sources: list[dict[str, typing.Any]]
    critique: dict[str, typing.Any] | None = None
    previous_draft: str | None = None
