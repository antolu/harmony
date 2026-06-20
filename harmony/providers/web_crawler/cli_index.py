from __future__ import annotations

import asyncio
import collections.abc
import logging
import os
import sys
import typing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import bs4
import httpx
import litellm
import pydantic
import qdrant_client
from elasticsearch import Elasticsearch, helpers
from jsonargparse import ActionConfigFile, ArgumentParser

from harmony.config.elasticsearch import ESConfig
from harmony.config.indexer import IndexerConfig
from harmony.core import (
    BackendStatsWriter,
    CorruptDocumentError,
    StatsWriter,
    default_registry,
    language_detector,
)
from harmony.core import url_to_id as _url_to_id
from harmony.db.connection import close_async_pool, get_async_pool
from harmony.db.repositories import IndexerCheckpointRepo, ServiceConfigRepo

logger = logging.getLogger(__name__)


@dataclass
class IndexingContext:
    stats_writer: StatsWriter | None
    already_indexed: int
    total_documents: int
    stats: dict[str, int]
    checkpoint_repo: IndexerCheckpointRepo | None = None
    config_name: str = ""


@dataclass
class BulkIndexContext:
    es: Elasticsearch
    all_entries: list[dict[str, pydantic.JsonValue]]
    index_name: str
    batch_size: int
    ctx: IndexingContext
    threshold: int = 0
    backend_url: str | None = None
    threshold_fired: bool = False


@dataclass
class EmbedBatchContext:
    client: typing.Any
    litellm: typing.Any
    qdrant_client: typing.Any
    urls: list[str]
    texts: list[str]
    embedding_model: str
    qdrant_collection: str
    exists: bool
    batch_index: int


@dataclass
class EmbedContext:
    all_entries: list[dict[str, pydantic.JsonValue]]
    qdrant_host: str
    qdrant_collection: str
    embedding_model: str
    batch_size: int
    stats_writer: StatsWriter | None = None


@dataclass
class IndexByLanguageContext:
    all_entries: list[dict[str, pydantic.JsonValue]]
    es: Elasticsearch
    es_config: ESConfig
    config: IndexerConfig
    stats_writer: StatsWriter | None
    checkpoint_repo: IndexerCheckpointRepo | None = None
    config_name: str = ""
    recreate: bool = False


@dataclass
class RunIndexingContext:
    args: typing.Any
    config: IndexerConfig
    checkpoint_repo: IndexerCheckpointRepo | None
    config_name: str
    final_es_host: str
    final_index_base_name: str
    final_languages: list[str]
    state_index: str
    stats_writer: StatsWriter | None


def _make_stats_writer() -> StatsWriter | None:
    job_id = os.environ.get("HARMONY_CRAWL_JOB_ID")
    backend_url = os.environ.get("HARMONY_BACKEND_URL")
    if job_id and backend_url:
        return BackendStatsWriter(backend_url, job_id)
    return None


def _publish_stats(
    writer: StatsWriter | None,
    *,
    phase: str,
    indexed: int,
    total: int,
) -> None:
    if writer is None:
        return
    writer.publish({
        "timestamp": datetime.now(UTC).isoformat(),
        "current_phase": phase,
        "documents_indexed": indexed,
        "total_documents": total,
    })


def extract_text_from_html(html: str | bytes) -> tuple[str, str]:
    soup = bs4.BeautifulSoup(html, "lxml")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    for script in soup(["script", "style"]):
        script.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = " ".join(text.split())

    return title, text


