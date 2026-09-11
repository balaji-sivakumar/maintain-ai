"""Human-in-the-loop confirmation persistence (Day 6).

Bridges Strands' interrupt/resume mechanics (see agents/orchestrator.py's
HumanInTheLoop intervention, gating submit_maintenance_request) to the
Storage interface, so a paused run survives past the request/process that
started it. This matters because the human's approval click always arrives
as a *separate* HTTP request — the WebSocket that streamed the original
check may already be closed, or (for the cron path) the unattended process
that hit the gate has already exited.

When the orchestrator calls submit_maintenance_request once per due
appliance in the same turn, Strands pauses with *all* of them as separate
entries in result.interrupts at once (verified directly against the SDK) —
one snapshot, multiple pending decisions. This module persists that whole
batch as a single confirmation record, so the dashboard can show one screen
with a decision per appliance and resolve them together in one submission.

The resuming caller must build its Agent the same way the paused one was
(same tools, same HumanInTheLoop interventions list) — load_snapshot restores
conversation history and interrupt state, but before_tool_call still re-runs
on resume to evaluate each response, so the intervention has to be attached
again on the fresh instance.
"""

import uuid
from typing import Any, Optional

from strands import Agent, Snapshot
from strands.agent.agent_result import AgentResult

from interfaces.storage import Storage


def pending_requests(result: AgentResult) -> list[dict[str, Any]]:
    """Pairs each pending interrupt with the structured tool-call input that
    raised it (appliance_id/action/notes), by matching the interrupt id's
    embedded tool_use_id (HumanInTheLoop's Confirm.prompt is a formatted
    string, not structured, so this reads the actual args straight off the
    paused assistant message instead of parsing that string)."""
    tool_use_by_id = {
        block["toolUse"]["toolUseId"]: block["toolUse"]
        for block in result.message.get("content", [])
        if "toolUse" in block
    }

    requests = []
    for interrupt in result.interrupts or []:
        tool_use_id = interrupt.id.split(":")[2]
        tool_use_input = tool_use_by_id.get(tool_use_id, {}).get("input", {})
        requests.append({"interrupt_id": interrupt.id, **tool_use_input})
    return requests


def persist_if_interrupted(
    storage: Storage, agent: Agent, result: AgentResult
) -> Optional[dict[str, Any]]:
    """Save a pending confirmation if `result` paused on one or more
    interrupts (one per due appliance submit_maintenance_request call).

    Returns the saved confirmation record (with a fresh confirmation_id), or
    None if the run completed normally (nothing to confirm).
    """
    if result.stop_reason != "interrupt" or not result.interrupts:
        return None

    confirmation_id = str(uuid.uuid4())
    record = {
        "id": confirmation_id,
        "requests": pending_requests(result),
        "snapshot": agent.take_snapshot(preset="session").to_dict(),
    }
    storage.save_confirmation(confirmation_id, record)
    return record


def resume_confirmation(
    storage: Storage, agent: Agent, confirmation_id: str, approved_appliance_ids: list[str]
) -> AgentResult:
    """Resume a paused run on `agent` (a freshly-built orchestrator) with the
    household's per-appliance decisions, resolving every pending request in
    the batch in one round trip: appliances in `approved_appliance_ids` are
    approved, every other pending request in the batch is denied.

    Raises KeyError if the confirmation is unknown (already resolved, or a
    bad id). Deletes the confirmation once resumed — the caller should check
    the returned result for a fresh interrupt (e.g. via
    persist_if_interrupted again) before assuming the run is fully done.
    """
    record = storage.get_confirmation(confirmation_id)
    if record is None:
        raise KeyError(f"No pending confirmation with id {confirmation_id!r}")

    approved = set(approved_appliance_ids)
    agent.load_snapshot(Snapshot.from_dict(record["snapshot"]))
    result = agent(
        prompt=[
            {
                "interruptResponse": {
                    "interruptId": request["interrupt_id"],
                    "response": request.get("appliance_id") in approved,
                }
            }
            for request in record["requests"]
        ]
    )
    storage.delete_confirmation(confirmation_id)
    return result
