from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import subprocess
import typing
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg_pool
import pydantic
import redis.asyncio

from harmony.api.admin_config import settings as admin_settings
from harmony.db.redis_client import get_async_redis
from harmony.db.repositories import (
    IndexerCheckpointRepo,
    JobLogsRepo,
    JobsRepo,
)
from harmony.models import Job, JobProgress, JobStatus, JobType
from harmony.providers import ProviderJobSpec
from harmony.services.admin._config_store import ConfigStore
from harmony.services.admin._crawl_config import CrawlConfigService
from harmony.services.admin._indexer_config import IndexerConfigService
from harmony.services.admin._job_log_stream import JobLogStreamManager
from harmony.services.admin._job_persistence import (
    JobPersistenceManager,
    to_job_data,
)
from harmony.services.admin._model_settings import ModelSettingsStore
from harmony.services.admin._webhook_service import WebhookService
from harmony.services.admin.jobs import JobExecutor, SubprocessJobExecutor

logger = logging.getLogger(__name__)


def make_job_env(job_id: str) -> dict[str, str]:
    env = {**os.environ, "HARMONY_CRAWL_JOB_ID": job_id}
    env.setdefault("HARMONY_BACKEND_URL", "http://harmony-api:8000")
    env.setdefault(
        "SCRAPY_SETTINGS_MODULE", "harmony.providers.web_crawler.runtime.settings"
    )
    return env


