from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from harmony.authz import AuthorizationContext
from harmony.clients import ElasticsearchService
from harmony.services import ConversationService

from .._dependencies import (
    get_authz_context,
    get_conversation_service,
    get_es_service,
)
from ..exceptions import ResourceNotFoundError

router = APIRouter()

_SNIPPET_CHARS = 300


class TitleUpdate(BaseModel):
    title: str


class HydrateSourcesRequest(BaseModel):
    urls: list[str]


class HydratedSource(BaseModel):
    url: str
    title: str
    snippet: str
    domain: str


@router.get("/")
async def list_conversations(
    limit: int = 20,
    offset: int = 0,
    authz: AuthorizationContext = Depends(get_authz_context),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> dict:
    if authz.user_id == "anonymous":
        return {"conversations": [], "total": 0, "limit": limit, "offset": offset}
    conversations, total = await conversation_service.list_for_user(
        str(authz.user_id), limit=limit, offset=offset
    )
    return {
        "conversations": conversations,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/sources/hydrate")
async def hydrate_sources(
    body: HydrateSourcesRequest,
    authz: AuthorizationContext = Depends(get_authz_context),
    es_service: ElasticsearchService = Depends(get_es_service),
) -> dict[str, list[HydratedSource]]:
    """Resolve cited URLs to live title/snippet from the index, ACL-scoped.

    Indexed citations persist only their URL (the ES _id); presentation fields
    are looked up here so they stay current and old conversations self-heal.
    URLs not in the index (or not permitted) are simply absent from the result;
    the caller keeps its own fallback (a stored external snapshot or hostname).
    """
    if authz.user_id == "anonymous":
        raise HTTPException(status_code=403, detail="Login required")
    docs = await es_service.get_documents_by_ids(body.urls, authz.harmony_roles)
    hydrated = [
        HydratedSource(
            url=url,
            title=str(doc.get("title", "")),
            snippet=str(doc.get("content", ""))[:_SNIPPET_CHARS],
            domain=str(doc.get("domain") or urlparse(url).hostname or ""),
        )
        for url, doc in docs.items()
    ]
    return {"sources": hydrated}


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    authz: AuthorizationContext = Depends(get_authz_context),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> dict:
    if authz.user_id == "anonymous":
        raise HTTPException(status_code=403, detail="Login required")
    messages = await conversation_service.get_messages(
        conversation_id, user_id=str(authz.user_id)
    )
    if messages is None:
        raise HTTPException(
            status_code=403, detail="Conversation not found or access denied"
        )
    traces = await conversation_service.get_traces(conversation_id)
    return {"id": conversation_id, "messages": messages, "traces": traces}


@router.patch("/{conversation_id}/title")
async def update_conversation_title(
    conversation_id: str,
    body: TitleUpdate,
    authz: AuthorizationContext = Depends(get_authz_context),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> dict:
    if authz.user_id == "anonymous":
        raise HTTPException(status_code=403, detail="Login required")
    try:
        await conversation_service.update_title(
            conversation_id, body.title, str(authz.user_id)
        )
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"id": conversation_id, "title": body.title}


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    authz: AuthorizationContext = Depends(get_authz_context),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> None:
    if authz.user_id == "anonymous":
        raise HTTPException(status_code=403, detail="Login required")
    try:
        await conversation_service.delete(conversation_id, str(authz.user_id))
    except ResourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
