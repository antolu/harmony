from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from harmony.api.auth.middleware import JWTAuthMiddleware
from harmony.api.config import settings
from harmony.api.observability import TraceMiddleware

logger = logging.getLogger(__name__)


def apply_middlewares(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled exception",
            extra={"method": request.method, "path": request.url.path},
        )
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc) or "Internal server error"},
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(JWTAuthMiddleware)
    app.add_middleware(TraceMiddleware)
