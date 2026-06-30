from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import subprocess
import typing
from pathlib import Path

if typing.TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from harmony.api.models.job import Job


class SubprocessJobExecutor:
    """Runs jobs as local subprocesses (dev / single-node).

    Owns the live `_processes` map (job_id -> Popen). This is the behavior the
    old JobProcessManager provided, moved behind the JobExecutor seam.
    """

    def __init__(self) -> None:
        self._processes: dict[str, subprocess.Popen[str]] = {}

    @property
    def processes(self) -> dict[str, subprocess.Popen[str]]:
        return self._processes

    async def submit(
        self,
        job: Job,
        command: list[str],
        env: dict[str, str],
        *,
        append_log: bool = False,
    ) -> str:
        """Launch the command, writing stdout/stderr to the job's log file."""
        log_file = Path(job.log_file) if job.log_file else None
        with contextlib.ExitStack() as stack:
            if log_file is not None:
                mode = "a" if append_log else "w"
                log_f = stack.enter_context(log_file.open(mode, encoding="utf-8"))
                stdout: typing.Any = log_f
            else:
                stdout = subprocess.DEVNULL
            process = subprocess.Popen(
                command,
                stdout=stdout,
                stderr=subprocess.STDOUT,
                text=True,
                process_group=0,
                env=env,
            )
        self._processes[job.id] = process
        job.pid = process.pid
        return str(process.pid)

    async def wait(self, job_id: str) -> int | None:
        """Wait for a job's process to exit and return its code."""
        process = self._processes.get(job_id)
        if process is None:
            return None
        return await asyncio.to_thread(process.wait)

    async def cancel(self, job: Job, *, force: bool = False) -> None:
        process = self._processes.get(job.id)
        if process is None:
            return
        with contextlib.suppress(ProcessLookupError):
            self._terminate(process, force=force)
        self._processes.pop(job.id, None)

    def pause(self, job: Job) -> None:
        process = self._processes.get(job.id)
        if process:
            os.killpg(os.getpgid(process.pid), signal.SIGSTOP)

    def resume(self, job: Job) -> None:
        process = self._processes.get(job.id)
        if process:
            os.killpg(os.getpgid(process.pid), signal.SIGCONT)

    def get_log_stream(self, job: Job) -> AsyncIterator[str]:
        return self._tail_local_log(job)

    async def _tail_local_log(self, job: Job) -> AsyncIterator[str]:
        if not job.log_file:
            return
        log_file = Path(job.log_file)
        if not log_file.exists():
            return
        position = 0
        process = self._processes.get(job.id)
        while True:
            with (
                contextlib.suppress(Exception),
                log_file.open("r", encoding="utf-8") as f,
            ):
                f.seek(position)
                for line in f:
                    yield line.rstrip("\n")
                position = f.tell()
            if process is not None and process.poll() is not None:
                break
            await asyncio.sleep(0.5)

    @staticmethod
    def _terminate(process: subprocess.Popen[str], *, force: bool) -> None:
        if force:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            process.wait()
