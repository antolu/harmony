from __future__ import annotations

import logging
import typing

import psycopg_pool

from harmony.db.repositories import AuditEventRepo, SearchQueryLogRepo

logger = logging.getLogger(__name__)


class AuditLogService:
    def __init__(self) -> None:
        self._audit_repo: AuditEventRepo | None = None
        self._search_query_repo: SearchQueryLogRepo | None = None

    async def initialize(self, pool: psycopg_pool.AsyncConnectionPool) -> None:
        self._audit_repo = AuditEventRepo(pool)
        self._search_query_repo = SearchQueryLogRepo(pool)
        self._pool = pool

    async def record(
        self,
        user_id: str,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        details: dict[str, typing.Any] | None = None,
    ) -> None:
        if self._audit_repo is None:
            logger.warning("AuditLogService not initialized — skipping audit record")
            return
        await self._audit_repo.record(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )

    async def record_search(  # noqa: PLR0913
        self,
        user_id: str,
        query: str,
        language: str | None,
        result_count: int | None,
        latency_ms: int | None,
        tokens: int | None,
        mode: str | None,
    ) -> None:
        if self._search_query_repo is None:
            logger.warning("AuditLogService not initialized — skipping search log")
            return
        await self._search_query_repo.record(
            user_id=user_id,
            query=query,
            language=language,
            result_count=result_count,
            latency_ms=latency_ms,
            tokens=tokens,
            mode=mode,
        )

    async def query(
        self,
        user_id: str | None,
        action: str | None,
        days_back: int = 90,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, typing.Any]]:
        if self._audit_repo is None:
            logger.warning("AuditLogService not initialized — returning empty query")
            return []
        return await self._audit_repo.query(
            user_id=user_id,
            action=action,
            days_back=days_back,
            limit=limit,
            offset=offset,
        )

    async def cleanup_audit_events(self, retention_days: int) -> int:
        if self._audit_repo is None:
            return 0
        return await self._audit_repo.cleanup(retention_days)

    async def cleanup_search_query_log(self, retention_days: int) -> int:
        if not hasattr(self, "_pool"):
            return 0
        async with self._pool.connection() as conn:
            await conn.set_autocommit(True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM search_query_log WHERE created_at < now() - interval '1 day' * %s",
                    (retention_days,),
                )
                return cur.rowcount
