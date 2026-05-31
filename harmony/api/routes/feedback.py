from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, field_validator

from harmony.api.dependencies import get_current_user, get_service_config_store
from harmony.api.models.user import AnonymousIdentity, UserIdentity
from harmony.api.services.admin import ServiceConfigStore
from harmony.db.repositories import MessageFeedbackRepo

router = APIRouter()


class FeedbackRequest(BaseModel):
    conversation_id: str
    message_id: int
    rating: Literal["up", "down"]

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: str) -> str:
        if v not in {"up", "down"}:
            msg = "rating must be 'up' or 'down'"
            raise ValueError(msg)
        return v


def _get_feedback_repo(request: Request) -> MessageFeedbackRepo:
    return MessageFeedbackRepo(request.app.state.db_pool)


async def _check_feedback_enabled(
    service_config: Annotated[ServiceConfigStore, Depends(get_service_config_store)],
) -> None:
    if await service_config.get("feedback_enabled") == "false":
        raise HTTPException(status_code=403, detail="Feedback is disabled")


def _require_user(current_user: UserIdentity | AnonymousIdentity) -> UserIdentity:
    if not isinstance(current_user, UserIdentity):
        raise HTTPException(status_code=401, detail="Authentication required")
    return current_user


@router.post("/")
async def submit_feedback(
    body: FeedbackRequest,
    request: Request,
    current_user: Annotated[
        UserIdentity | AnonymousIdentity, Depends(get_current_user)
    ],
    _enabled: Annotated[None, Depends(_check_feedback_enabled)],
) -> dict[str, bool]:
    user = _require_user(current_user)
    repo = _get_feedback_repo(request)
    await repo.upsert(body.conversation_id, body.message_id, user.id, body.rating)
    return {"success": True}


@router.delete("/{conversation_id}/{message_id}", status_code=204)
async def delete_feedback(
    conversation_id: str,
    message_id: int,
    request: Request,
    current_user: Annotated[
        UserIdentity | AnonymousIdentity, Depends(get_current_user)
    ],
    _enabled: Annotated[None, Depends(_check_feedback_enabled)],
) -> Response:
    user = _require_user(current_user)
    repo = _get_feedback_repo(request)
    await repo.delete_user_rating(conversation_id, message_id, user.id)
    return Response(status_code=204)


@router.get("/conversation/{conversation_id}")
async def get_conversation_feedback(
    conversation_id: str,
    request: Request,
    current_user: Annotated[
        UserIdentity | AnonymousIdentity, Depends(get_current_user)
    ],
) -> dict[str, list]:
    user = _require_user(current_user)
    repo = _get_feedback_repo(request)
    result = await repo.get_for_conversation(conversation_id, user.id)
    return {"feedback": result}
