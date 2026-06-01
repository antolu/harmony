from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from harmony.api.dependencies import require_role

router = APIRouter(prefix="/admin/urls", tags=["admin"])


@router.get("/blacklist")
async def list_blacklist_patterns(
    request: Request,
    _: object = Depends(require_role("read-only")),
) -> dict[str, list[str]]:
    pool = request.app.state.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT pattern FROM crawl_blacklist")
    return {"patterns": [row["pattern"] for row in rows]}
