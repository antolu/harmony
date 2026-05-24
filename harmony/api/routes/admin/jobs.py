from __future__ import annotations

import asyncio
import json
import typing

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from harmony.api.dependencies import get_job_manager, get_model_settings_store
from harmony.api.models.job import (
    Job,
    JobProgress,
    JobStartRequest,
    JobStatus,
    JobStopRequest,
    JobType,
)
from harmony.api.services.admin import JobManager, ModelSettingsStore
from harmony.db.redis_client import get_async_redis

router = APIRouter()


@router.get("", response_model=list[Job])
async def list_jobs(
    job_type: JobType | None = None,
    status: JobStatus | None = None,
    limit: int = 50,
    job_manager: JobManager = Depends(get_job_manager),
) -> list[Job]:
    """List all jobs with optional filtering."""
    return await job_manager.list_jobs(job_type=job_type, status=status, limit=limit)


@router.get("/{job_id}", response_model=Job)
async def get_job(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager),
) -> Job:
    """Get a specific job by ID."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


@router.post("/crawl", response_model=Job)
async def start_crawl_job(
    request: JobStartRequest,
    job_manager: JobManager = Depends(get_job_manager),
) -> Job:
    """Start a new crawl job."""
    try:
        return await job_manager.start_crawl_job(
            config_name=request.config_name,
            output_override=request.output_override,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/index", response_model=Job)
async def start_index_job(
    request: JobStartRequest,
    job_manager: JobManager = Depends(get_job_manager),
) -> Job:
    """Start a new index job."""
    try:
        return await job_manager.start_index_job(config_name=request.config_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/embed", response_model=Job)
async def start_embed_job(
    job_manager: JobManager = Depends(get_job_manager),
    model_settings: ModelSettingsStore = Depends(get_model_settings_store),
) -> Job:
    """Start a re-embed job using the current embedding model."""
    embedding_model = await model_settings.get_embedding_model()
    try:
        return await job_manager.start_embed_job(embedding_model=embedding_model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{job_id}/stop", response_model=Job)
async def stop_job(
    job_id: str,
    request: JobStopRequest | None = None,
    job_manager: JobManager = Depends(get_job_manager),
) -> Job:
    """Stop a running job."""
    force = request.force if request else False
    try:
        return await job_manager.stop_job(job_id, force=force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{job_id}/pause", response_model=Job)
async def pause_job(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager),
) -> Job:
    """Pause a running crawl job."""
    try:
        return await job_manager.pause_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{job_id}/resume", response_model=Job)
async def resume_job(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager),
) -> Job:
    """Resume a paused crawl job."""
    try:
        return await job_manager.resume_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{job_id}/progress", response_model=JobProgress)
async def get_job_progress(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager),
) -> JobProgress:
    """Get current progress for a job."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    progress = await job_manager.get_progress(job_id)
    if progress is None:
        return JobProgress()
    return progress


async def _poll_job_events(
    job_id: str,
    job_manager: JobManager,
    pubsub: typing.Any,
) -> typing.AsyncGenerator[dict[str, str], None]:
    last_progress: dict[str, typing.Any] | None = None
    while True:
        current_job = job_manager.get_job(job_id)
        if current_job is None:
            yield {"event": "error", "data": json.dumps({"message": "Job not found"})}
            break

        safety_msg = await pubsub.get_message(
            ignore_subscribe_messages=True, timeout=0.1
        )
        if safety_msg is not None:
            yield {"event": "safety_pending", "data": safety_msg["data"]}

        progress = await job_manager.get_progress(job_id)
        if progress:
            progress_dict = progress.model_dump(mode="json")
            if progress_dict != last_progress:
                yield {"event": "progress", "data": json.dumps(progress_dict)}
                last_progress = progress_dict

        if current_job.status in {
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.STOPPED,
        }:
            yield {
                "event": "done",
                "data": json.dumps({
                    "status": current_job.status.value,
                    "error": current_job.error,
                }),
            }
            break

        await asyncio.sleep(1)


@router.get("/{job_id}/progress/stream")
async def stream_job_progress(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager),
) -> EventSourceResponse:
    """Stream progress updates for a job via SSE."""
    job = job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    async def event_generator() -> typing.AsyncGenerator[dict[str, str], None]:
        redis = await get_async_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"safety-pending:{job_id}")

        try:
            async for event in _poll_job_events(job_id, job_manager, pubsub):
                yield event
        finally:
            await pubsub.unsubscribe()
            await redis.aclose()

    return EventSourceResponse(event_generator())
