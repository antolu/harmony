from __future__ import annotations

import contextlib
import io
import json
import os
import tarfile
import tempfile
import typing

import pydantic
import qdrant_client.models
import structlog

from harmony.api.services._elasticsearch import ElasticsearchService
from harmony.api.services._qdrant import QdrantService
from harmony.api.services.admin._audit_log import AuditLogService

logger = structlog.get_logger(__name__)

_STATE_INDEX = "harmony-crawl-state"
_SCROLL_SIZE = 500
_CHUNK_SIZE = 65536


def _safe_tar_member(name: str) -> bool:
    normalized = os.path.normpath(name)
    return not (normalized.startswith(("/", "..")) or "\\.." in normalized)


def _read_file_chunks(path: str) -> typing.Generator[bytes, None, None]:
    with open(path, "rb") as f:
        while True:
            chunk = f.read(_CHUNK_SIZE)
            if not chunk:
                break
            yield chunk


class ExportService:
    def __init__(
        self,
        es_service: ElasticsearchService,
        qdrant_service: QdrantService | None,
        audit_log_service: AuditLogService,
    ) -> None:
        self._es = es_service
        self._qdrant = qdrant_service
        self._audit_log = audit_log_service

    async def get_domains(self) -> list[dict[str, pydantic.JsonValue]]:
        es = self._es.client
        response = await es.search(
            index=_STATE_INDEX,
            size=0,
            aggregations={"domains": {"terms": {"field": "domain", "size": 1000}}},
            ignore_unavailable=True,
        )
        buckets = response.get("aggregations", {}).get("domains", {}).get("buckets", [])
        return sorted(
            [{"domain": b["key"], "doc_count": b["doc_count"]} for b in buckets],
            key=lambda x: x["domain"],
        )

    async def export_archive(
        self, domains: list[str]
    ) -> typing.AsyncGenerator[bytes, None]:
        fd, tmp_path = tempfile.mkstemp(suffix=".tar.gz")
        os.close(fd)

        await self._write_archive_async(domains, tmp_path)

        return self._stream_file(tmp_path)

    async def _stream_file(self, path: str) -> typing.AsyncGenerator[bytes, None]:
        try:
            for chunk in _read_file_chunks(path):
                yield chunk
        finally:
            with contextlib.suppress(OSError):
                os.unlink(path)

    async def _write_archive_async(self, domains: list[str], tmp_path: str) -> None:
        es = self._es.client

        with tarfile.open(tmp_path, "w:gz") as tar:
            for domain in domains:
                crawl_lines = await self._scroll_es_index(
                    _STATE_INDEX, {"term": {"domain": domain}}
                )
                self._add_bytes_to_tar(tar, crawl_lines, f"{domain}/crawl_state.jsonl")

                lang_indices = await es.cat.indices(
                    index="harmony-*",
                    format="json",
                )
                for idx_info in lang_indices or []:
                    index_name = idx_info.get("index", "")  # type: ignore
                    if not index_name.startswith("harmony-") or index_name in {
                        "harmony-crawl-state",
                    }:
                        continue
                    lang = index_name[len("harmony-") :]
                    content_lines = await self._scroll_es_index(
                        index_name, {"term": {"domain": domain}}
                    )
                    if content_lines:
                        self._add_bytes_to_tar(
                            tar,
                            content_lines,
                            f"{domain}/content_{lang}.jsonl",
                        )

                if self._qdrant is not None:
                    qdrant_lines = await self._scroll_qdrant_domain(domain)
                    if qdrant_lines:
                        self._add_bytes_to_tar(
                            tar, qdrant_lines, f"{domain}/qdrant_vectors.jsonl"
                        )

    async def _scroll_es_index(
        self, index: str, query_filter: dict[str, pydantic.JsonValue]
    ) -> bytes:
        es = self._es.client
        lines: list[bytes] = []
        pit = None
        try:
            pit_response = await es.open_point_in_time(
                index=index, keep_alive="2m", ignore_unavailable=True
            )
            pit = pit_response.get("id")
        except Exception:
            pit = None

        if pit:
            search_after: list[typing.Any] | None = None
            while True:
                body: dict[str, typing.Any] = {
                    "size": _SCROLL_SIZE,
                    "query": query_filter,
                    "sort": [{"_shard_doc": "asc"}],
                    "pit": {"id": pit, "keep_alive": "2m"},
                }
                if search_after:
                    body["search_after"] = search_after
                resp = await es.search(**body)
                hits = resp.get("hits", {}).get("hits", [])
                if not hits:
                    break
                for hit in hits:
                    doc = {"_id": hit["_id"], **hit.get("_source", {})}
                    lines.append(json.dumps(doc).encode())
                search_after = hits[-1].get("sort")
                pit = resp.get("pit_id", pit)
                if len(hits) < _SCROLL_SIZE:
                    break
            with contextlib.suppress(Exception):
                await es.close_point_in_time(body={"id": pit})
        else:
            resp = await es.search(
                index=index,
                query=query_filter,
                size=_SCROLL_SIZE,
                ignore_unavailable=True,
            )
            hits = resp.get("hits", {}).get("hits", [])
            for hit in hits:
                doc = {"_id": hit["_id"], **hit.get("_source", {})}
                lines.append(json.dumps(doc).encode())

        return b"\n".join(lines) if lines else b""

    async def _scroll_qdrant_domain(self, domain: str) -> bytes:
        if self._qdrant is None:
            return b""

        lines: list[bytes] = []
        client = self._qdrant.client
        collection = self._qdrant.collection
        offset = None
        while True:
            result = await client.scroll(
                collection_name=collection,
                scroll_filter=qdrant_client.models.Filter(
                    must=[
                        qdrant_client.models.FieldCondition(
                            key="path",
                            match=qdrant_client.models.MatchText(text=domain),
                        )
                    ]
                ),
                limit=_SCROLL_SIZE,
                offset=offset,
                with_vectors=True,
                with_payload=True,
            )
            points, next_offset = result
            for point in points:
                payload = point.payload or {}
                if domain not in payload.get("path", ""):
                    continue
                record = {
                    "id": point.id,
                    "payload": payload,
                    "vector": point.vector,
                }
                lines.append(json.dumps(record).encode())
            if next_offset is None:
                break
            offset = next_offset

        return b"\n".join(lines) if lines else b""

    @staticmethod
    def _add_bytes_to_tar(tar: tarfile.TarFile, data: bytes, arcname: str) -> None:
        if not data:
            return
        buf = io.BytesIO(data)
        info = tarfile.TarInfo(name=arcname)
        info.size = len(data)
        tar.addfile(info, buf)

    async def import_archive(self, file_content: bytes) -> dict[str, int]:
        fd, tmp_path = tempfile.mkstemp(suffix=".tar.gz")
        try:
            os.write(fd, file_content)
            os.close(fd)
            result = await self._extract_archive_async(tmp_path)
        finally:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
        return result

    async def _extract_archive_async(self, tmp_path: str) -> dict[str, int]:
        es = self._es.client
        total_docs = 0

        with tarfile.open(tmp_path, "r:gz") as tar:
            members = tar.getmembers()
            for member in members:
                if not _safe_tar_member(member.name):
                    logger.warning("skipping unsafe tar member", name=member.name)
                    continue

                f = tar.extractfile(member)
                if f is None:
                    continue
                raw = f.read()

                if member.name.endswith("/crawl_state.jsonl"):
                    docs = self._parse_jsonl(raw)
                    if docs:
                        await self._bulk_index(es, _STATE_INDEX, docs)

                elif "/content_" in member.name and member.name.endswith(".jsonl"):
                    filename = member.name.split("/")[-1]
                    lang = filename[len("content_") : -len(".jsonl")]
                    index_name = f"harmony-{lang}"
                    docs = self._parse_jsonl(raw)
                    if docs:
                        await self._bulk_index(es, index_name, docs)
                        total_docs += len(docs)

                elif member.name.endswith("/qdrant_vectors.jsonl"):
                    if self._qdrant is not None:
                        records = self._parse_jsonl(raw)
                        await self._upsert_qdrant(records)

        return {"imported_docs": total_docs}

    @staticmethod
    def _parse_jsonl(raw: bytes) -> list[dict[str, pydantic.JsonValue]]:
        docs: list[dict[str, pydantic.JsonValue]] = []
        for line in raw.split(b"\n"):
            line = line.strip()
            if not line:
                continue
            try:
                docs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return docs

    @staticmethod
    async def _bulk_index(
        es: typing.Any, index: str, docs: list[dict[str, pydantic.JsonValue]]
    ) -> None:
        bulk_body: list[dict[str, pydantic.JsonValue] | str] = []
        for doc in docs:
            doc_id = doc.pop("_id", None)
            action: dict[str, typing.Any] = {"index": {"_index": index}}
            if doc_id:
                action["index"]["_id"] = doc_id
            bulk_body.append(action)
            bulk_body.append(doc)
        if bulk_body:
            await es.bulk(operations=bulk_body)

    async def _upsert_qdrant(
        self, records: list[dict[str, pydantic.JsonValue]]
    ) -> None:
        if self._qdrant is None or not records:
            return

        points = []
        for rec in records:
            point_id = rec.get("id")
            vector = rec.get("vector")
            payload = rec.get("payload", {})
            if point_id is None or not vector:
                continue
            points.append(
                qdrant_client.models.PointStruct(
                    id=typing.cast(int | str, point_id),
                    vector=typing.cast(list[float], vector),
                    payload=typing.cast(dict[str, typing.Any] | None, payload),
                )
            )
        if points:
            await self._qdrant.client.upsert(
                collection_name=self._qdrant.collection, points=points
            )