def _group_entries_by_language(
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


def _transform_state_to_entry(
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


def _load_entries_from_es(
    es: Elasticsearch,
    state_index: str,
    data_dir: Path,
) -> list[dict[str, pydantic.JsonValue]]:
    if not es.indices.exists(index=state_index):
        logger.error(
            "state index '%s' does not exist; run crawler with state tracking enabled",
            state_index,
        )
        return []

    query: dict[str, pydantic.JsonValue] = {"query": {"match_all": {}}}
    logger.info("querying state index: %s", state_index)

    all_entries = []
    for doc in helpers.scan(es, query=query, index=state_index):
        state_doc = doc["_source"]
        entry = _transform_state_to_entry(state_doc, data_dir)
        if entry:
            all_entries.append(entry)

    logger.info("loaded %d entries from ES state", len(all_entries))
    return all_entries


def _process_document(
    entry: dict[str, pydantic.JsonValue], file_path: Path
) -> tuple[str | None, str | None]:
    content_type = entry.get("content_type", "")
    extension = file_path.suffix

    parser = default_registry.get_parser(str(content_type), extension)
    if not parser:
        logger.warning(
            "no parser for %s (%s): %s", content_type, extension, file_path.name
        )
        return None, None

    try:
        title, content = parser.parse(file_path)
    except CorruptDocumentError:
        logger.exception("parse error %s", file_path.name)
        return None, None
    else:
        return title, content


def _sync_deletions(
    es: Elasticsearch,
    state_index: str,
    content_index: str,
    missing_threshold: int,
) -> None:
    logger.info("syncing deletions from crawl state...")

    if not es.indices.exists(index=state_index):
        logger.error("state index %s does not exist", state_index)
        return

    try:
        _sync_deletions_inner(es, state_index, content_index, missing_threshold)
    except Exception:
        logger.exception("error during deletion sync")


def _sync_deletions_inner(
    es: Elasticsearch,
    state_index: str,
    content_index: str,
    missing_threshold: int,
) -> None:
    query = {"query": {"range": {"missing_count": {"gte": missing_threshold}}}}
    response = es.search(index=state_index, body=query, size=10000, source=False)
    urls_to_delete = [hit["_id"] for hit in response["hits"]["hits"]]

    if not urls_to_delete:
        logger.info("no URLs to delete")
        return

    logger.info("deleting %d URLs...", len(urls_to_delete))
    delete_actions = [
        {"_op_type": "delete", "_index": content_index, "_id": url}
        for url in urls_to_delete
    ]
    success_del, errors_del = helpers.bulk(
        es, delete_actions, raise_on_error=False, stats_only=True
    )
    logger.info("deleted %d documents", success_del)
    if errors_del:
        logger.error("deletion errors: %s", errors_del)


def _generate_docs(
    all_entries: list[dict[str, pydantic.JsonValue]],
    index_name: str,
    stats: dict[str, int],
    config_name: str,
) -> collections.abc.Generator[dict[str, pydantic.JsonValue], None, None]:
    for entry in all_entries:
        base_dir_val = entry.pop("_base_dir", None)
        file_path_val = entry.get("file_path")
        if not base_dir_val or not file_path_val:
            continue
        file_path = Path(str(base_dir_val)) / str(file_path_val)

        if not file_path.exists():
            logger.warning("file not found, skipping: %s", file_path)
            stats["missing_files"] += 1
            continue

        doc_type = entry.get("type", "html")

        if doc_type == "document":
            title, content = _process_document(entry, file_path)
            if title is None:
                stats["parse_errors"] += 1
                continue
            stats["documents"] += 1
        else:
            html = file_path.read_bytes()
            title, content = extract_text_from_html(html)
            stats["html"] += 1

        entry["_content"] = f"{title} {content}"

        allowed_roles = entry.get("acl_allowed_roles", [])
        if not allowed_roles:
            allowed_roles = ["anonymous"]
            logger.warning(
                "no ACL configured for %s — defaulting to anonymous (public)",
                entry.get("url", "?"),
            )
        acl = {
            "allowed_roles": allowed_roles,
            "policy_version": "v1",
            "raw_claims": entry.get("acl_raw_claims", {}),
        }

        yield {
            "_index": index_name,
            "_id": entry["url"],
            "_source": {
                "url": entry["url"],
                "title": title,
                "content": content,
                "domain": entry["domain"],
                "path": entry["path"],
                "depth": entry["depth"],
                "crawled_at": entry["crawled_at"],
                "file_path": entry["file_path"],
                "language": entry.get("language", ""),
                "acl": acl,
                "source_name": config_name,
            },
        }


def _setup_elasticsearch_index(
    es: Elasticsearch,
    index_name: str,
    language: str,
    es_config: ESConfig,
    *,
    recreate: bool = False,
) -> None:
    index_settings = es_config.get_index_settings(language)

    if es.indices.exists(index=index_name):
        if recreate:
            logger.info("recreating index: %s", index_name)
            es.indices.delete(index=index_name)
            es.indices.create(index=index_name, body=index_settings)
        else:
            logger.info("index %s exists, skipping recreation", index_name)
    else:
        logger.info("creating index: %s (language: %s)", index_name, language)
        es.indices.create(index=index_name, body=index_settings)


def _perform_bulk_indexing(c: BulkIndexContext) -> tuple[int, int, bool]:
    success_count = 0
    error_count = 0
    pending_checkpoint_urls: list[str] = []
    threshold_fired = c.threshold_fired

    def _flush_checkpoints() -> None:
        if pending_checkpoint_urls and c.ctx.checkpoint_repo and c.ctx.config_name:
            asyncio.run(
                c.ctx.checkpoint_repo.record_indexed_batch(
                    c.ctx.config_name, pending_checkpoint_urls
                )
            )
            pending_checkpoint_urls.clear()

    for ok, result in helpers.streaming_bulk(
        c.es,
        _generate_docs(c.all_entries, c.index_name, c.ctx.stats, c.ctx.config_name),
        chunk_size=c.batch_size,
        raise_on_error=False,
    ):
        if ok:
            success_count += 1
            action_result: dict[str, pydantic.JsonValue] = next(
                iter(result.values()), {}
            )
            url = action_result.get("_id")
            if url and c.ctx.checkpoint_repo and c.ctx.config_name:
                pending_checkpoint_urls.append(str(url))
                if len(pending_checkpoint_urls) >= c.batch_size:
                    _flush_checkpoints()
            logger.info(
                "document_indexed url=%s count=%d total=%d",
                url,
                c.ctx.already_indexed + success_count,
                c.ctx.total_documents,
            )
            total_so_far = c.ctx.already_indexed + success_count
            if (
                c.threshold > 0
                and not threshold_fired
                and total_so_far >= c.threshold
                and c.backend_url is not None
            ):
                _fire_threshold_webhook(c.backend_url, total_so_far, c.ctx.config_name)
                threshold_fired = True
        else:
            error_count += 1
            logger.error("error indexing: %s", result)

        if (success_count + error_count) % 10 == 0:
            _publish_stats(
                c.ctx.stats_writer,
                phase="indexing",
                indexed=c.ctx.already_indexed + success_count,
                total=c.ctx.total_documents,
            )

    _flush_checkpoints()

    return success_count, error_count, threshold_fired


async def _embed_batch(c: EmbedBatchContext) -> bool:
    response = await c.litellm.aembedding(model=c.embedding_model, input=c.texts)
    vectors = [
        item["embedding"] if isinstance(item, dict) else item.embedding
        for item in response.data
    ]
    vector_size = len(vectors[0])
    exists = c.exists
    if not exists and c.batch_index == 0:
        await c.client.create_collection(
            collection_name=c.qdrant_collection,
            vectors_config=c.qdrant_client.models.VectorParams(
                size=vector_size,
                distance=c.qdrant_client.models.Distance.COSINE,
            ),
            metadata={"embedding_model": c.embedding_model},
        )
        exists = True
    points = [
        c.qdrant_client.models.PointStruct(
            id=_url_to_id(url),
            vector=vec,
            payload={"path": url},
        )
        for url, vec in zip(c.urls, vectors, strict=False)
    ]
    await c.client.upsert(collection_name=c.qdrant_collection, points=points)
    return exists


def _embed_and_upsert(ctx: EmbedContext) -> None:
    async def _run() -> None:
        client = qdrant_client.AsyncQdrantClient(url=ctx.qdrant_host)
        exists = await client.collection_exists(ctx.qdrant_collection)

        if exists:
            probe = await litellm.aembedding(model=ctx.embedding_model, input=["probe"])
            actual_dim = len(
                probe.data[0]["embedding"]
                if isinstance(probe.data[0], dict)
                else probe.data[0].embedding
            )
            info = await client.get_collection(ctx.qdrant_collection)
            vectors = info.config.params.vectors
            stored_dim = (
                vectors.size
                if isinstance(vectors, qdrant_client.models.VectorParams)
                else 0
            )
            stored_model = (info.config.metadata or {}).get("embedding_model")
            if stored_dim != actual_dim or (
                stored_model and stored_model != ctx.embedding_model
            ):
                reason = (
                    f"dim {stored_dim}→{actual_dim}"
                    if stored_dim != actual_dim
                    else f"model {stored_model!r}→{ctx.embedding_model!r}"
                )
                logger.warning(
                    "collection '%s' is stale (%s). recreating.",
                    ctx.qdrant_collection,
                    reason,
                )
                await client.delete_collection(ctx.qdrant_collection)
                exists = False

        docs = [
            (entry["url"], entry.get("_content", ""))
            for entry in ctx.all_entries
            if entry.get("url") and entry.get("_content")
        ]

        logger.info(
            "embedding %d documents in batches of %d", len(docs), ctx.batch_size
        )

        for i in range(0, len(docs), ctx.batch_size):
            batch = docs[i : i + ctx.batch_size]
            urls = [str(u) for u, _ in batch]
            texts = [str(t) for _, t in batch]

            try:
                exists = await _embed_batch(
                    EmbedBatchContext(
                        client=client,
                        litellm=litellm,
                        qdrant_client=qdrant_client,
                        urls=urls,
                        texts=texts,
                        embedding_model=ctx.embedding_model,
                        qdrant_collection=ctx.qdrant_collection,
                        exists=exists,
                        batch_index=i,
                    )
                )
            except Exception:
                logger.exception("embedding batch %d failed", i // ctx.batch_size)

            embedded_so_far = min(i + ctx.batch_size, len(docs))
            _publish_stats(
                ctx.stats_writer,
                phase="embedding",
                indexed=embedded_so_far,
                total=len(docs),
            )
            if (i // ctx.batch_size) % 5 == 0:
                logger.info("embedded %d/%d documents", embedded_so_far, len(docs))

        await client.close()
        logger.info("embedding complete")

    asyncio.run(_run())


def _detect_languages_if_missing(
    all_entries: list[dict[str, pydantic.JsonValue]],
    stats_writer: StatsWriter | None = None,
    total_documents: int = 0,
) -> None:
    missing_count = sum(1 for e in all_entries if not e.get("language"))
    if missing_count == 0:
        return

    logger.info("detecting language for %d documents...", missing_count)

    detected = 0
    for entry in all_entries:
        if entry.get("language"):
            continue

        base_dir_val = entry.get("_base_dir")
        if not base_dir_val:
            continue

        file_path_val = entry.get("file_path")
        if not file_path_val:
            continue

        file_path = Path(str(base_dir_val)) / str(file_path_val)

        if not file_path.exists():
            continue

        doc_type = entry.get("type", "html")
        content = None

        if doc_type == "document":
            _, content = _process_document(entry, file_path)
        else:
            try:
                html = file_path.read_bytes()
                _, content = extract_text_from_html(html)
            except Exception:
                pass

        if content:
            lang = language_detector.detect_language(content)
            if lang:
                entry["language"] = lang

        detected += 1
        if detected % 10 == 0:
            _publish_stats(
                stats_writer,
                phase="language_detection",
                indexed=detected,
                total=total_documents,
            )


async def _get_db_config(key: str) -> str | None:
    try:
        pool = await get_async_pool()
        repo = ServiceConfigRepo(pool)
        config = await repo.get(key)
        if config and config.get("is_configured"):
            return config["value"]
    except Exception:
        pass
    return None


def _read_index_threshold() -> int:
    try:
        value = asyncio.run(_get_db_config("index_threshold_count"))
        if value:
            return int(value)
    except Exception:
        pass
    return 0


def _fire_threshold_webhook(
    backend_url: str, total_indexed: int, config_name: str
) -> None:
    token = os.environ.get("HARMONY_INTERNAL_TOKEN", "")
    headers = {"X-Internal-Token": token} if token else {}
    try:
        httpx.post(
            f"{backend_url}/api/internal/webhook/fire",
            json={
                "event": "index_threshold",
                "payload": {
                    "documents_indexed": total_indexed,
                    "config_name": config_name,
                },
            },
            headers=headers,
            timeout=5.0,
        )
    except Exception as exc:
        logger.warning("failed to fire index_threshold webhook: %s", exc)


def resolve_es_host(config: IndexerConfig) -> str:
    if config.es_host:
        return config.es_host

    env_host = os.environ.get("ES_HOST")
    if env_host:
        return env_host

    try:
        db_host = asyncio.run(_get_db_config("elasticsearch_url"))
        if db_host:
            logger.info("using ES config from database: %s", db_host)
            return db_host
    except Exception as e:
        logger.warning("DB config check failed: %s", e)

    default_host = "http://elasticsearch:9200"
    logger.warning("using default ES host: %s", default_host)
    return default_host


def resolve_index_base_name(config: IndexerConfig) -> str:
    if config.index_base_name != "harmony":
        return config.index_base_name

    env_name = os.environ.get("ES_INDEX_BASE_NAME")
    if env_name:
        return env_name

    try:
        db_name = asyncio.run(_get_db_config("es_index_base_name"))
        if db_name:
            logger.info("using index base name from database: %s", db_name)
            return db_name
    except Exception as e:
        logger.warning("DB config check failed: %s", e)

    return "harmony"


def resolve_languages(config: IndexerConfig) -> list[str]:
    if config.languages:
        return config.languages

    env_langs = os.environ.get("ES_LANGUAGES")
    if env_langs:
        return [lang.strip() for lang in env_langs.split(",") if lang.strip()]

    try:
        db_langs = asyncio.run(_get_db_config("es_languages"))
        if db_langs:
            langs = [lang.strip() for lang in db_langs.split(",") if lang.strip()]
            logger.info("using languages from database: %s", langs)
            return langs
    except Exception as e:
        logger.warning("DB config check failed: %s", e)

    return ["en", "fr"]


def _resolve_configs(config: IndexerConfig) -> tuple[str, str, list[str]]:
    final_es_host = resolve_es_host(config)
    final_index_base_name = resolve_index_base_name(config)
    final_languages = resolve_languages(config)
    return final_es_host, final_index_base_name, final_languages


def _build_es_config(
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


def _connect_elasticsearch(es_config: ESConfig) -> Elasticsearch | None:
    logger.info("connecting to Elasticsearch at %s", es_config.host)
    es = Elasticsearch([es_config.host])
    if not es.ping():
        logger.error("cannot connect to Elasticsearch")
        return None
    return es


def _load_entries_from_source(
    config: IndexerConfig,
    es_host: str,
    index_base_name: str,
    languages: list[str],
    state_index: str,
) -> tuple[list[dict[str, pydantic.JsonValue]], Elasticsearch, ESConfig] | None:
    if config.source != "elasticsearch" and (
        config.data_dir is None or not config.data_dir.exists()
    ):
        logger.error("data directory %s does not exist", config.data_dir)
        return None
    logger.info("loading from ES state index: %s", state_index)
    es_config = _build_es_config(config, es_host, index_base_name, languages)
    es = _connect_elasticsearch(es_config)
    if es is None:
        return None
    data_dir = config.data_dir or Path(".")
    all_entries = _load_entries_from_es(es, state_index, data_dir)
    if not all_entries:
        logger.warning("no documents found in state index")
        return None
    return all_entries, es, es_config


def _index_by_language(
    ctx_lang: IndexByLanguageContext,
) -> tuple[int, int, dict[str, int]]:
    entries_by_lang = _group_entries_by_language(ctx_lang.all_entries)
    logger.info(
        "found %d language(s): %s",
        len(entries_by_lang),
        ", ".join(entries_by_lang.keys()),
    )

    threshold = _read_index_threshold()
    backend_url = os.environ.get("HARMONY_BACKEND_URL")
    threshold_fired = False

    total_success = 0
    total_errors = 0
    total_stats: dict[str, int] = {
        "html": 0,
        "documents": 0,
        "parse_errors": 0,
        "missing_files": 0,
    }

    for lang, entries in entries_by_lang.items():
        logger.info("processing language: %s (%d documents)", lang, len(entries))
        index_name = ctx_lang.es_config.get_index_name(lang)
        _setup_elasticsearch_index(
            ctx_lang.es,
            index_name,
            lang,
            ctx_lang.es_config,
            recreate=ctx_lang.recreate,
        )

        lang_stats: dict[str, int] = {
            "html": 0,
            "documents": 0,
            "parse_errors": 0,
            "missing_files": 0,
        }
        ctx = IndexingContext(
            stats_writer=ctx_lang.stats_writer,
            already_indexed=total_success,
            total_documents=len(entries),
            stats=lang_stats,
            checkpoint_repo=ctx_lang.checkpoint_repo,
            config_name=ctx_lang.config_name,
        )
        success_count, error_count, threshold_fired = _perform_bulk_indexing(
            BulkIndexContext(
                es=ctx_lang.es,
                all_entries=entries,
                index_name=index_name,
                batch_size=ctx_lang.config.batch_size,
                ctx=ctx,
                threshold=threshold,
                backend_url=backend_url,
                threshold_fired=threshold_fired,
            )
        )
        total_success += success_count
        total_errors += error_count
        for key in total_stats:
            total_stats[key] += lang_stats[key]
        logger.info("%s: %d indexed, %d errors", lang, success_count, error_count)

    return total_success, total_errors, total_stats


def main() -> None:
    parser = ArgumentParser(
        prog="harmony-index",
        description="Index crawled data to Elasticsearch",
        default_config_files=["indexer_config.yaml"],
    )
    parser.add_argument(
        "--config", action=ActionConfigFile, help="Path to YAML configuration file"
    )

    parser.add_argument(
        "--sync-deletions",
        action="store_true",
        help="Sync deletions from crawl state to content index",
    )
    parser.add_argument(
        "--start-fresh",
        action="store_true",
        help="Clear existing checkpoint before indexing (re-index all documents)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate ES indices before indexing (default: incremental upsert)",
    )

    parser.add_class_arguments(IndexerConfig, None, skip={"sync_deletions"})
    parser.add_argument(
        "--state_index",
        type=str,
        default=None,
        help="ES state index name (overrides ES_STATE_INDEX env var)",
    )
    parser.add_argument(
        "-v",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv, -vvv)",
    )

    args = parser.parse_args()

    config_data = {}
    for field_name in IndexerConfig.model_fields:
        if hasattr(args, field_name):
            config_data[field_name] = getattr(args, field_name)

    config = IndexerConfig(**config_data)

    if args.v > 0:
        config.verbose = args.v

    log_level = logging.DEBUG if config.verbose > 0 else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    final_es_host, final_index_base_name, final_languages = _resolve_configs(config)
    stats_writer = _make_stats_writer()
    state_index = args.state_index or os.environ.get(
        "ES_STATE_INDEX", "harmony-crawl-state"
    )

    config_name = getattr(args, "config_name", None) or os.environ.get(
        "HARMONY_CRAWL_JOB_ID", final_index_base_name
    )

    pool = asyncio.run(get_async_pool()) if os.environ.get("DATABASE_URL") else None
    checkpoint_repo = IndexerCheckpointRepo(pool) if pool is not None else None

    try:
        _run_indexing(
            RunIndexingContext(
                args=args,
                config=config,
                checkpoint_repo=checkpoint_repo,
                config_name=config_name,
                final_es_host=final_es_host,
                final_index_base_name=final_index_base_name,
                final_languages=final_languages,
                state_index=state_index,
                stats_writer=stats_writer,
            )
        )
    finally:
        if pool is not None:
            asyncio.run(close_async_pool())


def _run_indexing(ctx: RunIndexingContext) -> None:
    if ctx.args.start_fresh and ctx.checkpoint_repo is not None:
        cleared = asyncio.run(ctx.checkpoint_repo.clear(ctx.config_name))
        logger.info(
            "cleared %d checkpoint entries for config '%s'", cleared, ctx.config_name
        )

    indexed_urls = (
        asyncio.run(ctx.checkpoint_repo.get_indexed_urls(ctx.config_name))
        if ctx.checkpoint_repo is not None
        else set()
    )
    logger.info("found %d already-indexed URLs in checkpoint", len(indexed_urls))

    result = _load_entries_from_source(
        ctx.config,
        ctx.final_es_host,
        ctx.final_index_base_name,
        ctx.final_languages,
        ctx.state_index,
    )
    if result is None:
        sys.exit(1)
    all_entries, es, es_config = result

    if indexed_urls:
        original_count = len(all_entries)
        all_entries = [e for e in all_entries if e.get("url") not in indexed_urls]
        skipped = original_count - len(all_entries)
        if skipped:
            logger.info("skipping %d already-indexed URLs", skipped)

    logger.info("processing %d documents", len(all_entries))
    _detect_languages_if_missing(all_entries, ctx.stats_writer, len(all_entries))

    total_success, total_errors, total_stats = _index_by_language(
        IndexByLanguageContext(
            all_entries=all_entries,
            es=es,
            es_config=es_config,
            config=ctx.config,
            stats_writer=ctx.stats_writer,
            checkpoint_repo=ctx.checkpoint_repo,
            config_name=ctx.config_name,
            recreate=ctx.args.recreate,
        )
    )

    logger.info(
        "indexing complete: %d success, %d errors; html=%d documents=%d parse_errors=%d missing_files=%d",
        total_success,
        total_errors,
        total_stats["html"],
        total_stats["documents"],
        total_stats["parse_errors"],
        total_stats["missing_files"],
    )

    if not ctx.config.skip_embedding:
        _embed_and_upsert(
            EmbedContext(
                all_entries=all_entries,
                qdrant_host=ctx.config.qdrant_host,
                qdrant_collection=ctx.config.qdrant_collection,
                embedding_model=ctx.config.embedding_model,
                batch_size=ctx.config.embedding_batch_size,
                stats_writer=ctx.stats_writer,
            )
        )

    if ctx.config.sync_deletions:
        entries_by_lang = _group_entries_by_language(all_entries)
        for lang in entries_by_lang:
            index_name = es_config.get_index_name(lang)
            _sync_deletions(
                es, ctx.state_index, index_name, ctx.config.missing_threshold
            )


if __name__ == "__main__":
    main()
