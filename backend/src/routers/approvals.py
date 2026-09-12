"""Human-in-the-loop approval endpoints (Day 6) — list pending
submit_maintenance_request decisions and resolve them. The pause/resume
mechanics themselves live in confirmations.py; this is just the HTTP
surface over it.
"""

from fastapi import APIRouter, HTTPException

from core import app_state
from core.confirmations import confirmation_required_response, resume_confirmation
from schemas.requests import RespondConfirmationRequest

router = APIRouter()


@router.get("/confirmations")
def list_confirmations():
    """Pending submit_maintenance_request approvals for the dashboard to
    display — each `requests` entry is one due appliance's proposed
    repair/replace decision awaiting a human's approve/deny."""
    return [
        {"id": c["id"], "requests": c["requests"]}
        for c in app_state.state["storage"].list_confirmations()
    ]


@router.post("/confirmations/{confirmation_id}/respond")
def respond_to_confirmation(confirmation_id: str, body: RespondConfirmationRequest):
    """Resolve every pending appliance decision in a confirmation batch in
    one round trip: appliances in `approved_appliance_ids` are approved,
    every other pending appliance in the batch is denied. Resumes the run
    that raised it on a fresh agent instance (see confirmations.py)."""
    storage = app_state.state["storage"]
    agent = app_state.build_agent()
    try:
        result = resume_confirmation(storage, agent, confirmation_id, body.approved_appliance_ids)
    except KeyError:
        raise HTTPException(status_code=404, detail="confirmation not found")
    app_state.flush_telemetry()

    # Same agent instance resume_confirmation just resumed — a further
    # gated tool call later in the same run would interrupt it again, and
    # take_snapshot() must run on the agent that actually holds that state.
    next_confirmation = confirmation_required_response(storage, agent, result)
    return next_confirmation or {
        "approved_appliance_ids": body.approved_appliance_ids,
        "response": str(result),
    }
