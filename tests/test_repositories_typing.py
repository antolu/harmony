from __future__ import annotations

import inspect
import pathlib
import typing
from datetime import datetime

from harmony.db import repositories


def test_crawl_config_repo_returns_typed_dict() -> None:
    hints = typing.get_type_hints(repositories.CrawlConfigData)
    assert hints["id"] is str
    assert hints["name"] is str
    assert hints["created_at"] is datetime
    assert hints["updated_at"] is datetime

    list_hints = typing.get_type_hints(repositories.CrawlConfigRepo.list)
    assert list_hints["return"] == list[repositories.CrawlConfigData]

    get_hints = typing.get_type_hints(repositories.CrawlConfigRepo.get)
    assert get_hints["return"] == repositories.CrawlConfigData | None


def test_audit_event_repo_returns_typed_dict_and_no_index_ignore() -> None:
    hints = typing.get_type_hints(repositories.AuditEventData)
    assert hints["id"] is str
    assert hints["created_at"] is datetime

    query_hints = typing.get_type_hints(repositories.AuditEventRepo.query)
    assert query_hints["return"] == tuple[list[repositories.AuditEventData], int]

    source = inspect.getsource(repositories.AuditEventRepo.query)
    assert "type: ignore[index]" not in source


def test_job_logs_repo_returns_typed_dict() -> None:
    hints = typing.get_type_hints(repositories.JobLogData)
    assert hints["id"] is str
    assert hints["created_at"] is datetime

    get_logs_hints = typing.get_type_hints(repositories.JobLogsRepo.get_logs)
    assert get_logs_hints["return"] == list[repositories.JobLogData]


def test_crawl_blacklist_repo_returns_typed_dict_and_no_valid_type_ignore() -> None:
    hints = typing.get_type_hints(repositories.CrawlBlacklistData)
    assert hints["id"] is str
    assert hints["created_at"] is datetime

    list_hints = typing.get_type_hints(repositories.CrawlBlacklistRepo.list)
    assert list_hints["return"] == list[repositories.CrawlBlacklistData]

    add_hints = typing.get_type_hints(repositories.CrawlBlacklistRepo.add)
    assert add_hints["return"] == repositories.CrawlBlacklistData

    source = inspect.getsource(repositories.CrawlBlacklistRepo.get_patterns)
    assert "type: ignore[valid-type]" not in source


def test_auth_session_data_datetime_fields_typed() -> None:
    hints = typing.get_type_hints(repositories.AuthSessionData)
    assert hints["created_at"] is datetime
    assert hints["expires_at"] is datetime


def test_data_source_data_datetime_fields_typed() -> None:
    hints = typing.get_type_hints(repositories.DataSourceData)
    assert hints["created_at"] is datetime
    assert hints["updated_at"] is datetime
    assert hints["last_run_at"] == datetime | None


def test_no_remaining_named_ignores_in_repositories() -> None:
    content = pathlib.Path("harmony/db/repositories.py").read_text(encoding="utf-8")
    assert "type: ignore[index]" not in content
