from __future__ import annotations

import unittest.mock

from harmony.api.models.job import JobStatus


def test_interrupted_status_exists() -> None:
    assert hasattr(JobStatus, "INTERRUPTED"), (
        "JobStatus must have INTERRUPTED value (Plan 06 adds this)"
    )


def test_interrupted_value_is_string() -> None:
    assert str(JobStatus.INTERRUPTED) == "interrupted", (  # type: ignore[attr-defined]
        "JobStatus.INTERRUPTED must equal 'interrupted'"
    )


async def test_zombie_jobs_become_interrupted() -> None:
    from harmony.api.services.admin._job_manager import JobManager  # noqa: PLC2701

    job_id = "test-zombie-job-id"

    mock_pool = unittest.mock.AsyncMock()
    mock_repo = unittest.mock.AsyncMock()
    from harmony.db.repositories import JobData

    mock_repo.load_all.return_value = [
        JobData(
            id=job_id,
            type="crawl",
            status="running",
            config_name="test",
            started_at=None,
            finished_at=None,
            pid=None,
            log_file=None,
            error=None,
        )
    ]
    mock_repo.update_status = unittest.mock.AsyncMock()

    with (
        unittest.mock.patch(
            "harmony.api.services.admin._job_persistence.get_async_pool",
            return_value=mock_pool,
        ),
        unittest.mock.patch(
            "harmony.api.services.admin._job_persistence.JobsRepo",
            return_value=mock_repo,
        ),
    ):
        manager = JobManager()
        loaded = await manager._persistence_manager.load_persisted_jobs()
        manager._jobs.update(loaded)

    job = manager._jobs[job_id]
    assert job.status == JobStatus.INTERRUPTED, (  # type: ignore[attr-defined]
        f"Zombie job status must be INTERRUPTED, got {job.status} (Plan 06 fixes this)"
    )
