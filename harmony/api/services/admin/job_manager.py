from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

from harmony.api.models.job import Job, JobProgress, JobStatus, JobType
from harmony.api.services.admin.config_store import config_store

logger = logging.getLogger(__name__)


class JobManager:
    """Manages job lifecycle including subprocess management."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._job_state_path: Path | None = None
        self._job_log_path: Path | None = None
        self._progress_tasks: dict[str, asyncio.Task[None]] = {}

    def initialize(
        self,
        job_state_path: Path,
        job_log_path: Path,
    ) -> None:
        """Initialize the job manager."""
        self._job_state_path = job_state_path
        self._job_log_path = job_log_path

        self._load_persisted_jobs()

    @property
    def job_state_path(self) -> Path:
        if self._job_state_path is None:
            msg = "JobManager not initialized. Call initialize() first."
            raise RuntimeError(msg)
        return self._job_state_path

    @property
    def job_log_path(self) -> Path:
        if self._job_log_path is None:
            msg = "JobManager not initialized. Call initialize() first."
            raise RuntimeError(msg)
        return self._job_log_path

    def _load_persisted_jobs(self) -> None:
        """Load jobs from persisted state."""
        jobs_file = self.job_state_path / "jobs.json"
        if jobs_file.exists():
            try:
                with jobs_file.open("r") as f:
                    data = json.load(f)
                for job_data in data:
                    job = Job(**job_data)
                    if job.status == JobStatus.RUNNING:
                        job.status = JobStatus.STOPPED
                        job.error = "Job stopped due to server restart"
                    self._jobs[job.id] = job
                logger.info(f"Loaded {len(self._jobs)} jobs from state")
            except Exception as e:
                logger.warning(f"Failed to load persisted jobs: {e}")

    def _persist_jobs(self) -> None:
        """Persist jobs to disk."""
        jobs_file = self.job_state_path / "jobs.json"
        with jobs_file.open("w") as f:
            json.dump([job.model_dump(mode="json") for job in self._jobs.values()], f)

    def list_jobs(
        self,
        job_type: JobType | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[Job]:
        """List jobs with optional filtering."""
        jobs = list(self._jobs.values())

        if job_type:
            jobs = [j for j in jobs if j.type == job_type]
        if status:
            jobs = [j for j in jobs if j.status == status]

        jobs.sort(
            key=lambda j: j.started_at or datetime.min.replace(tzinfo=UTC), reverse=True
        )
        return jobs[:limit]

    def get_job(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    async def start_crawl_job(
        self,
        config_name: str,
        output_override: str | None = None,
    ) -> Job:
        """Start a crawl job."""
        config = config_store.get_config("crawler", config_name)
        if config is None:
            msg = f"Config '{config_name}' not found"
            raise ValueError(msg)

        job_id = str(uuid.uuid4())[:8]
        log_file = self.job_log_path / f"crawl-{job_id}.log"
        stats_file = self.job_state_path / f"crawl-{job_id}.stats.json"

        job = Job(
            id=job_id,
            type="crawl",
            config_name=config_name,
            log_file=str(log_file),
            stats_file=str(stats_file),
            started_at=datetime.now(UTC),
        )

        self.job_state_path / f"crawl-{job_id}.config.yaml"
        config_store.save_config("crawler", f"__job_{job_id}", config)

        cmd = [
            "harmony-crawl",
            "--config",
            str(config_store.get_config_path("crawler", f"__job_{job_id}")),
            "--crawler.stats_export_file",
            str(stats_file),
        ]

        if output_override:
            cmd.extend(["--crawler.output", output_override])

        try:
            with log_file.open("w") as log_f:
                process = subprocess.Popen(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    preexec_fn=os.setsid,  # noqa: PLW1509
                )

            self._processes[job_id] = process
            job.pid = process.pid
            job.status = JobStatus.RUNNING

            self._progress_tasks[job_id] = asyncio.create_task(
                self._monitor_job(job_id)
            )

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)

        self._jobs[job_id] = job
        self._persist_jobs()
        return job

    async def start_index_job(self, config_name: str) -> Job:
        """Start an index job."""
        config = config_store.get_config("indexer", config_name)
        if config is None:
            msg = f"Config '{config_name}' not found"
            raise ValueError(msg)

        job_id = str(uuid.uuid4())[:8]
        log_file = self.job_log_path / f"index-{job_id}.log"

        job = Job(
            id=job_id,
            type="index",
            config_name=config_name,
            log_file=str(log_file),
            started_at=datetime.now(UTC),
        )

        config_store.save_config("indexer", f"__job_{job_id}", config)

        cmd = [
            "harmony-index",
            "--config",
            str(config_store.get_config_path("indexer", f"__job_{job_id}")),
        ]

        try:
            with log_file.open("w") as log_f:
                process = subprocess.Popen(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    preexec_fn=os.setsid,  # noqa: PLW1509
                )

            self._processes[job_id] = process
            job.pid = process.pid
            job.status = JobStatus.RUNNING

            self._progress_tasks[job_id] = asyncio.create_task(
                self._monitor_job(job_id)
            )

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)

        self._jobs[job_id] = job
        self._persist_jobs()
        return job

    async def stop_job(self, job_id: str, *, force: bool = False) -> Job:
        """Stop a running job."""
        job = self._jobs.get(job_id)
        if job is None:
            msg = f"Job '{job_id}' not found"
            raise ValueError(msg)

        if job.status != JobStatus.RUNNING:
            msg = f"Job '{job_id}' is not running"
            raise ValueError(msg)

        process = self._processes.get(job_id)
        if process:
            try:
                if force:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)

                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    process.wait()
            except ProcessLookupError:
                pass

            del self._processes[job_id]

        job.status = JobStatus.STOPPED
        job.finished_at = datetime.now(UTC)
        self._persist_jobs()

        if job_id in self._progress_tasks:
            self._progress_tasks[job_id].cancel()
            del self._progress_tasks[job_id]

        return job

    async def pause_job(self, job_id: str) -> Job:
        """Pause a crawl job (using SIGSTOP)."""
        job = self._jobs.get(job_id)
        if job is None:
            msg = f"Job '{job_id}' not found"
            raise ValueError(msg)

        if job.type != "crawl":
            msg = "Only crawl jobs can be paused"
            raise ValueError(msg)

        if job.status != JobStatus.RUNNING:
            msg = f"Job '{job_id}' is not running"
            raise ValueError(msg)

        process = self._processes.get(job_id)
        if process:
            os.killpg(os.getpgid(process.pid), signal.SIGSTOP)

        job.status = JobStatus.PAUSED
        self._persist_jobs()
        return job

    async def resume_job(self, job_id: str) -> Job:
        """Resume a paused crawl job."""
        job = self._jobs.get(job_id)
        if job is None:
            msg = f"Job '{job_id}' not found"
            raise ValueError(msg)

        if job.status != JobStatus.PAUSED:
            msg = f"Job '{job_id}' is not paused"
            raise ValueError(msg)

        process = self._processes.get(job_id)
        if process:
            os.killpg(os.getpgid(process.pid), signal.SIGCONT)

        job.status = JobStatus.RUNNING
        self._persist_jobs()
        return job

    def get_progress(self, job_id: str) -> JobProgress | None:
        """Get current progress for a job."""
        job = self._jobs.get(job_id)
        if job is None:
            return None

        if job.stats_file and Path(job.stats_file).exists():
            try:
                with Path(job.stats_file).open("r", encoding="utf-8") as f:
                    stats = json.load(f)
                return JobProgress(
                    pages_crawled=stats.get("pages_crawled", 0),
                    pages_pending=stats.get("pages_pending", 0),
                    requests_made=stats.get("requests_made", 0),
                    pages_per_min=stats.get("pages_per_min", 0.0),
                    current_url=stats.get("current_url"),
                    timestamp=datetime.fromisoformat(stats["timestamp"])
                    if "timestamp" in stats
                    else None,
                )
            except Exception:
                pass

        return job.progress

    async def _monitor_job(self, job_id: str) -> None:
        """Monitor a job and update its status when it completes."""
        job = self._jobs.get(job_id)
        process = self._processes.get(job_id)

        if not job or not process:
            return

        while True:
            await asyncio.sleep(1)

            return_code = process.poll()

            progress = self.get_progress(job_id)
            if progress:
                job.progress = progress

            if return_code is not None:
                if return_code == 0:
                    job.status = JobStatus.COMPLETED
                else:
                    job.status = JobStatus.FAILED
                    job.error = f"Process exited with code {return_code}"

                job.finished_at = datetime.now(UTC)
                self._persist_jobs()

                if job_id in self._processes:
                    del self._processes[job_id]

                config_store.delete_config(job.type, f"__job_{job_id}")
                break

    async def cleanup(self) -> None:
        """Cleanup resources on shutdown."""
        for task in self._progress_tasks.values():
            task.cancel()

        for job_id in list(self._processes.keys()):
            try:
                await self.stop_job(job_id)
            except Exception as e:
                logger.warning(f"Failed to stop job {job_id}: {e}")


job_manager = JobManager()
