from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harmony.api.models.job import Job, JobStatus
from harmony.api.services.admin import JobManager


@pytest.fixture
def k8s_executor() -> MagicMock:
    executor = MagicMock()

    async def _stream(job: Job) -> AsyncIterator[str]:
        for line in ("line-1", "line-2", "line-3"):
            yield line

    executor.get_log_stream = _stream
    return executor


async def test_monitor_k8s_job_persists_each_line(k8s_executor: MagicMock) -> None:
    manager = JobManager(pool=AsyncMock(), executor=k8s_executor)
    manager._log_stream_manager._config_store = MagicMock()
    repo = AsyncMock()
    manager._log_stream_manager._job_logs_repo = repo

    job = Job(id="k8s01", type="crawl", config_name="c", status=JobStatus.RUNNING)
    manager._jobs["k8s01"] = job

    with patch(
        "harmony.api.services.admin._job_log_stream.JobsRepo", return_value=AsyncMock()
    ):
        await manager._log_stream_manager.monitor_k8s_job("k8s01")

    assert repo.append.await_count == 3
    repo.append.assert_any_await("k8s01", "info", "line-1")
    assert job.status == JobStatus.COMPLETED


async def test_monitor_k8s_job_absent_is_noop(k8s_executor: MagicMock) -> None:
    manager = JobManager(pool=AsyncMock(), executor=k8s_executor)
    repo = AsyncMock()
    manager._log_stream_manager._job_logs_repo = repo

    await manager._log_stream_manager.monitor_k8s_job("missing")

    repo.append.assert_not_awaited()


async def test_schedule_monitor_uses_k8s_path_for_non_subprocess(
    k8s_executor: MagicMock,
) -> None:
    manager = JobManager(pool=AsyncMock(), executor=k8s_executor)
    called: list[str] = []

    async def _k8s(job_id: str) -> None:
        called.append(job_id)

    manager._log_stream_manager.monitor_k8s_job = _k8s  # type: ignore[method-assign]
    manager._log_stream_manager.monitor_job = MagicMock()  # type: ignore[method-assign]

    manager._schedule_monitor("k8s01")
    await manager._progress_tasks["k8s01"]

    assert called == ["k8s01"]
    manager._log_stream_manager.monitor_job.assert_not_called()
