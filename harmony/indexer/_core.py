from __future__ import annotations

import dataclasses
import logging
import os
import typing
from datetime import UTC, datetime
from pathlib import Path

import bs4
import httpx
import litellm
import pydantic
from elasticsearch.helpers import async_bulk, async_streaming_bulk

from harmony.clients import ElasticsearchService, QdrantService
from harmony.core import (
    BackendStatsWriter,
    CorruptDocumentError,
    StatsWriter,
    default_registry,
)
from harmony.core._elasticsearch_config import ESConfig
from harmony.db.repositories import IndexerCheckpointRepo

from ._config import IndexerConfigCLI as IndexerConfig
from ._sources import group_entries_by_language

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class IndexingContext:
    stats_writer: StatsWriter | None
    already_indexed: int
    total_documents: int
    stats: dict[str, int]
    checkpoint_repo: IndexerCheckpointRepo | None = None
    config_name: str = ""


@dataclasses.dataclass
class BulkIndexContext:
    es_service: ElasticsearchService
    all_entries: list[dict[str, pydantic.JsonValue]]
    index_name: str
    batch_size: int
    ctx: IndexingContext
    threshold: int = 0
    backend_url: str | None = None
    threshold_fired: bool = False


@dataclasses.dataclass
class EmbedBatchContext:
    client: QdrantService
    urls: list[str]
    texts: list[str]
    embedding_model: str
    exists: bool
    batch_index: int


@dataclasses.dataclass
class EmbedContext:
    all_entries: list[dict[str, pydantic.JsonValue]]
    qdrant_service: QdrantService
    embedding_model: str
    batch_size: int
    stats_writer: StatsWriter | None = None


@dataclasses.dataclass
class IndexByLanguageContext:
    all_entries: list[dict[str, pydantic.JsonValue]]
    es_service: ElasticsearchService
    es_config: ESConfig
    config: IndexerConfig
    stats_writer: StatsWriter | None
    checkpoint_repo: IndexerCheckpointRepo | None = None
    config_name: str = ""
    recreate: bool = False


@dataclasses.dataclass
class RunIndexingContext:
    config: IndexerConfig
    checkpoint_repo: IndexerCheckpointRepo | None
    config_name: str
    final_es_host: str
    final_index_base_name: str
    final_languages: list[str]
    state_index: str
    stats_writer: StatsWriter | None
    start_fresh: bool = False
    recreate: bool = False


def make_stats_writer() -> StatsWriter | None:
    job_id = os.environ.get("HARMONY_CRAWL_JOB_ID")
    backend_url = os.environ.get("HARMONY_BACKEND_URL")
    if job_id and backend_url:
        return BackendStatsWriter(backend_url, job_id)
    return None


