"""Runs the orchestrator's maintenance check: /check (one-shot, also the
Railway cron path) and /ws/check (the same check, live tool-by-tool trace
for the dashboard).
"""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

import app_state
from confirmations import confirmation_required_response
from live_trace import stream_events

router = APIRouter()


@router.post("/check")
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
    agent = app_state.build_agent()
    result = agent(app_state.CHECK_PROMPT)
    app_state.flush_telemetry()

    confirmation = confirmation_required_response(app_state.state["storage"], agent, result)
    return confirmation or {"response": str(result)}


@router.websocket("/ws/check")
async def ws_check(websocket: WebSocket):
    """Streams the orchestrator's tool-by-tool trace for one maintenance
    check, live, as it executes — see live_trace.stream_events().

    stream_events() is a pure translator: it doesn't know about Storage or
    confirmations, it just reports "interrupted" vs "done" with the raw
    AgentResult attached. This handler is where that gets turned into the
    actual wire payload — the same shape /check and POST /confirmations/
    {id}/respond use, via confirmation_required_response().
    """
    await websocket.accept()
    try:
        agent = app_state.build_agent()
        async for event in stream_events(agent, app_state.CHECK_PROMPT):
            if event["type"] == "interrupted":
                response = confirmation_required_response(
                    app_state.state["storage"], agent, event["result"]
                )
                payload = {
                    "type": "confirmation_required",
                    "confirmation_id": response["confirmation_id"],
                    "requests": response["requests"],
                }
            elif event["type"] == "done":
                payload = {"type": "done", "final_text": str(event["result"])}
            else:
                payload = event
            await websocket.send_text(json.dumps(payload))
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
    finally:
        app_state.flush_telemetry()
        try:
            await websocket.close()
        except RuntimeError:
            pass  # already closed (e.g. client disconnected mid-stream)
