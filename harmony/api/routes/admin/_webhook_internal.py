from __future__ import annotations

import typing

from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/webhook/fire")
async def fire_webhook(request: Request, body: dict[str, typing.Any]) -> dict[str, str]:
    event = body.get("event", "")
    payload = body.get("payload", {})

    webhook_service = getattr(request.app.state, "webhook_service", None)
    if webhook_service is None:
        return {"status": "no_webhooks_configured"}

    await webhook_service.fire_event(event, payload)
    return {"status": "ok"}
