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
from confirmations import persist_if_interrupted, resume_confirmation
from live_trace import stream_events
from runtime import build_notifier, build_storage, build_vector_store, setup_telemetry

_telemetry = setup_telemetry()

_state: dict = {}


def _flush_telemetry() -> None:
    # Not correctness-critical here (unlike the cron script, this process
    # stays alive and the batch timer would flush eventually) — just makes
    # spans show up in Honeycomb immediately after a check, rather than
    # trailing behind the WebSocket trace by the batch interval.
    if _telemetry:
        _telemetry.tracer_provider.force_flush()

CHECK_PROMPT = "Check if any of my appliances need maintenance."


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state["storage"] = build_storage()
    _state["vector_store"] = build_vector_store()
    _state["notifier"] = build_notifier()
    yield
    _state.clear()


def _build_agent():
    # Fresh Agent per call, not a shared instance: Strands agents carry
    # conversation history and raise ConcurrencyException if the same
    # instance is invoked concurrently — both wrong for a multi-request API.
    # Storage/vector_store (the expensive, stateful pieces — DB connections)
    # are still built once in lifespan and shared. Notifier is stateless.
    return build_orchestrator(
        _state["storage"], vector_store=_state["vector_store"], notifier=_state["notifier"]
    )


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


class UpdateApplianceRequest(BaseModel):
    """Fields to edit on an existing tracked appliance — for playing around
    with scenarios (age it, back-date/clear its last service) without
    deleting and re-adding it. Only fields actually present in the request
    body are touched (model_dump(exclude_unset=True) below): omit a field to
    leave it alone, send it as null to clear it (e.g. last_serviced_date),
    or send a value to set it."""

    install_date: str | None = None
    last_serviced_date: str | None = None


class RespondConfirmationRequest(BaseModel):
    approved_appliance_ids: list[str]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/appliances")
def list_appliances():
    # status is whatever check_due_maintenance last persisted (see
    # maintenance_status.py) — absent until the first check runs, not
    # computed live here, so seeding never shows a status out of thin air.
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


@app.patch("/appliances/{appliance_id}")
def update_appliance(appliance_id: str, body: UpdateApplianceRequest):
    """Edit install_date and/or last_serviced_date on an existing appliance
    — lets the dashboard's scenario simulator age an appliance or back-date
    (or clear) its last service without deleting and re-adding it."""
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="no fields to update")
    try:
        _state["storage"].update_appliance(appliance_id, **fields)
    except KeyError:
        raise HTTPException(status_code=404, detail="appliance not found")
    return _state["storage"].get_appliance(appliance_id)


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

    If the check ends up recommending a repair/replacement, submitting that
    request is gated behind human approval (Day 6) — the run pauses there
    rather than recording anything, and this returns a pending confirmation
    (one entry per due appliance) instead of a final response. See
    /confirmations and POST /confirmations/{id}/respond.
    """
    agent = _build_agent()
    result = agent(CHECK_PROMPT)
    _flush_telemetry()

    confirmation = persist_if_interrupted(_state["storage"], agent, result)
    if confirmation:
        return {
            "confirmation_required": True,
            "confirmation_id": confirmation["id"],
            "requests": confirmation["requests"],
        }
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


def _clear_confirmations(storage) -> None:
    """Any pending confirmation left over from before a seed/reset points at
    appliance ids that no longer exist — without this they'd keep showing up
    in the Pending Approvals panel as orphaned, unresolvable entries."""
    for confirmation in storage.list_confirmations():
        storage.delete_confirmation(confirmation["id"])


@app.post("/demo/seed")
def seed_demo_data():
    """Clears tracked appliances and pending confirmations, then adds a
    fixed set of demo scenarios."""
    storage = _state["storage"]
    for appliance in storage.list_appliances():
        storage.delete_appliance(appliance["id"])
    _clear_confirmations(storage)

    seeded = []
    for appliance in DEMO_APPLIANCES:
        appliance_id = storage.add_appliance(appliance)
        seeded.append({**appliance, "id": appliance_id})
    return {"seeded": seeded}


@app.post("/demo/reset")
def reset_demo_data():
    """Deletes all tracked appliances and any pending confirmations."""
    storage = _state["storage"]
    ids = [a["id"] for a in storage.list_appliances()]
    for appliance_id in ids:
        storage.delete_appliance(appliance_id)
    _clear_confirmations(storage)
    return {"deleted": len(ids)}


# --- Live tool trace ---------------------------------------------------

@app.websocket("/ws/check")
async def ws_check(websocket: WebSocket):
    """Streams the orchestrator's tool-by-tool trace for one maintenance
    check, live, as it executes — see live_trace.stream_events()."""
    await websocket.accept()
    try:
        agent = _build_agent()
        async for event in stream_events(agent, CHECK_PROMPT, storage=_state["storage"]):
            await websocket.send_text(json.dumps(event))
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
    finally:
        _flush_telemetry()
        try:
            await websocket.close()
        except RuntimeError:
            pass  # already closed (e.g. client disconnected mid-stream)


# --- Human-in-the-loop confirmations (Day 6) --------------------------

@app.get("/confirmations")
def list_confirmations():
    """Pending submit_maintenance_request approvals for the dashboard to
    display — each `requests` entry is one due appliance's proposed
    repair/replace decision awaiting a human's approve/deny."""
    return [
        {"id": c["id"], "requests": c["requests"]} for c in _state["storage"].list_confirmations()
    ]


@app.post("/confirmations/{confirmation_id}/respond")
def respond_to_confirmation(confirmation_id: str, body: RespondConfirmationRequest):
    """Resolve every pending appliance decision in a confirmation batch in
    one round trip: appliances in `approved_appliance_ids` are approved,
    every other pending appliance in the batch is denied. Resumes the run
    that raised it on a fresh agent instance (see confirmations.py)."""
    agent = _build_agent()
    try:
        result = resume_confirmation(
            _state["storage"], agent, confirmation_id, body.approved_appliance_ids
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="confirmation not found")
    _flush_telemetry()

    # Same agent instance resume_confirmation just resumed — a further
    # gated tool call later in the same run would interrupt it again, and
    # take_snapshot() must run on the agent that actually holds that state.
    next_confirmation = persist_if_interrupted(_state["storage"], agent, result)
    if next_confirmation:
        return {
            "confirmation_required": True,
            "confirmation_id": next_confirmation["id"],
            "requests": next_confirmation["requests"],
        }
    return {"approved_appliance_ids": body.approved_appliance_ids, "response": str(result)}
