from __future__ import annotations

import json
import typing

from fastapi import APIRouter, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from harmony.api.dependencies import get_job_manager, get_log_streamer
from harmony.api.services.admin import JobManager, LogStreamer

router = APIRouter()


@router.get("/{job_id}/logs")
async def get_job_logs(
    job_id: str,
    lines: int = 100,
    job_manager: JobManager = Depends(get_job_manager),
    log_streamer: LogStreamer = Depends(get_log_streamer),
) -> dict[str, list[str]]:
    """Get the last N lines of a job's log."""
    job = await job_manager.get_job_async(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    log_lines = await log_streamer.tail_log(job_id, num_lines=lines)
    return {"lines": log_lines}


@router.get("/{job_id}/logs/stream")
async def stream_job_logs(
    job_id: str,
    job_manager: JobManager = Depends(get_job_manager),
    log_streamer: LogStreamer = Depends(get_log_streamer),
) -> EventSourceResponse:
    """Stream job logs via SSE."""
    job = await job_manager.get_job_async(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    async def event_generator() -> typing.AsyncGenerator[dict[str, str], None]:
        async for line in log_streamer.stream_log(job_id, follow=True):
            yield {
                "event": "log",
                "data": json.dumps({"line": line}),
            }

            current_job = job_manager.get_job(job_id)
            if current_job and current_job.status.value in {
                "completed",
                "failed",
                "stopped",
            }:
                yield {
                    "event": "done",
                    "data": json.dumps({"status": current_job.status.value}),
                }
                break

    return EventSourceResponse(event_generator())
