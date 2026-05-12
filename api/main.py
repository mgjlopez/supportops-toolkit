"""
main.py — FastAPI application entrypoint.
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from api.database import test_connection
from api.logger import get_logger
from api.metrics import collect_metrics
from api.routers import reports, tickets

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if test_connection():
        log.info("SQL Server connection OK")
    else:
        log.warning("SQL Server not reachable — check your .env and Docker")
    yield
    log.info("API shutting down")


app = FastAPI(
    title="SupportOps Toolkit API",
    description=(
        "REST API for the SupportOps Toolkit — a local IT support automation system. "
        "Manages tickets, SLA tracking, health monitoring, and reporting."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Logs every request with method, path, status code and duration."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    log.info(
        "HTTP request",
        extra={
            "method":      request.method,
            "path":        request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


# ── Prometheus ────────────────────────────────────────────────────────────────
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
).add(lambda _: collect_metrics()).instrument(app).expose(app)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(tickets.router)
app.include_router(reports.router)


@app.get("/health", tags=["System"], summary="API health check")
def health():
    db_ok = test_connection()
    status = {"api": "ok", "database": "ok" if db_ok else "unreachable"}
    log.info("Health check", extra=status)
    return status


@app.get("/", tags=["System"], include_in_schema=False)
def root():
    return {"message": "SupportOps Toolkit API — visit /docs for the full API reference"}
