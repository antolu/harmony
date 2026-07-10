from __future__ import annotations

import dataclasses
import typing
from pathlib import Path

import structlog

from harmony.db.redis_client import get_sync_redis
from harmony.db.repositories import ConversationRepo
from harmony.services import (
    ConversationService,
    LLMService,
    PromptManager,
    make_document_cache,
)

if typing.TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool

    from harmony.services import DocumentCacheProtocol
    from harmony.services.admin import ModelPolicyStore, ServiceConfigStore

    from .._config import Settings

logger = structlog.get_logger(__name__)


@dataclasses.dataclass(frozen=True)
class CoreServices:
    llm_service: LLMService
    prompt_manager: PromptManager
    document_cache: DocumentCacheProtocol
    conversation_service: ConversationService


async def init_core_services(
    service_config: ServiceConfigStore,
    model_policy_store: ModelPolicyStore,
    pool: AsyncConnectionPool,
    settings: Settings,
) -> CoreServices:
    llm_service = LLMService(
        service_config=service_config,
        model_policy_store=model_policy_store,
    )

    templates_dir = Path(__file__).parent.parent.parent
    prompt_manager = PromptManager(
        templates_dir=templates_dir,
        auto_reload=settings.dev_mode,
    )

    logger.info(f"Initialized prompt manager with templates from {templates_dir}")

    cache_enabled = (
        await service_config.get("document_cache_enabled")
    ).lower() == "true"
    cache_ttl = int(await service_config.get("document_cache_ttl"))
    cache_max_size = int(await service_config.get("document_cache_max_size"))
    cache_backend = await service_config.get("document_cache_backend")

    cache_redis = await get_sync_redis() if cache_backend == "redis" else None
    document_cache = make_document_cache(
        cache_backend,
        redis=cache_redis,
        ttl=cache_ttl if cache_enabled else 3600,
        max_size=cache_max_size if cache_enabled else 1000,
    )
    if cache_enabled:
        logger.info(
            f"Document cache enabled: backend={cache_backend}, "
            f"TTL={cache_ttl}s, max_size={cache_max_size}"
        )

    conversation_service = ConversationService(repo=ConversationRepo(pool))
    return CoreServices(
        llm_service=llm_service,
        prompt_manager=prompt_manager,
        document_cache=document_cache,
        conversation_service=conversation_service,
    )
