from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from harmony.api.authz import AuthorizationContext
from harmony.api.dependencies import get_authz_context, get_conversation_service
from harmony.api.services import ConversationService

router = APIRouter()


class TitleUpdate(BaseModel):
    title: str


@router.get("/")
async def list_conversations(
    limit: int = 20,
    offset: int = 0,
    authz: AuthorizationContext = Depends(get_authz_context),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> dict:
    conversations, total = await conversation_service.list_for_user(
        str(authz.user_id), limit=limit, offset=offset
    )
    return {
        "conversations": conversations,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    authz: AuthorizationContext = Depends(get_authz_context),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> dict:
    messages = await conversation_service.get_messages(
        conversation_id, user_id=str(authz.user_id)
    )
    if messages is None:
        raise HTTPException(
            status_code=403, detail="Conversation not found or access denied"
        )
    return {"id": conversation_id, "messages": messages}


@router.patch("/{conversation_id}/title")
async def update_conversation_title(
    conversation_id: str,
    body: TitleUpdate,
    authz: AuthorizationContext = Depends(get_authz_context),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> dict:
    await conversation_service.update_title(
        conversation_id, body.title, str(authz.user_id)
    )
    return {"id": conversation_id, "title": body.title}


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    authz: AuthorizationContext = Depends(get_authz_context),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> None:
    await conversation_service.delete(conversation_id, str(authz.user_id))
