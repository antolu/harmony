from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
from elasticsearch import Elasticsearch

EXPECTED_DOC_COUNT = 2  # Number of test documents


@pytest.mark.skip(reason="disk source removed; indexer is ES-source only")
@pytest.mark.elasticsearch
@pytest.mark.integration
def test_indexer_es_source_vs_disk() -> None:  # noqa: PLR0915, PLR0914
    """
    Integration test: Compare indexing from disk source vs ES source.

    This test verifies that the indexer produces identical results when
    reading from metadata.jsonl files (disk) vs ES state index (elasticsearch).
    """
    es = Elasticsearch(["http://localhost:9200"])

    # Ensure ES is available
    if not es.ping():
        pytest.skip("Elasticsearch not available")

    # Create temporary test directory
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        output_dir = test_dir / "output"
        output_dir.mkdir()

        # Create test HTML files
        test_domain = "test.example.com"
        domain_dir = output_dir / test_domain
        domain_dir.mkdir()

        # Create HTML files
        (domain_dir / "index.html").write_text(
            """<html><head><title>Test Page 1</title></head>
            <body><h1>Test Content 1</h1><p>This is test content.</p></body></html>""",
            encoding="utf-8",
        )

        page2_dir = domain_dir / "page2"
        page2_dir.mkdir()
        (page2_dir / "index.html").write_text(
            """<html><head><title>Test Page 2</title></head>
            <body><h1>Test Content 2</h1><p>More test content.</p></body></html>""",
            encoding="utf-8",
        )

        # Create metadata.jsonl
        # Note: file_path is relative to the metadata.jsonl file's parent directory
        metadata_file = domain_dir / "metadata.jsonl"
        entries = [
            {
                "url": "https://test.example.com",
                "file_path": "index.html",  # Relative to domain_dir
                "depth": 0,
                "crawled_at": "2026-01-09T12:00:00Z",
                "domain": test_domain,
                "path": "/",
                "language": "en",
            },
            {
                "url": "https://test.example.com/page2",
                "file_path": "page2/index.html",  # Relative to domain_dir
                "depth": 1,
                "crawled_at": "2026-01-09T12:00:01Z",
                "domain": test_domain,
                "path": "/page2",
                "language": "en",
            },
        ]

        with metadata_file.open("w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        # Create state index and populate with test data
        state_index = "harmony-test-crawl-state"
        content_index_disk = "harmony-test-disk-en"
        content_index_es = "harmony-test-es-en"

        # Clean up any existing test indices
        for idx in [state_index, content_index_disk, content_index_es]:
            if es.indices.exists(index=idx):
                es.indices.delete(index=idx)

        # Create state index
        es.indices.create(
            index=state_index,
            mappings={
                "properties": {
                    "url": {"type": "keyword"},
                    "domain": {"type": "keyword"},
                    "file_path": {"type": "keyword"},
                    "depth": {"type": "integer"},
                    "last_crawled_at": {"type": "date"},
                    "content_type": {"type": "keyword"},
                }
            },
        )

        # Populate state index with same data as metadata.jsonl
        # Note: State index stores file_path relative to output_dir (includes domain)
        for entry in entries:
            url = str(entry["url"])
            es.index(
                index=state_index,
                id=url,
                document={
                    "url": url,
                    "domain": entry["domain"],
                    "path": entry["path"],
                    "file_path": f"{test_domain}/{entry['file_path']}",  # Include domain in path for state index
                    "depth": entry["depth"],
                    "last_crawled_at": entry["crawled_at"],
                    "content_type": "text/html",
                    "language": entry["language"],
                },
            )

        es.indices.refresh(index=state_index)

        # Test 1: Index from disk source
        result_disk = subprocess.run(
            [
                sys.executable,
                "-m",
                "harmony.indexer.cli",
                "--data_dir",
                str(output_dir),
                "--source",
                "disk",
                "--es_host",
                "http://localhost:9200",
                "--index_base_name",
                "harmony-test-disk",
                "--batch_size",
                "10",
                "--skip_embedding",
                "true",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        print(f"Disk indexing stdout: {result_disk.stdout}")
        print(f"Disk indexing stderr: {result_disk.stderr}")

        assert result_disk.returncode == 0, (
            f"Disk indexing failed: {result_disk.stderr}"
        )

        # Test 2: Index from ES source
        result_es = subprocess.run(
            [
                sys.executable,
                "-m",
                "harmony.indexer.cli",
                "--data_dir",
                str(output_dir),
                "--source",
                "elasticsearch",
                "--state_index",
                state_index,
                "--es_host",
                "http://localhost:9200",
                "--index_base_name",
                "harmony-test-es",
                "--batch_size",
                "10",
                "--skip_embedding",
                "true",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        print(f"ES indexing stdout: {result_es.stdout}")
        print(f"ES indexing stderr: {result_es.stderr}")

        assert result_es.returncode == 0, (
            f"ES indexing failed: stdout={result_es.stdout} stderr={result_es.stderr}"
        )

        # Wait a moment for indices to be created
        time.sleep(1)

        # Refresh indices (check if they exist first)
        if not es.indices.exists(index=content_index_disk):
            pytest.fail(f"Disk index {content_index_disk} was not created")
        if not es.indices.exists(index=content_index_es):
            pytest.fail(f"ES index {content_index_es} was not created")

        es.indices.refresh(index=content_index_disk)
        es.indices.refresh(index=content_index_es)

        # Verify both indices have same document count
        count_disk = es.count(index=content_index_disk)["count"]
        count_es = es.count(index=content_index_es)["count"]

        assert count_disk == EXPECTED_DOC_COUNT, (
            f"Expected {EXPECTED_DOC_COUNT} documents in disk index, got {count_disk}"
        )
        assert count_es == EXPECTED_DOC_COUNT, (
            f"Expected {EXPECTED_DOC_COUNT} documents in ES index, got {count_es}"
        )

        # Verify document content matches
        docs_disk = es.search(
            index=content_index_disk, query={"match_all": {}}, size=10
        )["hits"]["hits"]
        docs_es = es.search(index=content_index_es, query={"match_all": {}}, size=10)[
            "hits"
        ]["hits"]

        # Sort by URL for comparison
        docs_disk_sorted = sorted(docs_disk, key=lambda x: x["_source"]["url"])
        docs_es_sorted = sorted(docs_es, key=lambda x: x["_source"]["url"])

        # Compare content (excluding _base_dir which is not stored in ES)
        for disk_doc, es_doc in zip(docs_disk_sorted, docs_es_sorted, strict=False):
            assert disk_doc["_source"]["url"] == es_doc["_source"]["url"]
            assert disk_doc["_source"]["title"] == es_doc["_source"]["title"]
            assert disk_doc["_source"]["domain"] == es_doc["_source"]["domain"]
            assert disk_doc["_source"]["path"] == es_doc["_source"]["path"]
            assert disk_doc["_source"]["language"] == es_doc["_source"]["language"]
            # Content should be identical
            assert disk_doc["_source"]["content"] == es_doc["_source"]["content"], (
                f"Content mismatch for {disk_doc['_source']['url']}"
            )

        # Clean up test indices
        for idx in [state_index, content_index_disk, content_index_es]:
            if es.indices.exists(index=idx):
                es.indices.delete(index=idx)


@pytest.mark.elasticsearch
@pytest.mark.integration
def test_indexer_es_source_missing_state_index() -> None:
    """Test that indexer fails gracefully when state index doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "harmony.indexer.cli",
                "--data_dir",
                tmpdir,
                "--source",
                "elasticsearch",
                "--state_index",
                "nonexistent-index",
                "--es_host",
                "http://localhost:9200",
                "--index_base_name",
                "harmony-test",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode != 0
        output = (result.stdout + result.stderr).replace("\n", " ")
        assert "does not" in output
        assert "exist" in output


@pytest.mark.elasticsearch
@pytest.mark.integration
def test_indexer_es_source_empty_state() -> None:
    """Test that indexer handles empty state index gracefully."""
    es = Elasticsearch(["http://localhost:9200"])

    if not es.ping():
        pytest.skip("Elasticsearch not available")

    state_index = "harmony-test-empty-state"

    # Clean up if exists
    if es.indices.exists(index=state_index):
        es.indices.delete(index=state_index)

    # Create empty state index
    es.indices.create(
        index=state_index,
        mappings={
            "properties": {
                "url": {"type": "keyword"},
                "domain": {"type": "keyword"},
                "file_path": {"type": "keyword"},
            }
        },
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "harmony.indexer.cli",
                "--data_dir",
                tmpdir,
                "--source",
                "elasticsearch",
                "--state_index",
                state_index,
                "--es_host",
                "http://localhost:9200",
                "--index_base_name",
                "harmony-test-empty",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        # Should exit with warning about no documents
        assert "No documents found" in result.stdout or result.returncode != 0

    # Clean up
    if es.indices.exists(index=state_index):
        es.indices.delete(index=state_index)


def test_document_without_acl_config_has_empty_allowed_roles(tmp_path: Path) -> None:

    from harmony.indexer.cli import _generate_docs  # noqa: PLC2701

    html_file = tmp_path / "index.html"
    html_file.write_text("<html><head><title>T</title></head><body>body</body></html>")

    entry = {
        "url": "https://example.com/",
        "file_path": "index.html",
        "depth": 0,
        "crawled_at": "2026-01-01T00:00:00Z",
        "domain": "example.com",
        "path": "/",
        "language": "en",
        "_base_dir": tmp_path,
    }

    docs = list(
        _generate_docs(
            [entry],
            "harmony-en",
            {"html": 0, "documents": 0, "parse_errors": 0, "missing_files": 0},
        )
    )
    assert len(docs) == 1
    source = docs[0]["_source"]
    assert "acl" in source
    assert source["acl"]["allowed_roles"] == ["anonymous"]
    assert source["acl"]["policy_version"] == "v1"


def test_document_with_acl_config_has_correct_allowed_roles_and_policy_version(
    tmp_path: Path,
) -> None:

    from harmony.indexer.cli import _generate_docs  # noqa: PLC2701

    html_file = tmp_path / "index.html"
    html_file.write_text("<html><head><title>T</title></head><body>body</body></html>")

    entry = {
        "url": "https://example.com/",
        "file_path": "index.html",
        "depth": 0,
        "crawled_at": "2026-01-01T00:00:00Z",
        "domain": "example.com",
        "path": "/",
        "language": "en",
        "acl_allowed_roles": ["anonymous", "read_only", "admin"],
        "_base_dir": tmp_path,
    }

    docs = list(
        _generate_docs(
            [entry],
            "harmony-en",
            {"html": 0, "documents": 0, "parse_errors": 0, "missing_files": 0},
        )
    )
    assert len(docs) == 1
    source = docs[0]["_source"]
    assert source["acl"]["allowed_roles"] == ["anonymous", "read_only", "admin"]
    assert source["acl"]["policy_version"] == "v1"
