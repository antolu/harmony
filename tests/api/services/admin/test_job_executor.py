from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from harmony.api.models.job import Job
from harmony.api.services.admin.jobs import (
    JobExecutor,
    SubprocessJobExecutor,
)


def _make_job(tmp_path: Path) -> Job:
    return Job(
        id="abc12345",
        type="crawl",
        config_name="test",
        log_file=str(tmp_path / "job.log"),
        started_at=datetime.now(UTC),
    )


def test_subprocess_executor_satisfies_protocol() -> None:
    assert isinstance(SubprocessJobExecutor(), JobExecutor)


async def test_submit_launches_command_and_records_handle(tmp_path: Path) -> None:
    executor = SubprocessJobExecutor()
    job = _make_job(tmp_path)

    handle = await executor.submit(job, ["true"], {})

    assert handle == str(job.pid)
    assert job.id in executor.processes
    return_code = await executor.wait(job.id)
    assert return_code == 0


async def test_cancel_is_noop_on_finished_job(tmp_path: Path) -> None:
    executor = SubprocessJobExecutor()
    job = _make_job(tmp_path)

    await executor.submit(job, ["true"], {})
    await executor.wait(job.id)

    await executor.cancel(job)
    assert job.id not in executor.processes


async def test_cancel_unknown_job_is_noop(tmp_path: Path) -> None:
    executor = SubprocessJobExecutor()
    job = _make_job(tmp_path)
    await executor.cancel(job)


async def test_submit_writes_log_file(tmp_path: Path) -> None:
    executor = SubprocessJobExecutor()
    log_file = tmp_path / "job.log"
    job = _make_job(tmp_path)

    await executor.submit(job, ["sh", "-c", "echo hello"], {})
    await executor.wait(job.id)

    assert log_file.read_text(encoding="utf-8").strip() == "hello"
