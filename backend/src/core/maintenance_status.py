"""Shared due/overdue computation for a tracked appliance.

Used by both the check_due_maintenance tool (agent-facing) and the
GET /appliances list endpoint (dashboard-facing `status` field) — one
source of truth for what counts as due, so the two never disagree.
"""

from datetime import date
from typing import Any, Optional

from core.dates import add_months, parse_date

OK = "OK"
SERVICE_DUE = "SERVICE_DUE"
REPAIR_REQUESTED = "REPAIR_REQUESTED"
REPLACE_REQUESTED = "REPLACE_REQUESTED"
UNKNOWN = "UNKNOWN"


def next_due_date(appliance: dict[str, Any], reference: dict[str, Any]) -> date:
    last_service_str = appliance.get("last_serviced_date") or appliance["install_date"]
    return add_months(parse_date(last_service_str), reference["service_interval_months"])


def compute_status(appliance: dict[str, Any], reference: Optional[dict[str, Any]], today: date) -> str:
    """UNKNOWN means there's no reference data yet (e.g. a RAG-only type that
    hasn't been looked up/cached) — this never triggers a RAG lookup itself,
    since it's meant for cheap, side-effect-free display (the appliance
    list), not the agent's own due-check (see check_due_maintenance, which
    does fall back to RAG).

    When an appliance is due and a repair/replace request has already been
    submitted for it (submit_maintenance_request, Day 6 human-in-the-loop
    gate), that's reflected distinctly rather than just SERVICE_DUE again —
    it's already been acted on, just not serviced yet.
    """
    if not reference or not reference.get("service_interval_months"):
        return UNKNOWN

    if today < next_due_date(appliance, reference):
        return OK

    requested_action = appliance.get("requested_action")
    if requested_action == "repair":
        return REPAIR_REQUESTED
    if requested_action == "replace":
        return REPLACE_REQUESTED
    return SERVICE_DUE
