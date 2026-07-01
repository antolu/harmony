from __future__ import annotations

import asyncio
import json
import logging
import typing

import litellm
import redis.asyncio
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from harmony.api.dependencies import (
    get_job_manager,
    get_model_settings_store,
    require_role,
)
from harmony.api.services.admin import JobManager, ModelSettingsStore
from harmony.clients._qdrant import QdrantService
from harmony.db.redis_client import get_async_redis
from harmony.models import (
    AnonymousIdentity,
    Job,
    JobProgress,
    JobStatus,
    JobType,
    UserIdentity,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class JobCreateRequest(BaseModel):
    type: JobType | None = None
    config_name: str | None = None
    output_override: str | None = None
    copy_from: str | None = None
    start_fresh: bool = False


class JobActionRequest(BaseModel):
    action: typing.Literal["stop", "pause", "resume", "cancel"] | None = None
    force: bool = False
    reset_checkpoint: bool = False


class JobStartRequest(BaseModel):
    config_name: str = Field(..., description="Name of saved config to use")
    output_override: str | None = Field(
        None, description="Override output directory for crawl jobs"
    )


class JobStopRequest(BaseModel):
    force: bool = Field(
        default=False, description="Force stop without graceful shutdown"
    )


class IndexPreflightResult(BaseModel):
    needs_recreate: bool
    reason: str | None = None
    stored_model: str | None = None
    actual_model: str | None = None
    stored_dim: int | None = None
    actual_dim: int | None = None


async def _check_collection_stale(
    qdrant_service: QdrantService,
    embedding_model: str,
) -> IndexPreflightResult:
    if not await qdrant_service.collection_exists():
        return IndexPreflightResult(needs_recreate=False)

    probe = await litellm.aembedding(model=embedding_model, input=["probe"])
    actual_dim = len(
        probe.data[0]["embedding"]
        if isinstance(probe.data[0], dict)
        else probe.data[0].embedding
    )
    stored_dim, stored_model = await qdrant_service.get_collection_info()

    if stored_dim != actual_dim:
        return IndexPreflightResult(
            needs_recreate=True,
            reason=f"Vector dimension changed: {stored_dim} → {actual_dim}",
            stored_dim=stored_dim,
            actual_dim=actual_dim,
            stored_model=stored_model,
            actual_model=embedding_model,
        )
    if stored_model and stored_model != embedding_model:
        return IndexPreflightResult(
            needs_recreate=True,
            reason=f"Embedding model changed: {stored_model} → {embedding_model}",
            stored_model=stored_model,
            actual_model=embedding_model,
            stored_dim=stored_dim,
            actual_dim=actual_dim,
        )
    return IndexPreflightResult(needs_recreate=False)


async def _start_typed_job(
    body: JobCreateRequest,
    job_manager: JobManager,
    model_settings: ModelSettingsStore,
) -> Job:
    if body.start_fresh:
        return await job_manager.start_job_fresh(
            config_name=body.config_name or "",
            job_type=body.type or "",
            created_by="api",
        )
    if body.type == "crawl":
        return await job_manager.start_crawl_job(
            config_name=body.config_name or "",
            output_override=body.output_override,
        )
    if body.type == "index":
        return await job_manager.start_index_job(config_name=body.config_name or "")
    if body.type == "embed":
        embedding_model = await model_settings.get_embedding_model()
        return await job_manager.start_embed_job(embedding_model=embedding_model)
    raise HTTPException(status_code=422, detail=f"Unknown job type: {body.type!r}")


async def _apply_job_action(
    job_id: str,
    body: JobActionRequest,
    job_manager: JobManager,
) -> Job:
    if body.action == "stop":
        return await job_manager.stop_job(job_id, force=body.force)
    if body.action == "pause":
        return await job_manager.pause_job(job_id)
    if body.action == "resume":
        return await job_manager.resume_job(job_id)
    if body.action == "cancel":
        existing = await job_manager.get_job_async(job_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        cancelled = await job_manager.cancel_job(job_id)
        if not cancelled:
            raise HTTPException(
                status_code=400, detail=f"Job '{job_id}' is not running"
            )
        updated = await job_manager.get_job_async(job_id)
        if updated is None:
            raise HTTPException(
                status_code=404, detail=f"Job '{job_id}' not found after cancel"
            )
        return updated
    raise HTTPException(status_code=422, detail=f"Unknown action: {body.action!r}")


@router.get("", response_model=list[Job])
async def list_jobs(
    job_type: JobType | None = None,
    status: JobStatus | None = None,
    limit: int = 50,
    job_manager: JobManager = Depends(get_job_manager),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> list[Job]:
    """List all jobs with optional filtering."""
    return await job_manager.list_jobs(job_type=job_type, status=status, limit=limit)


@router.get("/preflight", response_model=IndexPreflightResult)
async def index_preflight(
    request: Request,
    model_settings: ModelSettingsStore = Depends(get_model_settings_store),
) -> IndexPreflightResult:
    """Check whether starting an index job would require recreating the Qdrant collection."""
    qdrant_service = getattr(request.app.state, "qdrant_service", None)
    if qdrant_service is None:
        return IndexPreflightResult(needs_recreate=False)
    try:
        embedding_model = await model_settings.get_embedding_model()
        return await _check_collection_stale(qdrant_service, embedding_model)
    except Exception:
        return IndexPreflightResult(needs_recreate=False)


@router.post("", response_model=Job)
async def create_job(
    body: JobCreateRequest,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
    job_manager: JobManager = Depends(get_job_manager),
    model_settings: ModelSettingsStore = Depends(get_model_settings_store),
) -> Job:
    """Start a new job. Accepts type+config_name or copy_from to retrigger."""
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"

    if body.copy_from:
        try:
            job = await job_manager.retrigger_job(body.copy_from, created_by=user_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        await request.app.state.audit_log_service.record(
            user_id=user_id,
            action="job_retriggered",
            entity_type="job",
            entity_id=body.copy_from,
            details={"new_job_id": job.id},
        )
        return job

    if body.type is None:
        raise HTTPException(
            status_code=422,
            detail="type is required when copy_from is not set",
        )

    try:
        job = await _start_typed_job(body, job_manager, model_settings)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Failed to start job: %s", body)
        raise HTTPException(status_code=500, detail=str(e)) from e

    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action="job_started",
        entity_type="job",
        entity_id=job.id,
        details={
            "config_name": body.config_name,
            "job_type": body.type,
            "start_fresh": body.start_fresh,
        },
    )
    return job


@router.patch("/{job_id}", response_model=Job)
async def update_job(
    job_id: str,
    body: JobActionRequest,
    request: Request,
    current_user: UserIdentity | AnonymousIdentity = Depends(require_role("operator")),
    job_manager: JobManager = Depends(get_job_manager),
) -> Job:
    """Control a job: stop, pause, resume, cancel, or reset checkpoint."""
    user_id = current_user.id if isinstance(current_user, UserIdentity) else "system"

    if body.reset_checkpoint:
        existing = await job_manager.get_job_async(job_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        try:
            job = await job_manager.start_job_fresh(
                config_name=existing.config_name,
                job_type=existing.type,
                created_by=user_id,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        await request.app.state.audit_log_service.record(
            user_id=user_id,
            action="job_started",
            entity_type="job",
            entity_id=job.id,
            details={"config_name": existing.config_name, "start_fresh": True},
        )
        return job

    if body.action is None:
        raise HTTPException(
            status_code=422,
            detail="action is required (stop|pause|resume|cancel) or set reset_checkpoint=true",
        )

    try:
        job = await _apply_job_action(job_id, body, job_manager)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    await request.app.state.audit_log_service.record(
        user_id=user_id,
        action=f"job_{body.action}",
        entity_type="job",
        entity_id=job_id,
        details={},
    )
    return job


@router.get("/{job_id}", response_model=Job)
async def get_job(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> Job:
    """Get a specific job by ID."""
    job = await job_manager.get_job_async(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


@router.get("/{job_id}/progress", response_model=JobProgress)
async def get_job_progress(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> JobProgress:
    """Get current progress for a job."""
    job = await job_manager.get_job_async(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    progress = await job_manager.get_progress(job_id)
    if progress is None:
        return JobProgress()
    return progress


async def _poll_job_events(
    job_id: str,
    job_manager: JobManager,
    pubsub: redis.asyncio.client.PubSub,
) -> typing.AsyncGenerator[dict[str, str], None]:
    last_progress: JobProgress | None = None
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
        if progress and progress != last_progress:
            yield {
                "event": "progress",
                "data": json.dumps(progress.model_dump(mode="json")),
            }
            last_progress = progress

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
async def _stream_job_progress(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager),
    _: UserIdentity | AnonymousIdentity = Depends(require_role("read-only")),
) -> EventSourceResponse:
    """Stream progress updates for a job via SSE."""
    job = await job_manager.get_job_async(job_id)
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
