from __future__ import annotations

import structlog

from harmony.db.connection import get_async_pool
from harmony.db.repositories import ConversationRepo
from harmony.services.admin import AuditLogService, ServiceConfigStore

logger = structlog.get_logger(__name__)


async def nightly_audit_cleanup() -> None:
    pool = await get_async_pool()
    service_config = ServiceConfigStore()
    await service_config.initialize(pool=pool)
    audit_svc = AuditLogService()
    await audit_svc.initialize(pool)
    retention_days_str = await service_config.get("audit_retention_days")
    try:
        retention_days = int(retention_days_str) if retention_days_str else 90
    except ValueError:
        retention_days = 90
    deleted = await audit_svc.cleanup_audit_events(retention_days)
    logger.info(
        f"Nightly audit cleanup: removed {deleted} records older than {retention_days} days"
    )


async def nightly_conversation_cleanup() -> None:
    pool = await get_async_pool()
    service_config = ServiceConfigStore()
    await service_config.initialize(pool=pool)
    ttl_days_str = await service_config.get("conversation_ttl_days")
    try:
        ttl_days = int(ttl_days_str) if ttl_days_str else 0
    except ValueError:
        ttl_days = 0
    if ttl_days > 0:
        deleted = await ConversationRepo(pool).delete_older_than(ttl_days)
        logger.info(
            f"Nightly conversation cleanup: removed {deleted} conversations older than {ttl_days} days"
        )
