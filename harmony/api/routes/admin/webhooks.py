from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from harmony.api.dependencies import require_role
from harmony.api.models.user import UserIdentity

router = APIRouter(prefix="/admin/webhooks", tags=["admin"])

_ALLOWED_EVENTS = {"job_complete", "job_failed", "index_threshold"}


class WebhookCreateRequest(BaseModel):
    url: str
    secret: str | None = None
    events: list[str]


@router.get("")
async def list_webhooks(
    request: Request,
    _: object = Depends(require_role("read-only")),
) -> list[dict[str, object]]:
    return await request.app.state.webhook_service.list()


@router.post("")
async def create_webhook(
    body: WebhookCreateRequest,
    request: Request,
    current_user: object = Depends(require_role("admin")),
) -> dict[str, object]:
    unknown = set(body.events) - _ALLOWED_EVENTS
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown event types: {sorted(unknown)}. Allowed: {sorted(_ALLOWED_EVENTS)}",
        )
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    try:
        result = await request.app.state.webhook_service.create(
            url=body.url,
            secret=body.secret,
            events=body.events,
            created_by=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="webhook_created",
        entity_type="webhook",
        entity_id=str(result.get("id")),
        details={"url": body.url, "events": body.events},
    )
    return result


@router.patch("/{webhook_id}")
async def toggle_webhook(
    webhook_id: str,
    body: dict[str, bool],
    request: Request,
    current_user: object = Depends(require_role("operator")),
) -> dict[str, object]:
    enabled = body.get("enabled")
    if enabled is None:
        raise HTTPException(status_code=422, detail="'enabled' is required")
    webhook = await request.app.state.webhook_service.set_enabled(
        webhook_id, enabled=enabled
    )
    if webhook is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return webhook


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    request: Request,
    current_user: object = Depends(require_role("admin")),
) -> dict[str, bool]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    deleted = await request.app.state.webhook_service.delete(webhook_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Webhook '{webhook_id}' not found")
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="webhook_deleted",
        entity_type="webhook",
        entity_id=webhook_id,
        details={},
    )
    return {"deleted": True}
