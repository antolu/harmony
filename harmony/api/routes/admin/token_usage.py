from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from harmony.api.dependencies import get_current_user
from harmony.api.models.user import AnonymousIdentity, UserIdentity
from harmony.db.repositories import TokenUsageRepo

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
    request: Request,
    model: str | None = None,
    user_id: str | None = None,
    date_range: str | None = None,
    current_user: UserIdentity | AnonymousIdentity = Depends(get_current_user),
) -> list[dict]:
    if (
        not isinstance(current_user, UserIdentity)
        or current_user.harmony_role != "admin"
    ):
        raise HTTPException(status_code=403, detail="Admin role required")

    pool = request.app.state.db_pool
    repo = TokenUsageRepo(pool)
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