class JobManager:  # noqa: PLR0904
    """Manages job lifecycle, delegating execution to an injected JobExecutor."""

    def __init__(
        self,
        pool: psycopg_pool.AsyncConnectionPool,
        config_store: ConfigStore,
        executor: JobExecutor | None = None,
        redis_client: redis.asyncio.Redis | None = None,
    ) -> None:
        self._jobs: dict[str, Job] = {}
        self._job_log_path: Path | None = None
        self._progress_tasks: dict[str, asyncio.Task[None]] = {}
        self._job_logs_repo: JobLogsRepo | None = None
        self._webhook_service: WebhookService | None = None
        self._crawl_config_service: CrawlConfigService | None = None
        self._indexer_config_service: IndexerConfigService | None = None
        self._model_settings_store: ModelSettingsStore | None = None

        self._config_store: ConfigStore = config_store
        self._executor: JobExecutor = executor or SubprocessJobExecutor()
        self._pool = pool
        self._redis: redis.asyncio.Redis | None = redis_client

        self._persistence_manager: JobPersistenceManager = JobPersistenceManager(pool)
        self._log_stream_manager: JobLogStreamManager = JobLogStreamManager(
            jobs=self._jobs,
            processes=self._subprocess_processes,
            config_store=config_store,
            pool=pool,
            executor=self._executor,
        )

    @property
    def _subprocess_processes(self) -> dict[str, subprocess.Popen[str]]:
        """Live subprocess map, empty for non-subprocess executors."""
        if isinstance(self._executor, SubprocessJobExecutor):
            return self._executor.processes
        return {}

    def set_webhook_service(self, webhook_service: WebhookService) -> None:
        self._webhook_service = webhook_service
        self._log_stream_manager.set_webhook_service(webhook_service)

    def set_config_services(
        self,
        crawl_config_service: CrawlConfigService,
        indexer_config_service: IndexerConfigService,
        model_settings_store: ModelSettingsStore,
    ) -> None:
        self._crawl_config_service = crawl_config_service
        self._indexer_config_service = indexer_config_service
        self._model_settings_store = model_settings_store
        self._log_stream_manager.set_model_settings_store(model_settings_store)

    async def initialize(self, job_log_path: Path) -> None:
        """Initialize the job manager."""
        self._job_log_path = job_log_path
        self._job_logs_repo = JobLogsRepo(self._pool)
        self._log_stream_manager.set_job_logs_repo(self._job_logs_repo)

        loaded_jobs = await self._persistence_manager.load_persisted_jobs()
        self._jobs.update(loaded_jobs)

    @property
    def job_log_path(self) -> Path:
        if self._job_log_path is None:
            msg = "JobManager not initialized. Call initialize() first."
            raise RuntimeError(msg)
        return self._job_log_path

    async def list_jobs(
        self,
        job_type: JobType | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[Job]:
        jobs = await self._persistence_manager.list_jobs(job_type, status, limit)
        for job in jobs:
            if job.status == JobStatus.RUNNING and job.id in self._jobs:
                progress = await self.get_progress(job.id)
                if progress:
                    job.progress = progress
        return jobs

    def get_job(self, job_id: str) -> Job | None:
        """Get a job by ID (local replica only; use get_job_async for cross-pod)."""
        return self._jobs.get(job_id)

    async def get_job_async(self, job_id: str) -> Job | None:
        """Get a job by ID, falling back to Postgres for jobs started on another replica."""
        job = self._jobs.get(job_id)
        if job is not None:
            return job
        return await self._persistence_manager.get_job(job_id)

    def _schedule_monitor(self, job_id: str) -> None:
        if isinstance(self._executor, SubprocessJobExecutor):
            coro = self._log_stream_manager.monitor_job(job_id)
        else:
            coro = self._log_stream_manager.monitor_k8s_job(job_id)
        self._progress_tasks[job_id] = asyncio.create_task(coro)

    async def _launch(
        self,
        job: Job,
        cmd: list[str],
        env: dict[str, str],
        on_started: typing.Callable[[], None],
    ) -> None:
        """Submit a job to the executor, preserving launch-failure semantics."""
        try:
            await self._executor.submit(job, cmd, env)
        except Exception as e:
            job.status = JobStatus.FAILED
            job.finished_at = datetime.now(UTC)
            job.error = str(e)
            if job.log_file:
                with contextlib.suppress(Exception):
                    Path(job.log_file).write_text(
                        f"Launch failed: {e}\n", encoding="utf-8"
                    )
            return
        job.status = JobStatus.RUNNING
        on_started()

    async def start_crawl_job(
        self,
        config_name: str,
        output_override: str | None = None,
    ) -> Job:
        """Start a crawl job."""
        if self._crawl_config_service is not None:
            config = await self._crawl_config_service.get(config_name)
        else:
            config = self._config_store.get_config("crawler", config_name)
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

        self._config_store.save_config("crawler", f"__job_{job_id}", config)

        base_output = admin_settings.crawler_output_path
        job_output = output_override or (
            str(base_output / job_id) if base_output else None
        )

        cmd = [
            "harmony-crawl",
            "--config",
            str(self._config_store.get_config_path("crawler", f"__job_{job_id}")),
        ]

        if job_output:
            cmd.extend(["--crawler.output", job_output])

        env = make_job_env(job_id)

        def on_started() -> None:
            self._schedule_monitor(job.id)

        await self._launch(job, cmd, env, on_started)
        self._jobs[job_id] = job
        pool = self._pool
        await JobsRepo(pool).upsert(to_job_data(job))
        return job

    async def start_index_job(self, config_name: str) -> Job:
        """Start an index job."""
        resolved_config: dict[str, pydantic.JsonValue] | None
        if self._indexer_config_service is not None:
            resolved_config = await self._indexer_config_service.get()
        else:
            resolved_config = self._config_store.get_config("indexer", config_name)
        if resolved_config is None:
            msg = f"Config '{config_name}' not found"
            raise ValueError(msg)
        config: dict[str, pydantic.JsonValue] = resolved_config

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
        data_dir = admin_settings.crawler_output_path
        if not data_dir:
            msg = "ADMIN_CRAWLER_OUTPUT_PATH is not set — cannot start index job"
            raise ValueError(msg)
        working_config = {
            **config,
            "source": "elasticsearch",
            "data_dir": str(data_dir),
        }
        if es_host and "es_host" not in working_config:
            working_config["es_host"] = es_host
        self._config_store.save_config("indexer", f"__job_{job_id}", working_config)

        qdrant_host = os.environ.get("QDRANT_HOST", "http://localhost:6333")
        cmd = [
            "harmony-index",
            "--config",
            str(self._config_store.get_config_path("indexer", f"__job_{job_id}")),
            f"--qdrant_host={qdrant_host}",
        ]

        env = make_job_env(job_id)

        def on_started() -> None:
            self._schedule_monitor(job.id)

        await self._launch(job, cmd, env, on_started)
        self._jobs[job_id] = job
        pool = self._pool
        await JobsRepo(pool).upsert(to_job_data(job))
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

        def on_started() -> None:
            self._progress_tasks[job.id] = asyncio.create_task(
                self._log_stream_manager.monitor_embed_job(job.id)
            )

        await self._launch(job, cmd, env, on_started)
        self._jobs[job_id] = job
        pool = self._pool
        await JobsRepo(pool).upsert(to_job_data(job))
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
        pool = self._pool
        await JobsRepo(pool).upsert(to_job_data(job))

        self._progress_tasks[job.id] = asyncio.create_task(
            self._run_specs_sequentially(job, specs, log_file)
        )

        return job

    async def _run_specs_sequentially(
        self, job: Job, specs: list[ProviderJobSpec], log_file: Path
    ) -> None:
        job.status = JobStatus.RUNNING
        pool = self._pool
        await JobsRepo(pool).update_status(job.id, str(job.status))

        for i, spec in enumerate(specs):
            cmd = [spec.entrypoint, *spec.args]
            env = {**make_job_env(job.id), **spec.env}

            try:
                if isinstance(self._executor, SubprocessJobExecutor):
                    await self._executor.submit(job, cmd, env, append_log=i > 0)
                else:
                    await self._executor.submit(job, cmd, env)
                return_code = await self._executor.wait(job.id)
            except Exception as e:
                job.status = JobStatus.FAILED
                job.error = str(e)
                job.finished_at = datetime.now(UTC)
                await JobsRepo(pool).update_status(
                    job.id, str(job.status), job.finished_at, job.error
                )
                return

            if return_code is not None and return_code != 0:
                job.status = JobStatus.FAILED
                job.error = f"Spec '{spec.entrypoint}' exited with code {return_code}"
                job.finished_at = datetime.now(UTC)
                await JobsRepo(pool).update_status(
                    job.id, str(job.status), job.finished_at, job.error
                )
                return

        job.status = JobStatus.COMPLETED
        job.finished_at = datetime.now(UTC)
        await JobsRepo(pool).update_status(job.id, str(job.status), job.finished_at)

    async def stop_job(self, job_id: str, *, force: bool = False) -> Job:
        """Stop a running job."""
        job = await self.get_job_async(job_id)
        if job is None:
            msg = f"Job '{job_id}' not found"
            raise ValueError(msg)

        if job.status != JobStatus.RUNNING:
            msg = f"Job '{job_id}' is not running"
            raise ValueError(msg)

        with contextlib.suppress(ProcessLookupError):
            await self._executor.cancel(job, force=force)

        job.status = JobStatus.STOPPED
        job.finished_at = datetime.now(UTC)
        pool = self._pool

        progress = await self.get_progress(job_id)
        if progress:
            await JobsRepo(pool).update_progress(job_id, progress)

        await JobsRepo(pool).update_status(job_id, str(job.status), job.finished_at)

        if job_id in self._progress_tasks:
            self._progress_tasks[job_id].cancel()
            del self._progress_tasks[job_id]

        return job

    async def pause_job(self, job_id: str) -> Job:
        """Pause a crawl job (using SIGSTOP)."""
        job = await self.get_job_async(job_id)
        if job is None:
            msg = f"Job '{job_id}' not found"
            raise ValueError(msg)

        if job.type != "crawl":
            msg = "Only crawl jobs can be paused"
            raise ValueError(msg)

        if job.status != JobStatus.RUNNING:
            msg = f"Job '{job_id}' is not running"
            raise ValueError(msg)

        self._executor.pause(job)

        job.status = JobStatus.PAUSED
        pool = self._pool
        await JobsRepo(pool).update_status(job_id, str(job.status))
        return job

    async def resume_job(self, job_id: str) -> Job:
        """Resume a paused crawl job."""
        job = await self.get_job_async(job_id)
        if job is None:
            msg = f"Job '{job_id}' not found"
            raise ValueError(msg)

        if job.status != JobStatus.PAUSED:
            msg = f"Job '{job_id}' is not paused"
            raise ValueError(msg)

        self._executor.resume(job)

        job.status = JobStatus.RUNNING
        pool = self._pool
        await JobsRepo(pool).update_status(job_id, str(job.status))
        return job

    async def get_progress(self, job_id: str) -> typing.Any | None:
        """Get current progress for a job."""
        job = self._jobs.get(job_id)
        if job is None:
            return None

        try:
            raw = await self._fetch_redis_progress(job_id)
        except Exception:
            raw = None

        if raw:
            return JobProgress.model_validate(raw)
        return job.progress

    async def _fetch_redis_progress(self, job_id: str) -> dict[str, typing.Any] | None:
        r = self._redis or await get_async_redis()
        try:
            raw = await r.hgetall(f"crawl-stats-latest:{job_id}")
        finally:
            if self._redis is None:
                await r.aclose()
        if not raw:
            return None
        return {
            (k.decode() if isinstance(k, bytes) else k): (
                v.decode() if isinstance(v, bytes) else v
            )
            for k, v in raw.items()
        }

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job (SIGTERM). Returns True if killed, False if not found/not running."""
        job = await self.get_job_async(job_id)
        if job is None or job.status != JobStatus.RUNNING:
            return False

        with contextlib.suppress(ProcessLookupError):
            await self._executor.cancel(job)

        job.status = JobStatus.CANCELLED
        job.finished_at = datetime.now(UTC)
        pool = self._pool
        await JobsRepo(pool).update_status(job_id, str(job.status), job.finished_at)

        if job_id in self._progress_tasks:
            self._progress_tasks[job_id].cancel()
            del self._progress_tasks[job_id]

        owned = self._redis is None
        r = self._redis or await get_async_redis()
        try:
            await r.publish(f"job-status:{job_id}", json.dumps({"status": "cancelled"}))
        except Exception:
            pass
        finally:
            if owned:
                await r.aclose()

        return True

    async def retrigger_job(self, job_id: str, created_by: str) -> Job:
        """Create a new job with the same config as an existing job."""
        job = await self.get_job_async(job_id)
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
        pool = self._pool
        await IndexerCheckpointRepo(pool).clear(config_name)
        if job_type == "crawl":
            return await self.start_crawl_job(config_name=config_name)
        if job_type in {"index", "crawl+index"}:
            return await self.start_index_job(config_name=config_name)
        msg = f"Unknown job type '{job_type}'"
        raise ValueError(msg)

    async def clear_checkpoint(self, job_id: str, config_name: str) -> int:
        """Clear indexer checkpoint for a config (Start fresh support)."""
        pool = self._pool
        return await IndexerCheckpointRepo(pool).clear(config_name)

    async def cleanup(self) -> None:
        """Cleanup resources on shutdown."""
        for task in self._progress_tasks.values():
            task.cancel()

        for job_id in list(self._subprocess_processes.keys()):
            try:
                await self.stop_job(job_id)
            except Exception as e:
                logger.warning(f"Failed to stop job {job_id}: {e}")
