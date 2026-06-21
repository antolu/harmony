from __future__ import annotations

import logging
import os
import typing
from pathlib import Path
from urllib.parse import urlparse

import pydantic

from harmony.clients import ElasticsearchService
from harmony.core._elasticsearch_config import ESConfig
from harmony.db.repositories import ServiceConfigRepo

from ._config import IndexerConfigCLI as IndexerConfig

logger = logging.getLogger(__name__)


def transform_state_to_entry(
    state_doc: dict[str, pydantic.JsonValue],
    data_dir: Path,
) -> dict[str, pydantic.JsonValue] | None:
    if "file_path" not in state_doc or not state_doc["file_path"]:
        return None

    url = state_doc["url"]
    parsed = urlparse(str(url))

    entry = {
        "url": url,
        "domain": state_doc["domain"],
        "file_path": state_doc["file_path"],
        "depth": state_doc["depth"],
        "crawled_at": state_doc["last_crawled_at"],
        "path": state_doc.get("path", parsed.path or "/"),
        "language": state_doc.get("language", ""),
        "content_type": state_doc.get("content_type", ""),
        "_base_dir": str(data_dir),
    }

    if "type" in state_doc:
        entry["type"] = state_doc["type"]

    if "acl_allowed_roles" in state_doc:
        entry["acl_allowed_roles"] = state_doc["acl_allowed_roles"]
    if "acl_raw_claims" in state_doc:
        entry["acl_raw_claims"] = state_doc["acl_raw_claims"]

    return entry


async def load_entries_from_es(
    es_service: ElasticsearchService,
    state_index: str,
    data_dir: Path,
) -> list[dict[str, pydantic.JsonValue]]:
    if not await es_service.index_exists(state_index):
        logger.error(
            "state index '%s' does not exist; run crawler with state tracking enabled",
            state_index,
        )
        return []

    query: dict[str, pydantic.JsonValue] = {"query": {"match_all": {}}}
    logger.info("querying state index: %s", state_index)

    all_entries = []
    from elasticsearch.helpers import async_scan  # noqa: PLC0415

    async for doc in async_scan(es_service.client, query=query, index=state_index):
        state_doc = doc["_source"]
        entry = transform_state_to_entry(state_doc, data_dir)
        if entry:
            all_entries.append(entry)

    logger.info("loaded %d entries from ES state", len(all_entries))
    return all_entries


def group_entries_by_language(
    all_entries: list[dict[str, pydantic.JsonValue]],
) -> dict[str, list[dict[str, pydantic.JsonValue]]]:
    entries_by_lang: dict[str, list[dict[str, pydantic.JsonValue]]] = {}
    for entry in all_entries:
        lang_val = entry.get("language", "unknown")
        lang = str(lang_val) if lang_val else "unknown"
        if lang not in entries_by_lang:
            entries_by_lang[lang] = []
        entries_by_lang[lang].append(entry)
    return entries_by_lang


async def get_db_config(pool: typing.Any, key: str) -> str | None:
    try:
        repo = ServiceConfigRepo(pool)
        config = await repo.get(key)
        if config and config.is_configured:
            return str(config.value)
    except Exception:
        pass
    return None


async def resolve_es_host(config: IndexerConfig, pool: typing.Any = None) -> str:
    if config.es_host:
        return config.es_host

    env_host = os.environ.get("ES_HOST")
    if env_host:
        return env_host

    if pool:
        try:
            db_host = await get_db_config(pool, "elasticsearch_url")
            if db_host:
                logger.info("using ES config from database: %s", db_host)
                return db_host
        except Exception as e:
            logger.warning("DB config check failed: %s", e)

    default_host = "http://elasticsearch:9200"
    logger.warning("using default ES host: %s", default_host)
    return default_host


async def resolve_index_base_name(
    config: IndexerConfig, pool: typing.Any = None
) -> str:
    if config.index_base_name != "harmony":
        return config.index_base_name

    env_name = os.environ.get("ES_INDEX_BASE_NAME")
    if env_name:
        return env_name

    if pool:
        try:
            db_name = await get_db_config(pool, "es_index_base_name")
            if db_name:
                logger.info("using index base name from database: %s", db_name)
                return db_name
        except Exception as e:
            logger.warning("DB config check failed: %s", e)

    return "harmony"


async def resolve_languages(
    config: IndexerConfig, pool: typing.Any = None
) -> list[str]:
    if config.languages:
        return config.languages

    env_langs = os.environ.get("ES_LANGUAGES")
    if env_langs:
        return [lang.strip() for lang in env_langs.split(",") if lang.strip()]

    if pool:
        try:
            db_langs = await get_db_config(pool, "es_languages")
            if db_langs:
                langs = [lang.strip() for lang in db_langs.split(",") if lang.strip()]
                logger.info("using languages from database: %s", langs)
                return langs
        except Exception as e:
            logger.warning("DB config check failed: %s", e)

    return ["en", "fr"]


async def resolve_configs(
    config: IndexerConfig, pool: typing.Any = None
) -> tuple[str, str, list[str]]:
    final_es_host = await resolve_es_host(config, pool)
    final_index_base_name = await resolve_index_base_name(config, pool)
    final_languages = await resolve_languages(config, pool)
    return final_es_host, final_index_base_name, final_languages


def build_es_config(
    config: IndexerConfig,
    es_host: str,
    index_base_name: str,
    languages: list[str],
) -> ESConfig:
    if config.es_config and config.es_config.exists():
        es_config = ESConfig.from_yaml(config.es_config)
        logger.info("loaded ES config from %s", config.es_config)
        return es_config
    return ESConfig(host=es_host, index_base_name=index_base_name, languages=languages)


async def load_entries_from_source(
    config: IndexerConfig,
    es_host: str,
    index_base_name: str,
    languages: list[str],
    state_index: str,
) -> tuple[list[dict[str, pydantic.JsonValue]], ElasticsearchService, ESConfig] | None:
    if config.source != "elasticsearch" and (
        config.data_dir is None or not config.data_dir.exists()
    ):
        logger.error("data directory %s does not exist", config.data_dir)
        return None
    logger.info("loading from ES state index: %s", state_index)
    es_config = build_es_config(config, es_host, index_base_name, languages)
    es_service = ElasticsearchService(host=es_config.host, es_config=es_config)
    if not await es_service.health_check():
        logger.error("cannot connect to Elasticsearch")
        return None

    data_dir = config.data_dir or Path(".")
    all_entries = await load_entries_from_es(es_service, state_index, data_dir)
    if not all_entries:
        logger.warning("no documents found in state index")
        return None
    return all_entries, es_service, es_config
