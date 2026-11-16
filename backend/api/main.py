"""FastAPI entrypoint for the Academic Question Bot backend."""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from ..core.config import get_settings
from ..core.logging import configure_logging, request_id_var
from ..db import (
    admission_applications,
    auth_tokens,
    chat_analytics,
    rag_documents,
    session as db_session,
    telegram_users,
)
from .routers import admin, auth, chat, rag, telegram

configure_logging()
logger = logging.getLogger("api")
settings = get_settings()


def _ensure_schema() -> None:
    telegram_users.ensure_table()
    auth_tokens.ensure_table()
    chat_analytics.ensure_tables()
    admission_applications.ensure_tables()
    rag_documents.ensure_tables()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        await run_in_threadpool(_ensure_schema)
    except Exception:
        # Fail fast in production; keep local dev usable without Postgres.
        logger.exception("Database schema initialisation failed")
        if settings.is_production:
            raise
    logger.info(
        "API started env=%s model=%s llm=%s",
        settings.app_env,
        settings.openai_model,
        "on" if settings.openai_api_key else "off",
    )
    yield
    db_session.close_pool()


app = FastAPI(
    title="Academic Question Bot",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/api/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/api/openapi.json",
)



@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        response = JSONResponse(status_code=500, content={"detail": "Internal server error", "request_id": request_id})
    finally:
        request_id_var.reset(token)
    elapsed = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    if not request.url.path.startswith("/api/health"):
        logger.info("%s %s -> %s %.0fms [%s]", request.method, request.url.path, response.status_code, elapsed, request_id)
    return response


# Added last = outermost: CORS headers are present even on error responses,
# so the browser shows the real error instead of a misleading "CORS policy" one.
allow_all = "*" in settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else list(settings.cors_origins),
    # Credentials must not be combined with a wildcard origin.
    allow_credentials=not allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.get("/api/health", tags=["health"])
def liveness() -> dict:
    """Liveness probe: the process is up."""
    return {"status": "ok"}


@app.get("/api/health/ready", tags=["health"])
def readiness() -> JSONResponse:
    """Readiness probe: dependencies are reachable."""
    from ..rag.service import rag_service

    checks = {
        "database": db_session.ping(),
        "vector_store": rag_service.vector_store.ping(),
        "llm_configured": bool(settings.openai_api_key),
    }
    healthy = checks["database"] and checks["vector_store"]
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "degraded", "checks": checks, "vector_mode": rag_service.vector_store.mode},
    )


app.include_router(chat.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(telegram.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
