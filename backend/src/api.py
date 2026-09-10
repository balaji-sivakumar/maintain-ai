"""FastAPI service — Day 5 deployment target for Railway.

Wraps the orchestrator built in agents/orchestrator.py behind a small HTTP
API: manual add/update endpoints, /check (also driven by the Railway cron
service, scripts/cron_check.py), a WebSocket live tool-trace endpoint for
the frontend, and demo/simulator helpers for seeding scenarios.
"""

import json
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.orchestrator import build_orchestrator
from live_trace import stream_events
from runtime import build_storage, build_vector_store

_state: dict = {}

CHECK_PROMPT = "Check if any of my appliances need maintenance."


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state["storage"] = build_storage()
    _state["vector_store"] = build_vector_store()
    yield
    _state.clear()


def _build_agent():
    # Fresh Agent per call, not a shared instance: Strands agents carry
    # conversation history and raise ConcurrencyException if the same
    # instance is invoked concurrently — both wrong for a multi-request API.
    # Storage/vector_store (the expensive, stateful pieces — DB connections)
    # are still built once in lifespan and shared.
    return build_orchestrator(_state["storage"], vector_store=_state["vector_store"])


app = FastAPI(title="Maintain-AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AddApplianceRequest(BaseModel):
    appliance_type: str
    brand: str
    model: str
    install_date: str


class LogServiceRequest(BaseModel):
    service_date: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/appliances")
def list_appliances():
    return _state["storage"].list_appliances()


@app.post("/appliances")
def add_appliance(body: AddApplianceRequest):
    appliance_id = _state["storage"].add_appliance(body.model_dump())
    return {"appliance_id": appliance_id}


@app.post("/appliances/{appliance_id}/service")
def log_service(appliance_id: str, body: LogServiceRequest):
    resolved_date = body.service_date or date.today().isoformat()
    try:
        _state["storage"].update_appliance(appliance_id, last_serviced_date=resolved_date)
    except KeyError:
        raise HTTPException(status_code=404, detail="appliance not found")
    return {"appliance_id": appliance_id, "last_serviced_date": resolved_date}


@app.delete("/appliances/{appliance_id}")
def delete_appliance(appliance_id: str):
    try:
        _state["storage"].delete_appliance(appliance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="appliance not found")
    return {"appliance_id": appliance_id, "deleted": True}


@app.post("/check")
def check_maintenance():
    """Runs the orchestrator's daily maintenance check (no live trace).

    Called by the Railway cron service. For a live tool-by-tool trace, use
    the /ws/check WebSocket instead.
    """
    result = _build_agent()(CHECK_PROMPT)
    return {"response": str(result)}


# --- Simulator / demo data -------------------------------------------------

DEMO_APPLIANCES = [
    # Badly overdue, structured-table hit -> repair recommendation.
    {
        "appliance_type": "hvac_system",
        "brand": "Carrier",
        "model": "Infinity",
        "install_date": "2024-01-01",
    },
    # Near end-of-life, structured-table hit -> replace recommendation.
    {
        "appliance_type": "water_heater_tank",
        "brand": "Rheem",
        "model": "Performance Plus",
        "install_date": "2015-01-01",
    },
    # Not in appliances.json -> exercises the RAG fallback live.
    {
        "appliance_type": "ev_charger",
        "brand": "ChargePoint",
        "model": "Home Flex",
        "install_date": "2015-01-01",
    },
    # Recently serviced -> not due, demonstrates the "stays silent" case
    # when checked on its own (delete the other three first to see it).
    {
        "appliance_type": "dishwasher",
        "brand": "Bosch",
        "model": "500 Series",
        "install_date": "2023-01-01",
        "last_serviced_date": date.today().isoformat(),
    },
]


@app.post("/demo/seed")
def seed_demo_data():
    """Clears tracked appliances and adds a fixed set of demo scenarios."""
    storage = _state["storage"]
    for appliance in storage.list_appliances():
        storage.delete_appliance(appliance["id"])

    seeded = []
    for appliance in DEMO_APPLIANCES:
        appliance_id = storage.add_appliance(appliance)
        seeded.append({**appliance, "id": appliance_id})
    return {"seeded": seeded}


@app.post("/demo/reset")
def reset_demo_data():
    """Deletes all tracked appliances."""
    storage = _state["storage"]
    ids = [a["id"] for a in storage.list_appliances()]
    for appliance_id in ids:
        storage.delete_appliance(appliance_id)
    return {"deleted": len(ids)}


# --- Live tool trace ---------------------------------------------------

@app.websocket("/ws/check")
async def ws_check(websocket: WebSocket):
    """Streams the orchestrator's tool-by-tool trace for one maintenance
    check, live, as it executes — see live_trace.stream_events()."""
    await websocket.accept()
    try:
        agent = _build_agent()
        async for event in stream_events(agent, CHECK_PROMPT):
            await websocket.send_text(json.dumps(event))
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass  # already closed (e.g. client disconnected mid-stream)
