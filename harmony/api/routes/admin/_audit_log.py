from __future__ import annotations

import dataclasses

from fastapi import APIRouter, Depends, Query, Request
from fastapi.encoders import jsonable_encoder

from harmony.models import AnonymousIdentity, UserIdentity

from ..._dependencies import require_role

router = APIRouter(prefix="/admin/audit-log", tags=["admin"])

_MAX_DAYS_BACK = 365
_MAX_LIMIT = 1000


@dataclasses.dataclass
class AuditLogQuery:
    user_id: str | None = Query(default=None)
    action: str | None = Query(default=None)
    days_back: int = Query(default=90)
    limit: int = Query(default=100)
    offset: int = Query(default=0)


@router.get("")
async def query_audit_log(
    request: Request,
    params: AuditLogQuery = Depends(),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> dict[str, object]:
    days_back = min(params.days_back, _MAX_DAYS_BACK)
    limit = min(params.limit, _MAX_LIMIT)
    events, total = await request.app.state.audit_log_service.query(
        user_id=params.user_id,
        action=params.action,
        days_back=days_back,
        limit=limit,
        offset=params.offset,
    )
    return {"events": [jsonable_encoder(e) for e in events], "total": total}
