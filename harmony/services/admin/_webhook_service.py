from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime

import httpx
import psycopg_pool
import pydantic

from harmony.db.models import WebhookData, WebhookDeliveryData
from harmony.db.repositories import WebhookRepo

from .. import SecretValueService
from ._audit_log import AuditLogService

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 2


class WebhookService:
    def __init__(self) -> None:
        self._repo: WebhookRepo | None = None
        self._pool: psycopg_pool.AsyncConnectionPool | None = None
        self._secret_svc: SecretValueService | None = None
        self._audit_log: AuditLogService | None = None

    async def initialize(
        self, pool: psycopg_pool.AsyncConnectionPool, audit_log_service: AuditLogService
    ) -> None:
        self._repo = WebhookRepo(pool)
        self._pool = pool
        self._audit_log = audit_log_service

    def set_secret_service(self, secret_svc: SecretValueService) -> None:
        self._secret_svc = secret_svc

    async def create(
        self,
        url: str,
        secret: str | None,
        events: list[str],
        created_by: str,
    ) -> WebhookData:
        if not url.startswith("https://"):
            msg = "Webhook URL must start with https://"
            raise ValueError(msg)
        if self._repo is None:
            msg = "WebhookService not initialized"
            raise RuntimeError(msg)
        encrypted_secret: str | None = None
        if secret and self._secret_svc is not None:
            encrypted_secret = self._secret_svc.encrypt(secret)
        return await self._repo.create(url, encrypted_secret, events, created_by)

    async def list(self) -> list[WebhookData]:
        if self._repo is None:
            msg = "WebhookService not initialized"
            raise RuntimeError(msg)
        return await self._repo.list()

    async def delete(self, webhook_id: str) -> bool:
        if self._repo is None:
            msg = "WebhookService not initialized"
            raise RuntimeError(msg)
        return await self._repo.delete(webhook_id)

    async def set_enabled(
        self,
        webhook_id: str,
        *,
        enabled: bool,
    ) -> WebhookData | None:
        if self._pool is None:
            msg = "WebhookService not initialized"
            raise RuntimeError(msg)
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE webhooks SET enabled = %s WHERE id = %s RETURNING *",
                    (enabled, webhook_id),
                )
                row = await cur.fetchone()
                if row is None or not cur.description:
                    return None
                cols = [desc.name for desc in cur.description]
        return WebhookData(**dict(zip(cols, row, strict=True)))

    async def fire_event(
        self, event: str, payload: dict[str, pydantic.JsonValue]
    ) -> None:
        if self._repo is None:
            return
        webhooks: list[WebhookData] = await self._repo.get_for_event(event)
        for webhook in webhooks:
            task = asyncio.create_task(self._deliver(webhook, event, payload))
            task.add_done_callback(
                lambda t: t.exception() if not t.cancelled() else None
            )

    def _build_headers(self, body: bytes, secret: str | None) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if secret:
            sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={sig}"
        return headers

    async def _post_with_retry(
        self,
        url: str,
        body: bytes,
        secret: str | None,
    ) -> int:
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            attempts = attempt + 1
            try:
                headers = self._build_headers(body, secret)
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, content=body, headers=headers)
                    resp.raise_for_status()
            except Exception as exc:
                last_error = exc
                logger.warning(
                    f"Webhook delivery attempt {attempts} failed for {url}: {exc}"
                )
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_BACKOFF_BASE ** (attempt + 1))
            else:
                return attempts
        msg = f"All {_MAX_RETRIES} delivery attempts failed: {last_error}"
        raise RuntimeError(msg)

    async def _deliver(
        self, webhook: WebhookData, event: str, payload: dict[str, pydantic.JsonValue]
    ) -> None:
        secret: str | None = None
        secret_encrypted = webhook.secret_encrypted
        if secret_encrypted and self._secret_svc is not None:
            secret = self._secret_svc.decrypt(secret_encrypted)

        body = json.dumps(payload).encode()
        repo = self._repo
        if repo is None:
            return

        try:
            attempts = await self._post_with_retry(webhook.url, body, secret)
            await repo.record_delivery(
                WebhookDeliveryData(
                    webhook_id=webhook.id,
                    event=event,
                    status="delivered",
                    attempts=attempts,
                    error=None,
                    delivered_at=datetime.now(UTC),
                )
            )
        except Exception as exc:
            error_str = str(exc)
            await repo.record_delivery(
                WebhookDeliveryData(
                    webhook_id=webhook.id,
                    event=event,
                    status="failed",
                    attempts=_MAX_RETRIES,
                    error=error_str,
                    delivered_at=None,
                )
            )
            if self._audit_log is not None:
                await self._audit_log.record(
                    user_id="system",
                    action="webhook_delivery_failed",
                    entity_type="webhook",
                    entity_id=webhook.id,
                    details={"event": event, "url": webhook.url, "error": error_str},
                )
