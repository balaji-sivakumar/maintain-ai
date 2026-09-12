"""FastAPI service — Day 5 deployment target for Railway.

Wraps the orchestrator built in agents/orchestrator.py behind a small HTTP
API. Route handlers live in routers/, grouped by responsibility:
    health       — /health
    appliances   — tracked-appliance CRUD + logging a completed service
    checks       — /check (also driven by the Railway cron service,
                   scripts/cron_check.py) and /ws/check, the live trace
    demo         — /demo/seed, /demo/reset (scenario simulator)
    approvals    — /confirmations, human-in-the-loop approve/deny (Day 6)

This module just builds the app, wires shared state (storage/vector_store/
notifier — see app_state.py) into the lifespan handler, and mounts routers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core import app_state
from routers import appliances, approvals, checks, demo, health
from runtime import build_notifier, build_storage, build_vector_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_state.state["storage"] = build_storage()
    app_state.state["vector_store"] = build_vector_store()
    app_state.state["notifier"] = build_notifier()
    yield
    app_state.state.clear()


app = FastAPI(title="Maintain-AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(appliances.router)
app.include_router(checks.router)
app.include_router(demo.router)
app.include_router(approvals.router)
