from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import typing
from datetime import UTC, datetime

import pydantic
import redis.asyncio.client

from harmony.api.models.job import Job, JobProgress, JobStatus
from harmony.api.services.admin._config_store import config_store
from harmony.db.connection import get_async_pool
from harmony.db.redis_client import get_async_redis
from harmony.db.repositories import JobLogsRepo, JobsRepo

if typing.TYPE_CHECKING:
    from harmony.api.services.admin._model_settings import ModelSettingsStore
    from harmony.api.services.admin._webhook_service import WebhookService

logger = logging.getLogger(__name__)

_STATS_CHANNEL_PREFIX = "crawl-stats:"


class JobLogStreamManager:
    def __init__(
        self,
        jobs: dict[str, Job],
        processes: dict[str, subprocess.Popen[str]],
        job_logs_repo: JobLogsRepo | None,
        webhook_service: WebhookService | None,
        model_settings_store: ModelSettingsStore | None,
    ) -> None:
        self._jobs = jobs
        self._processes = processes
        self._job_logs_repo = job_logs_repo
        self._webhook_service = webhook_service
        self._model_settings_store = model_settings_store

    async def monitor_job(self, job_id: str) -> None:
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
        pubsub: redis.asyncio.client.PubSub,
    ) -> None:
        while True:
            return_code = process.poll()
            message = await self._get_pubsub_message(pubsub)

            if message and message.get("data"):
                data_str = str(message["data"])
                await self._handle_pubsub_message(job_id, job, data_str)

            if return_code is not None:
                await self._finalize_job(job_id, job, return_code)
                break

    async def _handle_pubsub_message(self, job_id: str, job: Job, data: str) -> None:
        self._apply_stats_message(job, data)
        if self._job_logs_repo is not None:
            await self._persist_log_event(job_id, job, data)

    @staticmethod
    def _update_progress_from_event(
        job: Job, event: dict[str, pydantic.JsonValue]
    ) -> None:
        if event.get("current_phase") == "indexing" and event.get("documents_indexed"):
            job.progress.documents_indexed = int(str(event["documents_indexed"]))

    async def _persist_log_event(self, job_id: str, job: Job, data: str) -> None:
        try:  # noqa: PLW0717
            event = json.loads(data)
            level = event.get("level", "info")
            message = event.get("message", data)
            if self._job_logs_repo:
                await self._job_logs_repo.append(job_id, level, message)
            self._update_progress_from_event(job, event)
        except Exception as e:
            logger.debug("failed to persist log event: %s", e)

    @staticmethod
    async def _get_pubsub_message(
        pubsub: redis.asyncio.client.PubSub,
    ) -> dict[str, pydantic.JsonValue] | None:
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
        await JobsRepo(pool).update_progress(job_id, job.progress)
        await JobsRepo(pool).update_status(
            job_id, str(job.status), job.finished_at, job.error
        )

        if self._webhook_service is not None:
            event = "job_complete" if return_code == 0 else "job_failed"
            payload: dict[str, pydantic.JsonValue] = {
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

    async def monitor_embed_job(self, job_id: str) -> None:
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
                    if self._model_settings_store is not None:
                        await self._model_settings_store.clear_embedding_changed()
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
                    payload: dict[str, pydantic.JsonValue] = {
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
