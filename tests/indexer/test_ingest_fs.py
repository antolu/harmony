from __future__ import annotations

import typing
from pathlib import Path
from unittest import mock

import pytest

from harmony.indexer import _ingest_fs  # noqa: PLC2701


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_file_sha256_consistent_and_changes_with_content(tmp_path: Path) -> None:
    file_path = tmp_path / "doc.txt"
    _write(file_path, "hello world")
    digest_1 = _ingest_fs.file_sha256(file_path)
    digest_2 = _ingest_fs.file_sha256(file_path)
    assert digest_1 == digest_2

    _write(file_path, "hello world, changed")
    digest_3 = _ingest_fs.file_sha256(file_path)
    assert digest_3 != digest_1


def test_file_uri_normalized_for_trailing_slash_root(tmp_path: Path) -> None:
    file_path = tmp_path / "sub" / "doc.txt"
    _write(file_path, "content")

    root_no_slash = tmp_path
    root_with_slash = Path(f"{tmp_path}/")

    uri_1 = _ingest_fs.file_uri(root_no_slash, file_path)
    uri_2 = _ingest_fs.file_uri(root_with_slash, file_path)
    assert uri_1 == uri_2


def test_iter_candidate_files_respects_include_exclude(tmp_path: Path) -> None:
    _write(tmp_path / "keep.txt", "a")
    _write(tmp_path / "node_modules" / "skip.txt", "b")
    _write(tmp_path / ".git" / "skip2.txt", "c")

    candidates = set(
        _ingest_fs._iter_candidate_files(
            tmp_path,
            include_patterns=["**/*"],
            exclude_patterns=["**/.git/**", "**/node_modules/**"],
        )
    )
    names = {p.name for p in candidates}
    assert "keep.txt" in names
    assert "skip.txt" not in names
    assert "skip2.txt" not in names


@pytest.mark.asyncio
async def test_ingest_skips_unchanged_file(tmp_path: Path) -> None:
    file_path = tmp_path / "doc.txt"
    _write(file_path, "stable content")
    current_hash = _ingest_fs.file_sha256(file_path)

    fs_repo = mock.AsyncMock()
    fs_repo.get_hash.return_value = current_hash
    fs_repo.list_uris.return_value = []

    ds_repo = mock.AsyncMock()
    ds_repo.get.return_value = {
        "id": "ds-1",
        "name": "test-source",
        "config": {
            "root_path": str(tmp_path),
            "include_patterns": ["**/*"],
            "exclude_patterns": [],
        },
    }

    with (
        mock.patch.object(
            _ingest_fs, "_process_document", new_callable=mock.AsyncMock
        ) as mock_process,
        mock.patch.object(_ingest_fs, "_bulk_index_entries") as mock_bulk_index,
        mock.patch.object(_ingest_fs, "_embed_and_upsert_entries") as mock_embed,
        mock.patch.object(_ingest_fs, "_sync_deletions") as mock_sync,
    ):
        await _ingest_fs._ingest(
            data_source_id="ds-1",
            es_host="http://es:9200",
            index_base_name="harmony",
            qdrant_host="http://qdrant:6333",
            qdrant_collection="harmony",
            embedding_model="fake-model",
            embedding_batch_size=64,
            skip_embedding=False,
            ds_repo=ds_repo,
            fs_repo=fs_repo,
            model_registry_service=mock.AsyncMock(),
        )

    mock_process.assert_not_called()
    mock_bulk_index.assert_called_once()
    indexed_entries = mock_bulk_index.call_args.args[0]
    assert indexed_entries == []
    mock_embed.assert_not_called()
    mock_sync.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_indexes_changed_or_new_file(tmp_path: Path) -> None:
    file_path = tmp_path / "doc.txt"
    _write(file_path, "new content")

    fs_repo = mock.AsyncMock()
    fs_repo.get_hash.return_value = None
    fs_repo.list_uris.return_value = []

    ds_repo = mock.AsyncMock()
    ds_repo.get.return_value = {
        "id": "ds-1",
        "name": "test-source",
        "config": {
            "root_path": str(tmp_path),
            "include_patterns": ["**/*"],
            "exclude_patterns": [],
        },
    }

    with (
        mock.patch.object(
            _ingest_fs,
            "_process_document",
            new_callable=mock.AsyncMock,
            return_value=("Doc Title", "doc body"),
        ) as mock_process,
        mock.patch.object(_ingest_fs, "_bulk_index_entries") as mock_bulk_index,
        mock.patch.object(_ingest_fs, "_embed_and_upsert_entries") as mock_embed,
        mock.patch.object(_ingest_fs, "_sync_deletions") as mock_sync,
    ):
        await _ingest_fs._ingest(
            data_source_id="ds-1",
            es_host="http://es:9200",
            index_base_name="harmony",
            qdrant_host="http://qdrant:6333",
            qdrant_collection="harmony",
            embedding_model="fake-model",
            embedding_batch_size=64,
            skip_embedding=False,
            ds_repo=ds_repo,
            fs_repo=fs_repo,
            model_registry_service=mock.AsyncMock(),
        )

    mock_process.assert_called_once()
    fs_repo.upsert.assert_called_once()
    mock_bulk_index.assert_called_once()
    indexed_entries = mock_bulk_index.call_args.args[0]
    assert len(indexed_entries) == 1
    mock_embed.assert_called_once()
    mock_sync.assert_called_once()


