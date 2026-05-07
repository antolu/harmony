from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from harmony.api.models.job import Job, JobStatus
from harmony.api.services.admin.job_manager import JobManager


async def test_start_embed_job_creates_job_with_embed_type() -> None:
    manager = JobManager()
    log_path = MagicMock()
    log_file_mock = MagicMock()
    log_path.__truediv__ = MagicMock(return_value=log_file_mock)
    log_file_mock.open = MagicMock(
        return_value=MagicMock(
            __enter__=MagicMock(return_value=MagicMock()),
            __exit__=MagicMock(return_value=False),
        )
    )
    manager._job_log_path = log_path

    mock_pool = AsyncMock()
    mock_repo = AsyncMock()
    mock_proc = MagicMock()
    mock_proc.pid = 9999

    with (
        patch(
            "harmony.api.services.admin.job_manager.subprocess.Popen",
            return_value=mock_proc,
        ),
        patch(
            "harmony.api.services.admin.job_manager.get_async_pool",
            AsyncMock(return_value=mock_pool),
        ),
        patch(
            "harmony.api.services.admin.job_manager.JobsRepo", return_value=mock_repo
        ),
        patch("asyncio.create_task"),
    ):
        job = await manager.start_embed_job(
            embedding_model="ollama/qwen3-embedding:0.6b"
        )

    assert job.type == "embed"
    assert job.status == JobStatus.RUNNING
    assert "qwen3-embedding" in job.config_name


async def test_monitor_embed_job_clears_changed_flag_on_success() -> None:
    manager = JobManager()
    manager._job_log_path = MagicMock()

    job = Job(
        id="test123",
        type="embed",
        config_name="embed-test",
        status=JobStatus.RUNNING,
    )
    manager._jobs["test123"] = job

    mock_proc = MagicMock()
    mock_proc.poll.side_effect = [None, None, 0]
    manager._processes["test123"] = mock_proc

    mock_pool = AsyncMock()
    mock_repo = AsyncMock()
    mock_store = AsyncMock()

    with (
        patch(
            "harmony.api.services.admin.job_manager.get_async_pool",
            AsyncMock(return_value=mock_pool),
        ),
        patch(
            "harmony.api.services.admin.job_manager.JobsRepo", return_value=mock_repo
        ),
        patch(
            "harmony.api.services.admin.model_settings.model_settings_store",
            mock_store,
        ),
        patch("asyncio.sleep", AsyncMock()),
    ):
        await manager._monitor_embed_job("test123")

    assert job.status == JobStatus.COMPLETED
    mock_store.clear_embedding_changed.assert_called_once()
