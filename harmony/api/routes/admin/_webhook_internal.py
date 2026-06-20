from __future__ import annotations

import os

import pydantic
from fastapi import APIRouter, Header, HTTPException, Request

router = APIRouter()

_INTERNAL_TOKEN = os.environ.get("HARMONY_INTERNAL_TOKEN", "")


@router.post("/webhook/fire")
async def fire_webhook(
    request: Request,
    body: dict[str, pydantic.JsonValue],
    x_internal_token: str | None = Header(default=None),
) -> dict[str, str]:
    if _INTERNAL_TOKEN and x_internal_token != _INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid internal token")

    event = body.get("event", "")
    payload = body.get("payload", {})

    webhook_service = getattr(request.app.state, "webhook_service", None)
    if webhook_service is None:
        return {"status": "no_webhooks_configured"}

    await webhook_service.fire_event(event, payload)
    return {"status": "ok"}
