from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import logging
import os
import typing
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import UUID

import pydantic
import qdrant_client
from cryptography.fernet import Fernet
from elasticsearch import AsyncElasticsearch, helpers
from jsonargparse import ArgumentParser

from harmony.core import CorruptDocumentError, default_registry
from harmony.core import url_to_id as _url_to_id
from harmony.core.ocr import IMAGE_EXTENSIONS, ocr_dispatch
from harmony.db.connection import get_async_pool
from harmony.db.repositories import DataSourcesRepo, FilesystemStateRepo
from harmony.indexer import EmbedContext, embed_and_upsert
from harmony.services import SecretValueService
from harmony.services.admin import AuditLogService, ModelRegistryService

from .._filesystem import FilesystemProviderConfig

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 65536


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_uri(root: Path, abs_path: Path) -> str:
    return Path(abs_path).resolve().as_uri()


def _iter_candidate_files(
    root: Path, include_patterns: list[str], exclude_patterns: list[str]
) -> typing.Iterator[Path]:
    seen: set[Path] = set()
    for pattern in include_patterns:
        for candidate in root.glob(pattern):
            if not candidate.is_file():
                continue
            if candidate in seen:
                continue
            rel = PurePosixPath(candidate.relative_to(root).as_posix())
            if any(rel.full_match(excl) for excl in exclude_patterns):
                continue
            seen.add(candidate)
            yield candidate


async def _process_document(
    file_path: Path, model_registry_service: ModelRegistryService
) -> tuple[str | None, str | None]:
    extension = file_path.suffix.lower()

    if extension in IMAGE_EXTENSIONS:
        try:
            content = await ocr_dispatch(file_path, model_registry_service)
        except Exception:
            logger.exception("ocr error %s", file_path.name)
            return None, None
        return file_path.name, content

    parser = default_registry.get_parser("", extension)
    if not parser:
        logger.warning("no parser for extension %s: %s", extension, file_path.name)
        return None, None

    try:
        title, content = parser.parse(file_path)
    except CorruptDocumentError:
        logger.exception("parse error %s", file_path.name)
        return None, None

    if extension == ".pdf" and not content.strip():
        try:
            content = await ocr_dispatch(file_path, model_registry_service)
        except Exception:
            logger.exception("ocr error %s", file_path.name)
            return None, None

    return title, content


def _build_entry(
    *,
    root: Path,
    file_path: Path,
    title: str,
    content: str,
    source_name: str,
) -> dict[str, pydantic.JsonValue]:
    return {
        "url": file_uri(root, file_path),
        "title": title,
        "content": content,
        "source_name": source_name,
        "file_path": str(file_path.relative_to(root)),
        "file_type": file_path.suffix.lstrip("."),
        "indexed_at": datetime.now(UTC).isoformat(),
        "size_bytes": file_path.stat().st_size,
        "language": "",
    }


def _entry_to_es_source(
    entry: dict[str, pydantic.JsonValue],
) -> dict[str, pydantic.JsonValue]:
    return {
        "url": entry["url"],
        "title": entry["title"],
        "content": entry["content"],
        "source_name": entry["source_name"],
        "file_path": entry["file_path"],
        "file_type": entry["file_type"],
        "indexed_at": entry["indexed_at"],
        "size_bytes": entry["size_bytes"],
        "language": entry.get("language", ""),
        "acl": {
            "allowed_roles": ["anonymous"],
            "policy_version": "v1",
            "raw_claims": {},
        },
    }


async def _do_bulk_index(
    es: AsyncElasticsearch,
    entries: list[dict[str, pydantic.JsonValue]],
    index_name: str,
) -> None:
    if not await es.indices.exists(index=index_name):
        await es.indices.create(index=index_name)

    actions = (
        {
            "_index": index_name,
            "_id": entry["url"],
            "_source": _entry_to_es_source(entry),
        }
        for entry in entries
    )
    success, errors = await helpers.async_bulk(
        es, actions, raise_on_error=False, stats_only=True
    )
    logger.info("filesystem ingest: indexed %d documents", success)
    if errors:
        logger.error("filesystem ingest: %d indexing errors", errors)


async def _bulk_index_entries_async(
    entries: list[dict[str, pydantic.JsonValue]], es_host: str, index_name: str
) -> None:
    es = AsyncElasticsearch([es_host])
    try:
        await _do_bulk_index(es, entries, index_name)
    finally:
        await es.close()


