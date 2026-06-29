from __future__ import annotations

from unittest.mock import AsyncMock

from harmony.api.models.job import Job, JobStatus
from harmony.api.services.admin import JobManager


def _make_manager() -> JobManager:
    return JobManager()


async def test_get_job_async_falls_back_to_postgres() -> None:
    manager = _make_manager()
    remote_job = Job(
        id="remote01", type="crawl", config_name="c", status=JobStatus.RUNNING
    )
    manager._persistence_manager.get_job = AsyncMock(return_value=remote_job)  # type: ignore[method-assign]

    result = await manager.get_job_async("remote01")

    assert result is remote_job
    manager._persistence_manager.get_job.assert_awaited_once_with("remote01")


async def test_get_job_async_prefers_local() -> None:
    manager = _make_manager()
    local_job = Job(
        id="local01", type="crawl", config_name="c", status=JobStatus.RUNNING
    )
    manager._jobs["local01"] = local_job
    manager._persistence_manager.get_job = AsyncMock()  # type: ignore[method-assign]

    result = await manager.get_job_async("local01")

    assert result is local_job
    manager._persistence_manager.get_job.assert_not_awaited()


async def test_get_job_async_absent_returns_none() -> None:
    manager = _make_manager()
    manager._persistence_manager.get_job = AsyncMock(return_value=None)  # type: ignore[method-assign]

    result = await manager.get_job_async("missing")

    assert result is None


def test_get_job_sync_is_local_only() -> None:
    manager = _make_manager()
    assert manager.get_job("missing") is None