def test_es_doc_shape_for_filesystem_entry(tmp_path: Path) -> None:
    file_path = tmp_path / "sub" / "doc.txt"
    _write(file_path, "body text")

    entry = _ingest_fs._build_entry(
        root=tmp_path,
        file_path=file_path,
        title="Doc Title",
        content="body text",
        source_name="my-source",
    )
    doc = _ingest_fs._entry_to_es_source(entry)

    for key in ("source_name", "file_path", "file_type", "indexed_at", "size_bytes"):
        assert key in doc
    for key in ("domain", "depth", "crawled_at"):
        assert key not in doc

    assert doc["source_name"] == "my-source"
    assert doc["file_path"] == "sub/doc.txt"
    assert doc["file_type"] == "txt"


@pytest.mark.asyncio
async def test_ingest_calls_embed_and_upsert_with_indexed_entries(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "doc.txt"
    _write(file_path, "embed me")

    fs_repo = mock.AsyncMock()
    fs_repo.get_hash.return_value = None
    fs_repo.list_uris.return_value = []

    ds_repo = mock.AsyncMock()
    ds_repo.get.return_value = {
        "id": "ds-1",
        "name": "test-source",
        "config": {
            "root_path": str(tmp_path),
            "include_patterns": ["**/*"],
            "exclude_patterns": [],
        },
    }

    with (
        mock.patch.object(
            _ingest_fs,
            "_process_document",
            new_callable=mock.AsyncMock,
            return_value=("Title", "embed me"),
        ),
        mock.patch.object(_ingest_fs, "_bulk_index_entries"),
        mock.patch.object(_ingest_fs, "_embed_and_upsert_entries") as mock_embed,
        mock.patch.object(_ingest_fs, "_sync_deletions"),
    ):
        await _ingest_fs._ingest(
            data_source_id="ds-1",
            es_host="http://es:9200",
            index_base_name="harmony",
            qdrant_host="http://qdrant:6333",
            qdrant_collection="harmony",
            embedding_model="fake-model",
            embedding_batch_size=64,
            skip_embedding=False,
            ds_repo=ds_repo,
            fs_repo=fs_repo,
            model_registry_service=mock.AsyncMock(),
        )

    mock_embed.assert_called_once()
    all_entries = mock_embed.call_args.kwargs.get(
        "all_entries",
        mock_embed.call_args.args[0] if mock_embed.call_args.args else None,
    )
    assert all_entries is not None
    assert len(all_entries) == 1


@pytest.mark.asyncio
async def test_ingest_skips_embed_and_upsert_when_skip_embedding(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "doc.txt"
    _write(file_path, "no embed")

    fs_repo = mock.AsyncMock()
    fs_repo.get_hash.return_value = None
    fs_repo.list_uris.return_value = []

    ds_repo = mock.AsyncMock()
    ds_repo.get.return_value = {
        "id": "ds-1",
        "name": "test-source",
        "config": {
            "root_path": str(tmp_path),
            "include_patterns": ["**/*"],
            "exclude_patterns": [],
        },
    }

    with (
        mock.patch.object(
            _ingest_fs,
            "_process_document",
            new_callable=mock.AsyncMock,
            return_value=("Title", "no embed"),
        ),
        mock.patch.object(_ingest_fs, "_bulk_index_entries"),
        mock.patch.object(_ingest_fs, "_embed_and_upsert_entries") as mock_embed,
        mock.patch.object(_ingest_fs, "_sync_deletions"),
    ):
        await _ingest_fs._ingest(
            data_source_id="ds-1",
            es_host="http://es:9200",
            index_base_name="harmony",
            qdrant_host="http://qdrant:6333",
            qdrant_collection="harmony",
            embedding_model="fake-model",
            embedding_batch_size=64,
            skip_embedding=True,
            ds_repo=ds_repo,
            fs_repo=fs_repo,
            model_registry_service=mock.AsyncMock(),
        )

    mock_embed.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_deletion_sync_removes_stale_uris(tmp_path: Path) -> None:
    file_path = tmp_path / "still_here.txt"
    _write(file_path, "present")

    current_uri = _ingest_fs.file_uri(tmp_path, file_path)
    stale_uri = _ingest_fs.file_uri(tmp_path, tmp_path / "deleted.txt")

    fs_repo = mock.AsyncMock()
    fs_repo.get_hash.return_value = _ingest_fs.file_sha256(file_path)
    fs_repo.list_uris.return_value = [current_uri, stale_uri]

    ds_repo = mock.AsyncMock()
    ds_repo.get.return_value = {
        "id": "ds-1",
        "name": "test-source",
        "config": {
            "root_path": str(tmp_path),
            "include_patterns": ["**/*"],
            "exclude_patterns": [],
        },
    }

    captured: dict[str, typing.Any] = {}

    async def _fake_sync_deletions(  # noqa: PLR0913
        *,
        fs_repo: typing.Any,
        data_source_id: str,
        stale_uris: list[str],
        es_host: str,
        index_name: str,
        qdrant_host: str,
        qdrant_collection: str,
        skip_embedding: bool,
    ) -> None:
        captured["stale_uris"] = stale_uris

    with (
        mock.patch.object(
            _ingest_fs, "_process_document", new_callable=mock.AsyncMock
        ) as mock_process,
        mock.patch.object(_ingest_fs, "_bulk_index_entries"),
        mock.patch.object(_ingest_fs, "_embed_and_upsert_entries"),
        mock.patch.object(
            _ingest_fs, "_sync_deletions", side_effect=_fake_sync_deletions
        ),
    ):
        await _ingest_fs._ingest(
            data_source_id="ds-1",
            es_host="http://es:9200",
            index_base_name="harmony",
            qdrant_host="http://qdrant:6333",
            qdrant_collection="harmony",
            embedding_model="fake-model",
            embedding_batch_size=64,
            skip_embedding=False,
            ds_repo=ds_repo,
            fs_repo=fs_repo,
            model_registry_service=mock.AsyncMock(),
        )

    mock_process.assert_not_called()
    assert captured["stale_uris"] == [stale_uri]
    assert current_uri not in captured["stale_uris"]
