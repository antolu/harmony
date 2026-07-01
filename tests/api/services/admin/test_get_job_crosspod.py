from __future__ import annotations

from unittest.mock import AsyncMock

from harmony.api.services.admin import JobManager
from harmony.models import Job, JobStatus


async def test_get_job_async_falls_back_to_postgres(job_manager: JobManager) -> None:
    remote_job = Job(
        id="remote01", type="crawl", config_name="c", status=JobStatus.RUNNING
    )
    job_manager._persistence_manager.get_job = AsyncMock(return_value=remote_job)  # type: ignore[method-assign]

    result = await job_manager.get_job_async("remote01")

    assert result is remote_job
    job_manager._persistence_manager.get_job.assert_awaited_once_with("remote01")


async def test_get_job_async_prefers_local(job_manager: JobManager) -> None:
    local_job = Job(
        id="local01", type="crawl", config_name="c", status=JobStatus.RUNNING
    )
    job_manager._jobs["local01"] = local_job
    job_manager._persistence_manager.get_job = AsyncMock()  # type: ignore[method-assign]

    result = await job_manager.get_job_async("local01")

    assert result is local_job
    job_manager._persistence_manager.get_job.assert_not_awaited()


async def test_get_job_async_absent_returns_none(job_manager: JobManager) -> None:
    job_manager._persistence_manager.get_job = AsyncMock(return_value=None)  # type: ignore[method-assign]

    result = await job_manager.get_job_async("missing")

    assert result is None


def test_get_job_sync_is_local_only(job_manager: JobManager) -> None:
    assert job_manager.get_job("missing") is None
