from __future__ import annotations

import typing
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

JobType = typing.Literal["crawl", "index", "embed", "ingest"]


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"


class JobProgress(BaseModel):
    pages_crawled: int = 0
    pages_pending: int = 0
    requests_made: int = 0
    pages_per_min: float = 0.0
    current_url: str | None = None
    documents_indexed: int = 0
    total_documents: int = 0
    current_phase: str | None = None
    timestamp: datetime | None = None


class Job(BaseModel):
    id: str
    type: JobType
    status: JobStatus = JobStatus.PENDING
    config_name: str
    progress: JobProgress = Field(default_factory=JobProgress)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    pid: int | None = None
    log_file: str | None = None


class JobStartRequest(BaseModel):
    config_name: str = Field(..., description="Name of saved config to use")
    output_override: str | None = Field(
        None, description="Override output directory for crawl jobs"
    )


class JobStopRequest(BaseModel):
    force: bool = Field(
        default=False, description="Force stop without graceful shutdown"
    )
