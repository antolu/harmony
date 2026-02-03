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
from harmony.db.connection import get_async_pool
from harmony.db.redis_client import get_async_redis
from harmony.db.repositories import JobsRepo

logger = logging.getLogger(__name__)

_STATS_KEY_PREFIX = "crawl-stats-latest:"
_STATS_CHANNEL_PREFIX = "crawl-stats:"


class JobManager:
    """Manages job lifecycle including subprocess management."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._job_log_path: Path | None = None
        self._progress_tasks: dict[str, asyncio.Task[None]] = {}

    async def initialize(self, job_log_path: Path) -> None:
        """Initialize the job manager."""
        self._job_log_path = job_log_path
        await self._load_persisted_jobs()

    @property
    def job_log_path(self) -> Path:
        if self._job_log_path is None:
            msg = "JobManager not initialized. Call initialize() first."
            raise RuntimeError(msg)
        return self._job_log_path

    async def _load_persisted_jobs(self) -> None:
        """Load jobs from PostgreSQL."""
        pool = await get_async_pool()
        rows = await JobsRepo(pool).load_all()
        for row in rows:
            job = Job(
                id=row["id"],
                type=row["type"],
                status=JobStatus(row["status"]),
                config_name=row["config_name"],
                started_at=row.get("started_at"),
                finished_at=row.get("finished_at"),
                pid=row.get("pid"),
                log_file=row.get("log_file"),
                error=row.get("error"),
                progress=JobProgress(
                    pages_crawled=row.get("progress_pages_crawled", 0),
                    pages_pending=row.get("progress_pages_pending", 0),
                    requests_made=row.get("progress_requests_made", 0),
                    pages_per_min=row.get("progress_pages_per_min", 0.0),
                    current_url=row.get("progress_current_url"),
                    timestamp=row.get("progress_timestamp"),
                ),
            )
            if job.status == JobStatus.RUNNING:
                job.status = JobStatus.STOPPED
                job.error = "Job stopped due to server restart"
                await JobsRepo(pool).update_status(
                    job.id, str(job.status), job.finished_at, job.error
                )
            self._jobs[job.id] = job
        logger.info(f"Loaded {len(self._jobs)} jobs from database")

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

        job = Job(
            id=job_id,
            type="crawl",
            config_name=config_name,
            log_file=str(log_file),
            started_at=datetime.now(UTC),
        )

        config_store.save_config("crawler", f"__job_{job_id}", config)

        cmd = [
            "harmony-crawl",
            "--config",
            str(config_store.get_config_path("crawler", f"__job_{job_id}")),
        ]

        if output_override:
            cmd.extend(["--crawler.output", output_override])

        env = {**os.environ, "HARMONY_CRAWL_JOB_ID": job_id}
        if "HARMONY_BACKEND_URL" not in env:
            env["HARMONY_BACKEND_URL"] = "http://localhost:8000"

        try:
            with log_file.open("w") as log_f:
                process = subprocess.Popen(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    text=True,
                    preexec_fn=os.setsid,  # noqa: PLW1509
                    env=env,
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
        pool = await get_async_pool()
        await JobsRepo(pool).upsert(job.model_dump(mode="json"))
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
        pool = await get_async_pool()
        await JobsRepo(pool).upsert(job.model_dump(mode="json"))
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
        pool = await get_async_pool()
        await JobsRepo(pool).update_status(job_id, str(job.status), job.finished_at)

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
        pool = await get_async_pool()
        await JobsRepo(pool).update_status(job_id, str(job.status))
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
        pool = await get_async_pool()
        await JobsRepo(pool).update_status(job_id, str(job.status))
        return job

    async def get_progress(self, job_id: str) -> JobProgress | None:
        """Get current progress for a job."""
        job = self._jobs.get(job_id)
        if job is None:
            return None

        try:
            redis = get_async_redis()
            key = f"{_STATS_KEY_PREFIX}{job_id}"
            data = await redis.hgetall(key)
            await redis.aclose()
            if data:
                return JobProgress(
                    pages_crawled=int(data.get("pages_crawled", 0)),
                    pages_pending=int(data.get("pages_pending", 0)),
                    requests_made=int(data.get("requests_made", 0)),
                    pages_per_min=float(data.get("pages_per_min", 0.0)),
                    current_url=data.get("current_url") or None,
                    timestamp=datetime.fromisoformat(data["timestamp"])
                    if data.get("timestamp")
                    else None,
                )
        except Exception:
            pass

        return job.progress

    async def _monitor_job(self, job_id: str) -> None:
        """Monitor a job: subscribe to Redis for stats, poll process for exit."""
        job = self._jobs.get(job_id)
        process = self._processes.get(job_id)

        if not job or not process:
            return

        redis = get_async_redis()
        channel = f"{_STATS_CHANNEL_PREFIX}{job_id}"
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)

        try:
            while True:
                return_code = process.poll()

                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True), timeout=1.0
                    )
                except TimeoutError:
                    message = None

                if message and message.get("data"):
                    try:
                        stats = json.loads(message["data"])
                        progress = JobProgress(
                            pages_crawled=stats.get("pages_crawled", 0),
                            pages_pending=stats.get("pages_pending", 0),
                            requests_made=stats.get("requests_made", 0),
                            pages_per_min=stats.get("pages_per_min", 0.0),
                            current_url=stats.get("current_url"),
                            timestamp=datetime.fromisoformat(stats["timestamp"])
                            if stats.get("timestamp")
                            else None,
                        )
                        job.progress = progress
                        pool = await get_async_pool()
                        await JobsRepo(pool).update_progress(job_id, stats)
                    except Exception as e:
                        logger.debug(f"Failed to parse stats message: {e}")

                if return_code is not None:
                    if return_code == 0:
                        job.status = JobStatus.COMPLETED
                    else:
                        job.status = JobStatus.FAILED
                        job.error = f"Process exited with code {return_code}"

                    job.finished_at = datetime.now(UTC)
                    pool = await get_async_pool()
                    await JobsRepo(pool).update_status(
                        job_id, str(job.status), job.finished_at, job.error
                    )

                    if job_id in self._processes:
                        del self._processes[job_id]

                    config_store.delete_config(
                        "crawler" if job.type == "crawl" else "indexer",
                        f"__job_{job_id}",
                    )
                    break
        finally:
            await pubsub.unsubscribe(channel)
            await redis.aclose()

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