def _bulk_index_entries(
    entries: list[dict[str, pydantic.JsonValue]], es_host: str, index_name: str
) -> None:
    if not entries:
        return
    asyncio.run(_bulk_index_entries_async(entries, es_host, index_name))


async def _embed_and_upsert_entries(
    all_entries: list[dict[str, pydantic.JsonValue]],
    qdrant_host: str,
    qdrant_collection: str,
    embedding_model: str,
    batch_size: int,
) -> None:
    from harmony.clients import QdrantService  # noqa: PLC0415

    embed_entries = [
        {"url": entry["url"], "_content": f"{entry['title']} {entry['content']}"}
        for entry in all_entries
    ]
    qdrant_service = QdrantService(
        host=qdrant_host, collection=qdrant_collection, vector_size=512
    )
    await embed_and_upsert(
        EmbedContext(
            all_entries=embed_entries,
            qdrant_service=qdrant_service,
            embedding_model=embedding_model,
            batch_size=batch_size,
        )
    )


@dataclasses.dataclass
class SyncDeletionsContext:
    fs_repo: FilesystemStateRepo
    data_source_id: str
    stale_uris: list[str]
    es_host: str
    index_name: str
    qdrant_host: str
    qdrant_collection: str
    skip_embedding: bool


async def _sync_deletions(ctx: SyncDeletionsContext) -> None:
    if not ctx.stale_uris:
        return

    logger.warning("filesystem ingest: %d stale file(s) detected", len(ctx.stale_uris))

    try:
        await _delete_stale_es_docs(ctx.stale_uris, ctx.es_host, ctx.index_name)
    except Exception:
        logger.exception("filesystem ingest: failed to delete stale ES docs")

    if ctx.qdrant_host and not ctx.skip_embedding:
        try:
            await _delete_stale_qdrant_points(
                ctx.stale_uris, ctx.qdrant_host, ctx.qdrant_collection
            )
        except Exception:
            logger.exception("filesystem ingest: failed to delete stale Qdrant points")

    try:
        await ctx.fs_repo.delete_uris(ctx.data_source_id, ctx.stale_uris)
    except Exception:
        logger.exception(
            "filesystem ingest: failed to delete stale filesystem_state rows"
        )


async def _delete_stale_es_docs(
    stale_uris: list[str], es_host: str, index_name: str
) -> None:
    es = AsyncElasticsearch([es_host])
    try:
        delete_actions = [
            {"_op_type": "delete", "_index": index_name, "_id": uri}
            for uri in stale_uris
        ]
        success, errors = await helpers.async_bulk(
            es, delete_actions, raise_on_error=False, stats_only=True
        )
        logger.info("filesystem ingest: deleted %d stale ES documents", success)
        if errors:
            logger.error("filesystem ingest: %d deletion errors", errors)
    finally:
        await es.close()


async def _delete_stale_qdrant_points(
    stale_uris: list[str], qdrant_host: str, qdrant_collection: str
) -> None:
    client = qdrant_client.AsyncQdrantClient(url=qdrant_host)
    try:
        point_ids: list[int | str | UUID] = [_url_to_id(uri) for uri in stale_uris]
        await client.delete(
            collection_name=qdrant_collection,
            points_selector=point_ids,
        )
    finally:
        await client.close()


@dataclasses.dataclass
class IndexCandidateContext:
    candidate: Path
    root: Path
    data_source_id: str
    source_name: str
    fs_repo: FilesystemStateRepo
    model_registry_service: ModelRegistryService


async def _index_candidate(
    ctx: IndexCandidateContext,
) -> dict[str, pydantic.JsonValue] | None:
    current_hash = file_sha256(ctx.candidate)
    uri = file_uri(ctx.root, ctx.candidate)
    stored_hash = await ctx.fs_repo.get_hash(ctx.data_source_id, uri)
    if stored_hash == current_hash:
        return None

    title, content = await _process_document(ctx.candidate, ctx.model_registry_service)
    if title is None or content is None:
        return None

    entry = _build_entry(
        root=ctx.root,
        file_path=ctx.candidate,
        title=title,
        content=content,
        source_name=ctx.source_name,
    )
    await ctx.fs_repo.upsert(
        ctx.data_source_id, uri, current_hash, ctx.candidate.stat().st_size
    )
    return entry


