from __future__ import annotations

import dataclasses

import pydantic
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from harmony.models import AnonymousIdentity, UserIdentity
from harmony.services.admin import DomainExportItem

from ..._dependencies import require_role

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/admin/export", tags=["admin-export"])


class ExportRequest(BaseModel):
    domains: list[str]


@dataclasses.dataclass
class ExportDomainsResponse:
    domains: list[DomainExportItem]


@router.get("/domains")
async def list_export_domains(
    request: Request,
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> ExportDomainsResponse:
    export_service = request.app.state.export_service
    domains = await export_service.get_domains()
    return ExportDomainsResponse(domains=domains)


@router.post("/")
async def export_archive(
    body: ExportRequest,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> StreamingResponse:
    if not body.domains:
        raise HTTPException(status_code=422, detail="domains must not be empty")

    export_service = request.app.state.export_service
    audit_log = request.app.state.audit_log_service
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"

    await audit_log.record(
        user_id=user_id,
        action="export_started",
        entity_type="export",
        entity_id=None,
        details={"domains": body.domains},
    )

    stream = await export_service.export_archive(body.domains)

    return StreamingResponse(
        stream,
        media_type="application/gzip",
        headers={"Content-Disposition": "attachment; filename=harmony-export.tar.gz"},
    )


@router.post("/import")
async def import_archive(
    file: UploadFile,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
) -> dict[str, pydantic.JsonValue]:
    export_service = request.app.state.export_service
    audit_log = request.app.state.audit_log_service
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"

    file_content = await file.read()
    result = await export_service.import_archive(file_content)

    await audit_log.record(
        user_id=user_id,
        action="import_completed",
        entity_type="export",
        entity_id=None,
        details=result,
    )

    return result
