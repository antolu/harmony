from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends

from harmony.db.repositories import TokenUsageRepo
from harmony.models import AnonymousIdentity, UserIdentity

from ..._dependencies import get_token_usage_repo, require_role

router = APIRouter()


def _date_range_to_from(date_range: str | None) -> str | None:
    if date_range is None or date_range == "all":
        return None
    now = datetime.now(UTC)
    if date_range == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    if date_range == "7d":
        return (now - timedelta(days=7)).isoformat()
    if date_range == "30d":
        return (now - timedelta(days=30)).isoformat()
    return None


@router.get("/token-usage")
async def get_token_usage(
    model: str | None = None,
    user_id: str | None = None,
    date_range: str | None = None,
    repo: TokenUsageRepo = Depends(get_token_usage_repo),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("admin")),
) -> list[dict]:
    date_from = _date_range_to_from(date_range)
    rows = await repo.query(model=model, user_id=user_id, date_from=date_from)
    return [
        {
            "user_id": r["user_id"],
            "model": r["model"],
            "usage_date": str(r["usage_date"]),
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
            "total_tokens": r["total_tokens"],
        }
        for r in rows
    ]
