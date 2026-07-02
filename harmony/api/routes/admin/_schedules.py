from __future__ import annotations

from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from harmony.models import AnonymousIdentity, UserIdentity

from ..._dependencies import require_role

router = APIRouter(prefix="/admin/schedules", tags=["admin"])


class ScheduleCreateRequest(BaseModel):
    config_name: str
    cron_expr: str


@router.get("")
async def list_schedules(
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> list[dict[str, object]]:
    return await request.app.state.schedule_service.list_schedules()


@router.post("")
async def create_schedule(
    body: ScheduleCreateRequest,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, object]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    try:
        CronTrigger.from_crontab(body.cron_expr)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid cron expression: {e}"
        ) from e
    try:
        await request.app.state.schedule_service.add_crawl_schedule(
            body.config_name, body.cron_expr
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="schedule_created",
        entity_type="schedule",
        entity_id=body.config_name,
        details={"config_name": body.config_name, "cron_expr": body.cron_expr},
    )
    return {"config_name": body.config_name, "cron_expr": body.cron_expr}


@router.delete("/{config_name}")
async def delete_schedule(
    config_name: str,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, bool]:
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"
    removed = await request.app.state.schedule_service.remove_crawl_schedule(
        config_name
    )
    if not removed:
        raise HTTPException(
            status_code=404, detail=f"Schedule for '{config_name}' not found"
        )
    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="schedule_deleted",
        entity_type="schedule",
        entity_id=config_name,
        details={"config_name": config_name},
    )
    return {"deleted": True}
