"""
main.py — FastAPI application entrypoint.
"""

import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from api.database import test_connection
from api.logger import get_logger
from api.metrics import collect_metrics
from api.routers import reports, tickets
from api.routers.auth import router as auth_router

log = get_logger(__name__)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
INDEX_HTML   = os.path.join(FRONTEND_DIR, "index.html")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if test_connection():
        log.info("SQL Server connection OK")
    else:
        log.warning("SQL Server not reachable")
    yield
    log.info("API shutting down")


app = FastAPI(
    title="SupportOps Toolkit API",
    version="2.0.0",
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
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    if not request.url.path.startswith("/static"):
        log.info("HTTP request", extra={
            "method": request.method, "path": request.url.path,
            "status_code": response.status_code, "duration_ms": duration_ms,
        })
    return response


# ── Prometheus ────────────────────────────────────────────────────────────────
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
).add(lambda _: collect_metrics()).instrument(app).expose(app)

# ── API routes (registered BEFORE the SPA catch-all) ─────────────────────────
app.include_router(auth_router)
app.include_router(tickets.router)
app.include_router(reports.router)


@app.get("/health", tags=["System"])
def health():
    db_ok = test_connection()
    return {"api": "ok", "database": "ok" if db_ok else "unreachable"}


# ── Frontend static files ─────────────────────────────────────────────────────
# Mount static assets (JS, CSS, images) at /assets
assets_dir = os.path.join(FRONTEND_DIR, "assets")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# SPA catch-all — must be LAST so it never intercepts /tickets, /auth, etc.
@app.get("/ui", include_in_schema=False)
@app.get("/ui/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str = ""):
    """Serve the React SPA only for /ui/* routes."""
    if os.path.exists(INDEX_HTML):
        return FileResponse(INDEX_HTML)
    return {"message": "Frontend not built. API docs at /docs"}
