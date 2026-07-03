from __future__ import annotations

import dataclasses
import typing

import structlog

from harmony.infrastructure.search import (
    HarmonyKeywordBackend,
    HarmonyRerankerBackend,
    HarmonyVectorBackend,
    KeywordBackendConfig,
)
from harmony.services import ExternalSearchService, SearchService

from .._settings import load_pipeline_config

if typing.TYPE_CHECKING:
    from harmony.clients import QdrantService
    from harmony.services import PipelineConfig, SecretValueService
    from harmony.services.admin import (
        ModelRegistryService,
        ModelSettingsStore,
        ServiceConfigStore,
    )

    from .._config import Settings

logger = structlog.get_logger(__name__)


@dataclasses.dataclass(frozen=True)
class SearchComponents:
    pipeline_config: PipelineConfig
    keyword_backend: HarmonyKeywordBackend
    external_search_service: ExternalSearchService
    search_service: SearchService


async def init_search_service(  # noqa: PLR0913
    service_config: ServiceConfigStore,
    model_settings_store: ModelSettingsStore,
    settings: Settings,
    qdrant_service: QdrantService | None,
    model_registry_service: ModelRegistryService,
    secret_service: SecretValueService,
) -> SearchComponents:
    pipeline_config = await load_pipeline_config(service_config)
    if qdrant_service is None or await qdrant_service.is_empty():
        pipeline_config = dataclasses.replace(
            pipeline_config, vector_search_enabled=False
        )
        if qdrant_service is not None:
            logger.info(
                "Qdrant collection empty — vector search disabled until first embed job"
            )

    keyword_backend = HarmonyKeywordBackend(
        KeywordBackendConfig(
            host=settings.es_config.host,
            index_base_name=settings.es_config.index_base_name,
            languages=settings.es_config.languages,
            size=pipeline_config.keyword_candidates_n,
        ),
        service_config=service_config,
    )
    vector_backend = HarmonyVectorBackend(
        qdrant_service=qdrant_service,
        service_config=service_config,
        model_settings_store=model_settings_store,
        model_registry=model_registry_service,
    )
    reranker_backend = HarmonyRerankerBackend(
        service_config=service_config,
        model_settings_store=model_settings_store,
        model_registry=model_registry_service,
    )
    external_search_service = ExternalSearchService(
        service_config=service_config,
        secret_service=secret_service,
    )

    search_service = SearchService(
        keyword_backend=keyword_backend,
        vector_backend=vector_backend,
        reranker_backend=reranker_backend,
        config=pipeline_config,
        external_search_service=external_search_service,
    )
    logger.info("SearchService initialized with pipeline config: %s", pipeline_config)
    return SearchComponents(
        pipeline_config=pipeline_config,
        keyword_backend=keyword_backend,
        external_search_service=external_search_service,
        search_service=search_service,
    )