def publish_stats(
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


def process_document(
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


async def sync_deletions(
    es_service: ElasticsearchService,
    state_index: str,
    content_index: str,
    missing_threshold: int,
) -> None:
    logger.info("syncing deletions from crawl state...")

    if not await es_service.index_exists(state_index):
        logger.error("state index %s does not exist", state_index)
        return

    try:
        await sync_deletions_inner(
            es_service, state_index, content_index, missing_threshold
        )
    except Exception:
        logger.exception("error during deletion sync")


async def sync_deletions_inner(
    es_service: ElasticsearchService,
    state_index: str,
    content_index: str,
    missing_threshold: int,
) -> None:
    query = {"query": {"range": {"missing_count": {"gte": missing_threshold}}}}
    response = await es_service.client.search(
        index=state_index, body=query, size=10000, source=False
    )
    urls_to_delete = [hit["_id"] for hit in response["hits"]["hits"]]

    if not urls_to_delete:
        logger.info("no URLs to delete")
        return

    logger.info("deleting %d URLs...", len(urls_to_delete))
    delete_actions = [
        {"_op_type": "delete", "_index": content_index, "_id": url}
        for url in urls_to_delete
    ]
    success_del, errors_del = await async_bulk(
        es_service.client, delete_actions, raise_on_error=False, stats_only=True
    )
    logger.info("deleted %d documents", success_del)
    if errors_del:
        logger.error("deletion errors")


async def generate_docs(  # noqa: RUF029
    all_entries: list[dict[str, pydantic.JsonValue]],
    index_name: str,
    stats: dict[str, int],
    config_name: str,
) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
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
            title, content = process_document(entry, file_path)
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


async def setup_elasticsearch_index(
    es_service: ElasticsearchService,
    index_name: str,
    language: str,
    es_config: ESConfig,
    *,
    recreate: bool = False,
) -> None:
    index_settings = es_config.get_index_settings(language)

    if await es_service.index_exists(index_name):
        if recreate:
            logger.info("recreating index: %s", index_name)
            await es_service.delete_index(index_name)
            await es_service.client.indices.create(
                index=index_name, body=index_settings
            )
        else:
            logger.info("index %s exists, skipping recreation", index_name)
    else:
        logger.info("creating index: %s (language: %s)", index_name, language)
        await es_service.client.indices.create(index=index_name, body=index_settings)


async def perform_bulk_indexing(c: BulkIndexContext) -> tuple[int, int, bool]:
    success_count = 0
    error_count = 0
    pending_checkpoint_urls: list[str] = []
    threshold_fired = c.threshold_fired

    async def _flush_checkpoints() -> None:
        if pending_checkpoint_urls and c.ctx.checkpoint_repo and c.ctx.config_name:
            await c.ctx.checkpoint_repo.record_indexed_batch(
                c.ctx.config_name, pending_checkpoint_urls
            )
            pending_checkpoint_urls.clear()

    async for ok, result in async_streaming_bulk(
        c.es_service.client,
        generate_docs(c.all_entries, c.index_name, c.ctx.stats, c.ctx.config_name),
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
                    await _flush_checkpoints()
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
                fire_threshold_webhook(c.backend_url, total_so_far, c.ctx.config_name)
                threshold_fired = True
        else:
            error_count += 1
            logger.error("error indexing: %s", result)

        if (success_count + error_count) % 10 == 0:
            publish_stats(
                c.ctx.stats_writer,
                phase="indexing",
                indexed=c.ctx.already_indexed + success_count,
                total=c.ctx.total_documents,
            )

    await _flush_checkpoints()

    return success_count, error_count, threshold_fired


async def embed_batch(c: EmbedBatchContext) -> bool:
    response = await litellm.aembedding(model=c.embedding_model, input=c.texts)
    vectors = [
        item["embedding"] if isinstance(item, dict) else item.embedding
        for item in response.data
    ]
    exists = c.exists
    if not exists and c.batch_index == 0:
        await c.client.ensure_collection()
        exists = True
    points = [(str(url), vec) for url, vec in zip(c.urls, vectors, strict=False)]
    await c.client.upsert(vectors=points)
    return exists


async def embed_and_upsert(ctx: EmbedContext) -> None:
    client = ctx.qdrant_service
    exists = await client.collection_exists()

    if exists:
        probe = await litellm.aembedding(model=ctx.embedding_model, input=["probe"])
        actual_dim = len(
            probe.data[0]["embedding"]
            if isinstance(probe.data[0], dict)
            else probe.data[0].embedding
        )
        stored_dim, stored_model = await client.get_collection_info()

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
                client.collection,
                reason,
            )
            await client.client.delete_collection(client.collection)
            exists = False

    docs = [
        (entry["url"], entry.get("_content", ""))
        for entry in ctx.all_entries
        if entry.get("url") and entry.get("_content")
    ]

    logger.info("embedding %d documents in batches of %d", len(docs), ctx.batch_size)

    for i in range(0, len(docs), ctx.batch_size):
        batch = docs[i : i + ctx.batch_size]
        urls = [str(u) for u, _ in batch]
        texts = [str(t) for _, t in batch]

        try:
            exists = await embed_batch(
                EmbedBatchContext(
                    client=client,
                    urls=urls,
                    texts=texts,
                    embedding_model=ctx.embedding_model,
                    exists=exists,
                    batch_index=i,
                )
            )
        except Exception:
            logger.exception("embedding batch %d failed", i // ctx.batch_size)

        embedded_so_far = min(i + ctx.batch_size, len(docs))
        publish_stats(
            ctx.stats_writer,
            phase="embedding",
            indexed=embedded_so_far,
            total=len(docs),
        )
        if (i // ctx.batch_size) % 5 == 0:
            logger.info("embedded %d/%d documents", embedded_so_far, len(docs))

    await client.close()
    logger.info("embedding complete")


async def read_index_threshold(pool: typing.Any) -> int:
    from ._sources import get_db_config  # noqa: PLC0415

    try:
        value = await get_db_config(pool, "index_threshold_count")
        if value:
            return int(value)
    except Exception:
        logger.exception("failed to read index_threshold_count")
    return 0


def fire_threshold_webhook(
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


async def index_by_language(
    ctx_lang: IndexByLanguageContext, pool: typing.Any = None
) -> tuple[int, int, dict[str, int]]:
    entries_by_lang = group_entries_by_language(ctx_lang.all_entries)
    logger.info(
        "found %d language(s): %s",
        len(entries_by_lang),
        ", ".join(entries_by_lang.keys()),
    )

    threshold = await read_index_threshold(pool) if pool else 0
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
        await setup_elasticsearch_index(
            ctx_lang.es_service,
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
        success_count, error_count, threshold_fired = await perform_bulk_indexing(
            BulkIndexContext(
                es_service=ctx_lang.es_service,
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
