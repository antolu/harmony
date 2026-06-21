from __future__ import annotations

import contextlib
import dataclasses
import logging
import os
import signal
import typing
from datetime import datetime

import pydantic

from harmony.api.models.job import Job, JobProgress, JobStatus, JobType
from harmony.db.connection import get_async_pool
from harmony.db.repositories import JobData, JobsRepo

logger = logging.getLogger(__name__)


def to_job_data(job: Job) -> JobData:
    return JobData(
        id=job.id,
        type=job.type,
        status=job.status,
        config_name=job.config_name,
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
        pid=job.pid,
        log_file=job.log_file,
        error=job.error,
    )


class JobPersistenceManager:
    async def load_persisted_jobs(self) -> dict[str, Job]:
        pool = await get_async_pool()
        rows = await JobsRepo(pool).load_all()
        jobs = {}
        for row in rows:
            row_dict = typing.cast(
                dict[str, pydantic.JsonValue], dataclasses.asdict(row)
            )
            job = Job(
                id=str(row_dict["id"]),
                type=typing.cast(JobType, row_dict["type"]),
                status=JobStatus(str(row_dict["status"])),
                config_name=str(row_dict.get("config_name", "")),
                started_at=typing.cast(datetime | None, row_dict.get("started_at")),
                finished_at=typing.cast(datetime | None, row_dict.get("finished_at")),
                pid=typing.cast(int | None, row_dict.get("pid")),
                log_file=str(row_dict["log_file"])
                if row_dict.get("log_file")
                else None,
                error=str(row_dict["error"]) if row_dict.get("error") else None,
                progress=JobProgress(
                    pages_crawled=typing.cast(
                        int, row_dict.get("progress_pages_crawled", 0)
                    ),
                    pages_pending=typing.cast(
                        int, row_dict.get("progress_pages_pending", 0)
                    ),
                    requests_made=typing.cast(
                        int, row_dict.get("progress_requests_made", 0)
                    ),
                    pages_per_min=typing.cast(
                        float, row_dict.get("progress_pages_per_min", 0.0)
                    ),
                    current_url=str(row_dict["progress_current_url"])
                    if row_dict.get("progress_current_url")
                    else None,
                    documents_indexed=typing.cast(
                        int, row_dict.get("progress_documents_indexed", 0)
                    ),
                    total_documents=typing.cast(
                        int, row_dict.get("progress_total_documents", 0)
                    ),
                    current_phase=str(row_dict["progress_current_phase"])
                    if row_dict.get("progress_current_phase")
                    else None,
                    timestamp=typing.cast(
                        datetime | None, row_dict.get("progress_timestamp")
                    ),
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
            jobs[job.id] = job
        logger.info(f"Loaded {len(jobs)} jobs from database")
        return jobs

    async def list_jobs(
        self,
        job_type: JobType | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[Job]:
        pool = await get_async_pool()
        rows = await JobsRepo(pool).load_all()
        jobs = []
        for r in rows:
            r_dict = typing.cast(dict[str, pydantic.JsonValue], dataclasses.asdict(r))
            jobs.append(
                Job(
                    id=str(r_dict["id"]),
                    type=typing.cast(JobType, r_dict["type"]),
                    status=JobStatus(str(r_dict["status"])),
                    config_name=str(r_dict.get("config_name", "")),
                    started_at=typing.cast(datetime | None, r_dict.get("started_at")),
                    finished_at=typing.cast(datetime | None, r_dict.get("finished_at")),
                    pid=typing.cast(int | None, r_dict.get("pid")),
                    log_file=str(r_dict["log_file"])
                    if r_dict.get("log_file")
                    else None,
                    error=str(r_dict["error"]) if r_dict.get("error") else None,
                    progress=JobProgress(
                        pages_crawled=typing.cast(
                            int, r_dict.get("progress_pages_crawled", 0)
                        ),
                        pages_pending=typing.cast(
                            int, r_dict.get("progress_pages_pending", 0)
                        ),
                        requests_made=typing.cast(
                            int, r_dict.get("progress_requests_made", 0)
                        ),
                        pages_per_min=typing.cast(
                            float, r_dict.get("progress_pages_per_min", 0.0)
                        ),
                        current_url=str(r_dict["progress_current_url"])
                        if r_dict.get("progress_current_url")
                        else None,
                        documents_indexed=typing.cast(
                            int, r_dict.get("progress_documents_indexed", 0)
                        ),
                        total_documents=typing.cast(
                            int, r_dict.get("progress_total_documents", 0)
                        ),
                        current_phase=str(r_dict["progress_current_phase"])
                        if r_dict.get("progress_current_phase")
                        else None,
                        timestamp=typing.cast(
                            datetime | None, r_dict.get("progress_timestamp")
                        ),
                    ),
                )
            )

        if job_type:
            jobs = [j for j in jobs if j.type == job_type]
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs[:limit]
