"""
main.py — FastAPI application entrypoint.
Registers routers, startup events, and the health check endpoint.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.database import test_connection
from api.routers import tickets, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup checks before accepting traffic."""
    print("[SupportOps] Starting up...")
    if test_connection():
        print("[SupportOps] ✅ SQL Server connection OK")
    else:
        print("[SupportOps] ⚠️  SQL Server not reachable — check your .env and Docker")
    yield
    print("[SupportOps] Shutting down.")


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
    allow_origins=["*"],  # Fine for local dev; restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tickets.router)
app.include_router(reports.router)


@app.get("/health", tags=["System"], summary="API health check")
def health():
    db_ok = test_connection()
    return {
        "api": "ok",
        "database": "ok" if db_ok else "unreachable",
    }


@app.get("/", tags=["System"], include_in_schema=False)
def root():
    return {"message": "SupportOps Toolkit API — visit /docs for the full API reference"}
