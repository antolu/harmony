from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import typing
from datetime import UTC, datetime
from pathlib import Path

from harmony.api.models.job import Job, JobStatus


class JobProcessManager:
    """Handles subprocess lifecycle for jobs."""

    def __init__(self) -> None:
        self.processes: dict[str, subprocess.Popen[str]] = {}

    @staticmethod
    def make_env(job_id: str) -> dict[str, str]:
        env = {**os.environ, "HARMONY_CRAWL_JOB_ID": job_id}
        env.setdefault("HARMONY_BACKEND_URL", "http://harmony-api:8000")
        env.setdefault(
            "SCRAPY_SETTINGS_MODULE", "harmony.providers.web_crawler.runtime.settings"
        )
        return env

    def launch_process(
        self,
        job: Job,
        cmd: list[str],
        log_file: Path,
        env: dict[str, str],
        on_started: typing.Callable[[], None],
    ) -> None:
        try:
            self.start_process(job, cmd, log_file, env, on_started)
        except Exception as e:
            job.status = JobStatus.FAILED
            job.finished_at = datetime.now(UTC)
            job.error = str(e)
            with contextlib.suppress(Exception):
                log_file.write_text(f"Launch failed: {e}\n", encoding="utf-8")

    def start_process(
        self,
        job: Job,
        cmd: list[str],
        log_file: Path,
        env: dict[str, str],
        on_started: typing.Callable[[], None],
    ) -> None:
        with log_file.open("w", encoding="utf-8") as log_f:
            process = subprocess.Popen(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                text=True,
                process_group=0,
                env=env,
            )
        self.processes[job.id] = process
        job.pid = process.pid
        job.status = JobStatus.RUNNING
        on_started()

    @staticmethod
    def terminate_process(process: subprocess.Popen[str], *, force: bool) -> None:
        if force:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)

        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            process.wait()
