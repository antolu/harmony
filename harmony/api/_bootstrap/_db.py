from __future__ import annotations

import dataclasses
import typing

import structlog

from harmony.db.connection import get_async_pool
from harmony.services import SecretValueService
from harmony.services.admin import (
    ModelPolicyStore,
    ModelSettingsStore,
    ServiceConfigStore,
)

if typing.TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool

    from .._config import Settings

logger = structlog.get_logger(__name__)


@dataclasses.dataclass(frozen=True)
class DbServices:
    pool: AsyncConnectionPool
    service_config: ServiceConfigStore
    model_settings_store: ModelSettingsStore
    secret_service: SecretValueService
    model_policy_store: ModelPolicyStore


async def init_db(settings: Settings) -> DbServices:
    pool = await get_async_pool()
    logger.info("Connected to PostgreSQL")

    service_config = ServiceConfigStore()
    await service_config.initialize(pool)

    model_settings_store = ModelSettingsStore()

    secret_service = await SecretValueService.from_env_or_db(service_config)

    model_policy_store = ModelPolicyStore(pool)

    config_status = await service_config.get_status()
    logger.info(f"Service configuration: {config_status}")
    return DbServices(
        pool=pool,
        service_config=service_config,
        model_settings_store=model_settings_store,
        secret_service=secret_service,
        model_policy_store=model_policy_store,
    )
