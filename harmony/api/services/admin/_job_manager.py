from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import signal
import subprocess
import typing
import uuid
from datetime import UTC, datetime
from pathlib import Path

if typing.TYPE_CHECKING:
    from harmony.api.services.admin._crawl_config import CrawlConfigService
    from harmony.api.services.admin._indexer_config import IndexerConfigService
    from harmony.api.services.admin._webhook_service import WebhookService
    from harmony.providers import ProviderJobSpec

from harmony.api.models.job import Job, JobProgress, JobStatus, JobType
from harmony.api.services.admin._config_store import config_store
from harmony.api.services.admin._model_settings import model_settings_store
from harmony.db.connection import get_async_pool
from harmony.db.redis_client import get_async_redis
from harmony.db.repositories import IndexerCheckpointRepo, JobLogsRepo, JobsRepo

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
        self._job_logs_repo: JobLogsRepo | None = None
        self._webhook_service: WebhookService | None = None
        self._crawl_config_service: CrawlConfigService | None = None
        self._indexer_config_service: IndexerConfigService | None = None

    def set_webhook_service(self, webhook_service: WebhookService) -> None:
        self._webhook_service = webhook_service

    def set_config_services(
        self,
        crawl_config_service: CrawlConfigService,
        indexer_config_service: IndexerConfigService,
    ) -> None:
        self._crawl_config_service = crawl_config_service
        self._indexer_config_service = indexer_config_service

    async def initialize(self, job_log_path: Path) -> None:
        """Initialize the job manager."""
        self._job_log_path = job_log_path
        pool = await get_async_pool()
        self._job_logs_repo = JobLogsRepo(pool)
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
                    documents_indexed=row.get("progress_documents_indexed", 0),
                    total_documents=row.get("progress_total_documents", 0),
                    current_phase=row.get("progress_current_phase"),
                    timestamp=row.get("progress_timestamp"),
                ),
            )
            if job.status == JobStatus.RUNNING:
                if job.pid:
                    with contextlib.suppress(ProcessLookupError, PermissionError):
                        os.killpg(os.getpgid(job.pid), signal.SIGTERM)
                job.status = JobStatus.INTERRUPTED
                job.error = "Job interrupted by server restart or crash"
                await JobsRepo(pool).update_status(
                    job.id, str(job.status), job.finished_at, job.error
                )
            self._jobs[job.id] = job
        logger.info(f"Loaded {len(self._jobs)} jobs from database")

    async def list_jobs(
        self,
        job_type: JobType | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[Job]:
        pool = await get_async_pool()
        rows = await JobsRepo(pool).load_all()
        jobs = [
            Job(
                id=r["id"],
                type=r["type"],
                status=JobStatus(r["status"]),
                config_name=r["config_name"],
                started_at=r.get("started_at"),
                finished_at=r.get("finished_at"),
                pid=r.get("pid"),
                log_file=r.get("log_file"),
                error=r.get("error"),
                progress=JobProgress(
                    pages_crawled=r.get("progress_pages_crawled", 0),
                    pages_pending=r.get("progress_pages_pending", 0),
                    requests_made=r.get("progress_requests_made", 0),
                    pages_per_min=r.get("progress_pages_per_min", 0.0),
                    current_url=r.get("progress_current_url"),
                    documents_indexed=r.get("progress_documents_indexed", 0),
                    total_documents=r.get("progress_total_documents", 0),
                    current_phase=r.get("progress_current_phase"),
                    timestamp=r.get("progress_timestamp"),
                ),
            )
            for r in rows
        ]

        for job in jobs:
            if job.status == JobStatus.RUNNING and job.id in self._jobs:
                progress = await self.get_progress(job.id)
                if progress:
                    job.progress = progress

        if job_type:
            jobs = [j for j in jobs if j.type == job_type]
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs[:limit]

    def get_job(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    @staticmethod
    def _make_env(job_id: str) -> dict[str, str]:
        env = {**os.environ, "HARMONY_CRAWL_JOB_ID": job_id}
        env.setdefault("HARMONY_BACKEND_URL", "http://harmony-api:8000")
        env.setdefault("SCRAPY_SETTINGS_MODULE", "harmony.crawler.settings")
        return env

    def _launch_process(
        self,
        job: Job,
        cmd: list[str],
        log_file: Path,
        env: dict[str, str],
        monitor: typing.Callable[[str], typing.Coroutine[typing.Any, typing.Any, None]],
    ) -> None:
        try:
            self._start_process(job, cmd, log_file, env, monitor)
        except Exception as e:
            job.status = JobStatus.FAILED
            job.finished_at = datetime.now(UTC)
            job.error = str(e)
            with contextlib.suppress(Exception):
                log_file.write_text(f"Launch failed: {e}\n", encoding="utf-8")

    def _start_process(
        self,
        job: Job,
        cmd: list[str],
        log_file: Path,
        env: dict[str, str],
        monitor: typing.Callable[[str], typing.Coroutine[typing.Any, typing.Any, None]],
    ) -> None:
        with log_file.open("w", encoding="utf-8") as log_f:
            process = subprocess.Popen(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                text=True,
                preexec_fn=os.setsid,  # noqa: PLW1509
                env=env,
            )
        self._processes[job.id] = process
        job.pid = process.pid
        job.status = JobStatus.RUNNING
        self._progress_tasks[job.id] = asyncio.create_task(monitor(job.id))

    async def start_crawl_job(
        self,
        config_name: str,
        output_override: str | None = None,
    ) -> Job:
        """Start a crawl job."""
        if self._crawl_config_service is not None:
            config = await self._crawl_config_service.get(config_name)
        else:
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

        base_output = os.environ.get("ADMIN_CRAWLER_OUTPUT_PATH")
        job_output = output_override or (
            str(Path(base_output) / job_id) if base_output else None
        )

        cmd = [
            "harmony-crawl",
            "--config",
            str(config_store.get_config_path("crawler", f"__job_{job_id}")),
        ]

        if job_output:
            cmd.extend(["--crawler.output", job_output])

        env = self._make_env(job_id)

        self._launch_process(job, cmd, log_file, env, self._monitor_job)
        self._jobs[job_id] = job
        pool = await get_async_pool()
        await JobsRepo(pool).upsert(job.model_dump(mode="json"))
        return job

    async def start_index_job(self, config_name: str) -> Job:
        """Start an index job."""
        resolved_config: dict[str, typing.Any] | None
        if self._indexer_config_service is not None:
            resolved_config = await self._indexer_config_service.get()
        else:
            resolved_config = config_store.get_config("indexer", config_name)
        if resolved_config is None:
            msg = f"Config '{config_name}' not found"
            raise ValueError(msg)
        config: dict[str, typing.Any] = resolved_config

        job_id = str(uuid.uuid4())[:8]
        log_file = self.job_log_path / f"index-{job_id}.log"

        job = Job(
            id=job_id,
            type="index",
            config_name=config_name,
            log_file=str(log_file),
            started_at=datetime.now(UTC),
        )

        es_host = os.environ.get("ES_HOST", "http://localhost:9200")
        data_dir = os.environ.get("ADMIN_CRAWLER_OUTPUT_PATH")
        if not data_dir:
            msg = "ADMIN_CRAWLER_OUTPUT_PATH is not set — cannot start index job"
            raise ValueError(msg)
        working_config = {**config, "source": "elasticsearch", "data_dir": data_dir}
        if es_host and "es_host" not in working_config:
            working_config["es_host"] = es_host
        config_store.save_config("indexer", f"__job_{job_id}", working_config)

        qdrant_host = os.environ.get("QDRANT_HOST", "http://localhost:6333")
        cmd = [
            "harmony-index",
            "--config",
            str(config_store.get_config_path("indexer", f"__job_{job_id}")),
            f"--qdrant_host={qdrant_host}",
        ]

        env = self._make_env(job_id)

        self._launch_process(job, cmd, log_file, env, self._monitor_job)
        self._jobs[job_id] = job
        pool = await get_async_pool()
        await JobsRepo(pool).upsert(job.model_dump(mode="json"))
        return job

    async def start_embed_job(self, *, embedding_model: str) -> Job:
        """Start an embed job using harmony-embed CLI."""
        job_id = str(uuid.uuid4())[:8]
        log_file = self.job_log_path / f"embed-{job_id}.log"

        job = Job(
            id=job_id,
            type="embed",
            config_name=f"embed-{embedding_model}",
            log_file=str(log_file),
            started_at=datetime.now(UTC),
        )

        qdrant_host = os.environ.get("QDRANT_HOST", "http://localhost:6333")
        cmd = [
            "harmony-embed",
            f"--embedder.embedding-model={embedding_model}",
            f"--embedder.qdrant-host={qdrant_host}",
        ]

        env = {**os.environ}

        self._launch_process(job, cmd, log_file, env, self._monitor_embed_job)
        self._jobs[job_id] = job
        pool = await get_async_pool()
        await JobsRepo(pool).upsert(job.model_dump(mode="json"))
        return job

    async def start_from_specs(
        self, specs: list[ProviderJobSpec], data_source_id: str
    ) -> Job:
        """Start a job that executes a sequence of provider job specs."""
        job_id = str(uuid.uuid4())[:8]
        log_file = self.job_log_path / f"ingest-{job_id}.log"

        job = Job(
            id=job_id,
            type="ingest",
            config_name=data_source_id,
            log_file=str(log_file),
            started_at=datetime.now(UTC),
        )

        self._jobs[job_id] = job
        pool = await get_async_pool()
        await JobsRepo(pool).upsert(job.model_dump(mode="json"))

        self._progress_tasks[job.id] = asyncio.create_task(
            self._run_specs_sequentially(job, specs, log_file)
        )

        return job

    async def _run_specs_sequentially(
        self, job: Job, specs: list[ProviderJobSpec], log_file: Path
    ) -> None:
        job.status = JobStatus.RUNNING
        pool = await get_async_pool()
        await JobsRepo(pool).update_status(job.id, str(job.status))

        for i, spec in enumerate(specs):
            cmd = [spec.entrypoint, *spec.args]
            env = {**self._make_env(job.id), **spec.env}
            mode = "w" if i == 0 else "a"

            try:
                with log_file.open(mode, encoding="utf-8") as log_f:
                    process = subprocess.Popen(
                        cmd,
                        stdout=log_f,
                        stderr=subprocess.STDOUT,
                        text=True,
                        preexec_fn=os.setsid,  # noqa: PLW1509
                        env=env,
                    )
                self._processes[job.id] = process
                job.pid = process.pid
                return_code = await asyncio.to_thread(process.wait)
            except Exception as e:
                job.status = JobStatus.FAILED
                job.error = str(e)
                job.finished_at = datetime.now(UTC)
                await JobsRepo(pool).update_status(
                    job.id, str(job.status), job.finished_at, job.error
                )
                if job.id in self._processes:
                    del self._processes[job.id]
                return

            if return_code != 0:
                job.status = JobStatus.FAILED
                job.error = f"Spec '{spec.entrypoint}' exited with code {return_code}"
                job.finished_at = datetime.now(UTC)
                await JobsRepo(pool).update_status(
                    job.id, str(job.status), job.finished_at, job.error
                )
                if job.id in self._processes:
                    del self._processes[job.id]
                return

        job.status = JobStatus.COMPLETED
        job.finished_at = datetime.now(UTC)
        await JobsRepo(pool).update_status(job.id, str(job.status), job.finished_at)
        if job.id in self._processes:
            del self._processes[job.id]

    async def _monitor_embed_job(self, job_id: str) -> None:
        """Monitor an embed job: poll process for exit, clear changed flag on success."""

        job = self._jobs.get(job_id)
        process = self._processes.get(job_id)

        if not job or not process:
            return

        while True:
            await asyncio.sleep(1.0)
            return_code = process.poll()
            if return_code is not None:
                if return_code == 0:
                    job.status = JobStatus.COMPLETED
                    await model_settings_store.clear_embedding_changed()
                else:
                    job.status = JobStatus.FAILED
                    job.error = f"Process exited with code {return_code}"

                job.finished_at = datetime.now(UTC)
                pool = await get_async_pool()
                await JobsRepo(pool).update_status(
                    job_id, str(job.status), job.finished_at, job.error
                )

                if self._webhook_service is not None:
                    event = "job_complete" if return_code == 0 else "job_failed"
                    payload = {
                        "job_id": job_id,
                        "type": "embed",
                        "config_name": job.config_name,
                        "status": str(job.status),
                        "finished_at": job.finished_at.isoformat()
                        if job.finished_at
                        else None,
                        "error": job.error,
                    }
                    t = asyncio.create_task(
                        self._webhook_service.fire_event(event, payload)
                    )
                    t.add_done_callback(
                        lambda t: t.exception() if not t.cancelled() else None
                    )

                if job_id in self._processes:
                    del self._processes[job_id]
                break

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
            with contextlib.suppress(ProcessLookupError):
                self._terminate_process(process, force=force)

            del self._processes[job_id]

        job.status = JobStatus.STOPPED
        job.finished_at = datetime.now(UTC)
        pool = await get_async_pool()

        progress = await self.get_progress(job_id)
        if progress:
            await JobsRepo(pool).update_progress(
                job_id, progress.model_dump(mode="json")
            )

        await JobsRepo(pool).update_status(job_id, str(job.status), job.finished_at)

        if job_id in self._progress_tasks:
            self._progress_tasks[job_id].cancel()
            del self._progress_tasks[job_id]

        return job

    @staticmethod
    def _terminate_process(process: subprocess.Popen[str], *, force: bool) -> None:
        if force:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)

        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            process.wait()

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
            redis = await get_async_redis()
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
                    documents_indexed=int(data.get("documents_indexed", 0)),
                    total_documents=int(data.get("total_documents", 0)),
                    current_phase=data.get("current_phase") or None,
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

        redis = await get_async_redis()
        channel = f"{_STATS_CHANNEL_PREFIX}{job_id}"
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)

        try:
            await self._run_monitor_loop(job_id, job, process, pubsub)
        finally:
            await pubsub.unsubscribe(channel)
            await redis.aclose()

    async def _run_monitor_loop(
        self,
        job_id: str,
        job: Job,
        process: subprocess.Popen[str],
        pubsub: typing.Any,
    ) -> None:
        while True:
            return_code = process.poll()
            message = await self._get_pubsub_message(pubsub)

            if message and message.get("data"):
                await self._handle_pubsub_message(job_id, job, message["data"])

            if return_code is not None:
                await self._finalize_job(job_id, job, return_code)
                break

    async def _handle_pubsub_message(self, job_id: str, job: Job, data: str) -> None:
        self._apply_stats_message(job, data)
        if self._job_logs_repo is not None:
            await self._persist_log_event(job_id, job, data)

    @staticmethod
    def _update_progress_from_event(job: Job, event: dict[str, typing.Any]) -> None:
        if event.get("current_phase") == "indexing" and event.get("documents_indexed"):
            job.progress.documents_indexed = int(event["documents_indexed"])

    async def _persist_log_event(self, job_id: str, job: Job, data: str) -> None:
        try:
            event = json.loads(data)
            level = event.get("level", "info")
            message = event.get("message", data)
            await self._job_logs_repo.append(job_id, level, message)  # type: ignore[union-attr]
            self._update_progress_from_event(job, event)
        except Exception as e:
            logger.debug("failed to persist log event: %s", e)

    @staticmethod
    async def _get_pubsub_message(pubsub: typing.Any) -> dict[str, typing.Any] | None:
        try:
            return await asyncio.wait_for(
                pubsub.get_message(ignore_subscribe_messages=True), timeout=1.0
            )
        except TimeoutError:
            return None

    @staticmethod
    def _apply_stats_message(job: Job, data: str) -> None:
        try:
            stats = json.loads(data)
            job.progress = JobProgress(
                pages_crawled=stats.get("pages_crawled", 0),
                pages_pending=stats.get("pages_pending", 0),
                requests_made=stats.get("requests_made", 0),
                pages_per_min=stats.get("pages_per_min", 0.0),
                current_url=stats.get("current_url"),
                documents_indexed=stats.get("documents_indexed", 0),
                total_documents=stats.get("total_documents", 0),
                current_phase=stats.get("current_phase"),
                timestamp=datetime.fromisoformat(stats["timestamp"])
                if stats.get("timestamp")
                else None,
            )
        except Exception as e:
            logger.debug(f"Failed to parse stats message: {e}")

    async def _finalize_job(self, job_id: str, job: Job, return_code: int) -> None:
        if return_code == 0:
            job.status = JobStatus.COMPLETED
        else:
            job.status = JobStatus.FAILED
            job.error = f"Process exited with code {return_code}"

        job.finished_at = datetime.now(UTC)
        pool = await get_async_pool()
        await JobsRepo(pool).update_progress(
            job_id, job.progress.model_dump(mode="json")
        )
        await JobsRepo(pool).update_status(
            job_id, str(job.status), job.finished_at, job.error
        )

        if self._webhook_service is not None:
            event = "job_complete" if return_code == 0 else "job_failed"
            payload = {
                "job_id": job_id,
                "type": job.type,
                "config_name": job.config_name,
                "status": str(job.status),
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                "error": job.error,
            }
            t = asyncio.create_task(self._webhook_service.fire_event(event, payload))
            t.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

        if job_id in self._processes:
            del self._processes[job_id]

        config_store.delete_config(
            "crawler" if job.type == "crawl" else "indexer",
            f"__job_{job_id}",
        )

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job (SIGTERM). Returns True if killed, False if not found/not running."""
        job = self._jobs.get(job_id)
        if job is None or job.status != JobStatus.RUNNING:
            return False

        process = self._processes.get(job_id)
        if process:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            del self._processes[job_id]

        job.status = JobStatus.CANCELLED
        job.finished_at = datetime.now(UTC)
        pool = await get_async_pool()
        await JobsRepo(pool).update_status(job_id, str(job.status), job.finished_at)

        if job_id in self._progress_tasks:
            self._progress_tasks[job_id].cancel()
            del self._progress_tasks[job_id]

        redis = await get_async_redis()
        try:
            await redis.publish(
                f"job-status:{job_id}", json.dumps({"status": "cancelled"})
            )
        except Exception:
            pass
        finally:
            await redis.aclose()

        return True

    async def retrigger_job(self, job_id: str, created_by: str) -> Job:
        """Create a new job with the same config as an existing job."""
        job = self._jobs.get(job_id)
        if job is None:
            msg = f"Job '{job_id}' not found"
            raise ValueError(msg)

        if job.type == "crawl":
            return await self.start_crawl_job(config_name=job.config_name)
        if job.type == "index":
            return await self.start_index_job(config_name=job.config_name)
        msg = f"Cannot retrigger job type '{job.type}'"
        raise ValueError(msg)

    async def start_job_fresh(
        self, config_name: str, job_type: str, created_by: str
    ) -> Job:
        """Clear checkpoint for config then start a new job."""
        pool = await get_async_pool()
        await IndexerCheckpointRepo(pool).clear(config_name)
        if job_type == "crawl":
            return await self.start_crawl_job(config_name=config_name)
        if job_type in {"index", "crawl+index"}:
            return await self.start_index_job(config_name=config_name)
        msg = f"Unknown job type '{job_type}'"
        raise ValueError(msg)

    async def clear_checkpoint(self, job_id: str, config_name: str) -> int:
        """Clear indexer checkpoint for a config (Start fresh support)."""
        pool = await get_async_pool()
        return await IndexerCheckpointRepo(pool).clear(config_name)

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
