from __future__ import annotations

from unittest.mock import MagicMock, patch

from harmony.scripts.acl_backfill import AclBackfillJob


def _make_job() -> AclBackfillJob:
    with patch("harmony.scripts.acl_backfill.Elasticsearch"):
        return AclBackfillJob(
            es_host="http://localhost:9200",
            index_base="harmony",
            languages=["en", "fr"],
        )


def test_dry_run_does_not_write() -> None:
    with patch("harmony.scripts.acl_backfill.Elasticsearch") as mock_es_cls:
        mock_es = MagicMock()
        mock_es_cls.return_value = mock_es
        mock_es.count.return_value = {"count": 5}

        job = AclBackfillJob("http://localhost:9200", "harmony", ["en", "fr"])
        result = job.run("*/docs/*", ["read_only"], dry_run=True)

        assert result == 5
        mock_es.update_by_query.assert_not_called()
        assert mock_es.count.called


def test_run_calls_update_by_query_on_all_indices() -> None:
    with patch("harmony.scripts.acl_backfill.Elasticsearch") as mock_es_cls:
        mock_es = MagicMock()
        mock_es_cls.return_value = mock_es
        mock_es.update_by_query.return_value = {"updated": 3, "failures": []}

        job = AclBackfillJob("http://localhost:9200", "harmony", ["en", "fr"])
        result = job.run("*/docs/*", ["read_only", "admin"], dry_run=False)

        expected_indices = ["harmony-crawl-state", "harmony-en", "harmony-fr"]
        assert mock_es.update_by_query.call_count == len(expected_indices)

        called_indices = [
            c.kwargs["index"] for c in mock_es.update_by_query.call_args_list
        ]
        assert set(called_indices) == set(expected_indices)
        assert result == 9  # 3 updated * 3 indices


def test_empty_match_exits_cleanly() -> None:
    with patch("harmony.scripts.acl_backfill.Elasticsearch") as mock_es_cls:
        mock_es = MagicMock()
        mock_es_cls.return_value = mock_es
        mock_es.count.return_value = {"count": 0}

        job = AclBackfillJob("http://localhost:9200", "harmony", ["en"])
        result = job.run("*/nonexistent/*", ["read_only"], dry_run=True)

        assert result == 0


def test_allowed_roles_written_correctly() -> None:
    with patch("harmony.scripts.acl_backfill.Elasticsearch") as mock_es_cls:
        mock_es = MagicMock()
        mock_es_cls.return_value = mock_es
        mock_es.update_by_query.return_value = {"updated": 1, "failures": []}

        job = AclBackfillJob("http://localhost:9200", "harmony", ["en"])
        job.run("*/docs/*", ["read_only", "admin"], dry_run=False)

        calls_by_index = {
            c.kwargs["index"]: c.kwargs for c in mock_es.update_by_query.call_args_list
        }

        content_params = calls_by_index["harmony-en"]["body"]["script"]["params"]
        assert content_params["acl"]["allowed_roles"] == ["read_only", "admin"]
        assert content_params["acl"]["policy_version"] == "v1"

        crawl_state_params = calls_by_index["harmony-crawl-state"]["body"]["script"][
            "params"
        ]
        assert crawl_state_params["allowed_roles"] == ["read_only", "admin"]
