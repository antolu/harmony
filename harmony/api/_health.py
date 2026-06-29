from __future__ import annotations

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

logger = structlog.get_logger(__name__)
router = APIRouter()


# /health is a model-server-agnostic liveness probe — it does not depend on
# Ollama, vLLM, or any model backend. /ready checks dependencies; only ES,
# Postgres, and Redis are required (model serving is reported informationally).


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — always returns ok if the process is alive."""
    return {"status": "ok"}


@router.get("/api/health")
async def api_health() -> dict[str, str]:
    """Liveness probe (api prefix) — always returns ok if the process is alive."""
    return {"status": "ok"}


async def _check_deps(request: Request) -> dict[str, bool | str]:
    deps: dict[str, bool | str] = {}
    app = request.app

    try:
        es_healthy = await app.state.es_service.health_check()
    except Exception as exc:
        logger.warning("readiness_check_failed", dep="elasticsearch", error=str(exc))
        es_healthy = False
    deps["elasticsearch"] = es_healthy

    try:
        async with app.state.db_pool.connection() as _:
            pass
        deps["postgres"] = True
    except Exception as exc:
        logger.warning("readiness_check_failed", dep="postgres", error=str(exc))
        deps["postgres"] = False

    deps["redis"] = await _check_redis(request)

    qdrant = getattr(app.state, "qdrant_service", None)
    if qdrant is None:
        deps["qdrant"] = "disabled"
    else:
        try:
            deps["qdrant"] = not await qdrant.is_empty() or True
        except Exception as exc:
            logger.warning("readiness_check_failed", dep="qdrant", error=str(exc))
            deps["qdrant"] = False

    # Model serving is informational only — never required for readiness.
    try:
        hosts = await app.state.model_host_service.list_all()
        for host_type in ("ollama", "vllm"):
            deps[host_type] = (
                "configured"
                if any(h.host_type == host_type for h in hosts)
                else "disabled"
            )
    except Exception as exc:
        logger.warning("readiness_check_failed", dep="model_hosts", error=str(exc))
        deps["ollama"] = False
        deps["vllm"] = False

    return deps


async def _check_redis(request: Request) -> bool:
    app = request.app
    redis = getattr(app.state, "redis_client", None)
    if redis is None:
        return False
    try:
        await redis.ping()
    except Exception as exc:
        logger.warning("readiness_check_failed", dep="redis", error=str(exc))
        return False
    else:
        return True


@router.get("/ready")
async def ready(request: Request) -> Response:
    """Readiness probe — checks all configured dependencies."""
    deps = await _check_deps(request)
    required = ["elasticsearch", "postgres", "redis"]
    all_ready = all(deps[k] is True for k in required)
    status = "ready" if all_ready else "degraded"
    content: dict[str, str | dict[str, bool | str]] = {
        "status": status,
        "dependencies": deps,
    }
    status_code = 200 if all_ready else 503
    return JSONResponse(status_code=status_code, content=content)


@router.get("/api/ready")
async def api_ready(request: Request) -> Response:
    """Readiness probe (api prefix) — checks all configured dependencies."""
    return await ready(request)
