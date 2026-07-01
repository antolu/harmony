from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harmony.models import Job, JobStatus
from harmony.services.admin import JobManager


@pytest.mark.asyncio
async def test_fire_event_called_on_job_complete(job_manager: JobManager) -> None:
    mock_webhook = MagicMock()
    mock_webhook.fire_event = AsyncMock()
    job_manager.set_webhook_service(mock_webhook)

    job = Job(id="test-01", type="crawl", config_name="test-config")

    with patch("harmony.services.admin._job_log_stream.JobsRepo") as mock_jobs_repo_cls:
        mock_repo = MagicMock()
        mock_repo.update_progress = AsyncMock()
        mock_repo.update_status = AsyncMock()
        mock_jobs_repo_cls.return_value = mock_repo
        job_manager._log_stream_manager._config_store = MagicMock()

        await job_manager._log_stream_manager._finalize_job(
            "test-01", job, return_code=0
        )

    assert mock_webhook.fire_event.call_count == 1
    call_args = mock_webhook.fire_event.call_args[0]
    assert call_args[0] == "job_complete"
    assert call_args[1]["job_id"] == "test-01"
    assert call_args[1]["status"] == str(JobStatus.COMPLETED)


@pytest.mark.asyncio
async def test_fire_event_called_on_job_failed(job_manager: JobManager) -> None:
    mock_webhook = MagicMock()
    mock_webhook.fire_event = AsyncMock()
    job_manager.set_webhook_service(mock_webhook)

    job = Job(id="test-02", type="index", config_name="test-config")

    with patch("harmony.services.admin._job_log_stream.JobsRepo") as mock_jobs_repo_cls:
        mock_repo = MagicMock()
        mock_repo.update_progress = AsyncMock()
        mock_repo.update_status = AsyncMock()
        mock_jobs_repo_cls.return_value = mock_repo
        job_manager._log_stream_manager._config_store = MagicMock()

        await job_manager._log_stream_manager._finalize_job(
            "test-02", job, return_code=1
        )

    assert mock_webhook.fire_event.call_count == 1
    call_args = mock_webhook.fire_event.call_args[0]
    assert call_args[0] == "job_failed"
    assert call_args[1]["job_id"] == "test-02"
    assert call_args[1]["status"] == str(JobStatus.FAILED)


@pytest.mark.asyncio
async def test_fire_event_skipped_when_no_webhook_service(
    job_manager: JobManager,
) -> None:
    job = Job(id="test-03", type="crawl", config_name="test-config")

    with patch("harmony.services.admin._job_log_stream.JobsRepo") as mock_jobs_repo_cls:
        mock_repo = MagicMock()
        mock_repo.update_progress = AsyncMock()
        mock_repo.update_status = AsyncMock()
        mock_jobs_repo_cls.return_value = mock_repo
        job_manager._log_stream_manager._config_store = MagicMock()

        await job_manager._log_stream_manager._finalize_job(
            "test-03", job, return_code=0
        )