@dataclasses.dataclass
class IngestConfig:
    data_source_id: str
    es_host: str
    index_base_name: str
    qdrant_host: str
    qdrant_collection: str
    embedding_model: str
    embedding_batch_size: int
    skip_embedding: bool
    ds_repo: DataSourcesRepo | None = None
    fs_repo: FilesystemStateRepo | None = None
    model_registry_service: ModelRegistryService | None = None


async def _initialize_repos(
    config: IngestConfig,
) -> tuple[DataSourcesRepo, FilesystemStateRepo, ModelRegistryService]:
    ds_repo = config.ds_repo
    fs_repo = config.fs_repo
    model_registry_service = config.model_registry_service
    if ds_repo is None or fs_repo is None or model_registry_service is None:
        pool = await get_async_pool()
        ds_repo = ds_repo or DataSourcesRepo(pool)
        fs_repo = fs_repo or FilesystemStateRepo(pool)
        if model_registry_service is None:
            secret_key = os.environ.get("HARMONY_SECRET_KEY", "").strip().encode()
            secret_service = SecretValueService(secret_key or Fernet.generate_key())
            audit_log_service = AuditLogService()
            await audit_log_service.initialize(pool)
            model_registry_service = ModelRegistryService()
            await model_registry_service.initialize(
                pool, audit_log_service, secret_service
            )
    return ds_repo, fs_repo, model_registry_service


async def _ingest(config: IngestConfig) -> None:
    ds_repo, fs_repo, model_registry_service = await _initialize_repos(config)

    data_source = await ds_repo.get(config.data_source_id)
    if data_source is None:
        msg = f"data source {config.data_source_id!r} not found"
        raise ValueError(msg)

    prov_config = FilesystemProviderConfig.model_validate(data_source.config)
    root = Path(prov_config.root_path).resolve()
    candidates = list(
        _iter_candidate_files(
            root, prov_config.include_patterns, prov_config.exclude_patterns
        )
    )

    indexed_entries = []
    for candidate in candidates:
        entry = await _index_candidate(
            IndexCandidateContext(
                candidate=candidate,
                root=root,
                data_source_id=config.data_source_id,
                source_name=data_source.name,
                fs_repo=fs_repo,
                model_registry_service=model_registry_service,
            )
        )
        if entry is not None:
            indexed_entries.append(entry)

    index_name = f"{config.index_base_name}-en"
    _bulk_index_entries(indexed_entries, config.es_host, index_name)

    if indexed_entries and not config.skip_embedding:
        await _embed_and_upsert_entries(
            indexed_entries,
            config.qdrant_host,
            config.qdrant_collection,
            config.embedding_model,
            config.embedding_batch_size,
        )

    known_uris = await fs_repo.list_uris(config.data_source_id)
    current_uris = {file_uri(root, candidate) for candidate in candidates}
    stale_uris = [uri for uri in known_uris if uri not in current_uris]
    await _sync_deletions(
        SyncDeletionsContext(
            fs_repo=fs_repo,
            data_source_id=config.data_source_id,
            stale_uris=stale_uris,
            es_host=config.es_host,
            index_name=index_name,
            qdrant_host=config.qdrant_host,
            qdrant_collection=config.qdrant_collection,
            skip_embedding=config.skip_embedding,
        )
    )

    await ds_repo.update_last_run(
        config.data_source_id, status="completed", doc_count=len(indexed_entries)
    )


def main() -> None:
    parser = ArgumentParser(prog="harmony-ingest-fs")
    parser.add_argument("--data-source-id", required=True)
    parser.add_argument("--es-host", default="http://localhost:9200")
    parser.add_argument("--index-base-name", default="harmony")
    parser.add_argument("--qdrant-host", default="http://localhost:6333")
    parser.add_argument("--qdrant-collection", default="harmony")
    parser.add_argument(
        "--embedding-model",
        default=os.environ.get("EMBEDDING_MODEL", "ollama/qwen3-embedding:0.6b"),
    )
    parser.add_argument("--embedding-batch-size", type=int, default=64)
    parser.add_argument("--skip-embedding", action="store_true", default=False)

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    asyncio.run(
        _ingest(
            IngestConfig(
                data_source_id=args.data_source_id,
                es_host=args.es_host,
                index_base_name=args.index_base_name,
                qdrant_host=args.qdrant_host,
                qdrant_collection=args.qdrant_collection,
                embedding_model=args.embedding_model,
                embedding_batch_size=args.embedding_batch_size,
                skip_embedding=args.skip_embedding,
            )
        )
    )


if __name__ == "__main__":
    main()
