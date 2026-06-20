from __future__ import annotations

import json
import typing

import pydantic
from fastapi import APIRouter

from harmony.db.redis_client import get_async_redis

router = APIRouter()

_STATS_KEY_PREFIX = "crawl-stats-latest:"
_STATS_CHANNEL_PREFIX = "crawl-stats:"
_STATS_TTL_SECONDS = 604800  # 7 days


@router.post("/stats/{job_id}", status_code=201)
async def publish_stats(
    job_id: str, payload: dict[str, pydantic.JsonValue]
) -> dict[str, str]:
    redis = await get_async_redis()
    channel = f"{_STATS_CHANNEL_PREFIX}{job_id}"
    key = f"{_STATS_KEY_PREFIX}{job_id}"
    message = json.dumps(payload)

    await redis.publish(channel, message)

    str_payload = {str(k): str(json.dumps(v)) for k, v in payload.items()}
    await redis.hset(
        key,
        mapping=typing.cast(dict[str, str], str_payload),  # type: ignore[arg-type]
    )
    await redis.expire(key, _STATS_TTL_SECONDS)

    await redis.aclose()
    return {"status": "ok"}
