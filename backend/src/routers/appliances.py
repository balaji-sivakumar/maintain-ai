"""Tracked-appliance CRUD: add/list/edit/delete, and logging a completed
service. `status` on a listed appliance is whatever check_due_maintenance
last persisted (see maintenance_status.py) — absent until the first check
runs, never computed here.
"""

from datetime import date

from fastapi import APIRouter, HTTPException

import app_state
from maintenance_status import compute_status
from schemas.requests import AddApplianceRequest, LogServiceRequest, UpdateApplianceRequest

router = APIRouter()


@router.get("/appliances")
def list_appliances():
    return app_state.state["storage"].list_appliances()


@router.post("/appliances")
def add_appliance(body: AddApplianceRequest):
    appliance_id = app_state.state["storage"].add_appliance(body.model_dump())
    return {"appliance_id": appliance_id}


@router.post("/appliances/{appliance_id}/service")
def log_service(appliance_id: str, body: LogServiceRequest):
    """Marks the appliance serviced. Recomputes and persists `status`
    immediately (same precedent as submit_maintenance_request) rather than
    leaving a stale SERVICE_DUE/REPAIR_REQUESTED/REPLACE_REQUESTED label
    sitting there until the next check_due_maintenance run — the maintenance
    was just done, the household shouldn't have to re-check to see that."""
    resolved_date = body.service_date or date.today().isoformat()
    storage = app_state.state["storage"]
    try:
        storage.update_appliance(appliance_id, last_serviced_date=resolved_date)
    except KeyError:
        raise HTTPException(status_code=404, detail="appliance not found")

    appliance = storage.get_appliance(appliance_id)
    reference = storage.get_reference_data(appliance["appliance_type"])
    status = compute_status(appliance, reference, date.today()) if reference else None
    if status:
        storage.update_appliance(appliance_id, status=status)

    return {"appliance_id": appliance_id, "last_serviced_date": resolved_date, "status": status}


@router.patch("/appliances/{appliance_id}")
def update_appliance(appliance_id: str, body: UpdateApplianceRequest):
    """Edit install_date and/or last_serviced_date on an existing appliance
    — lets the dashboard's scenario simulator age an appliance or back-date
    (or clear) its last service without deleting and re-adding it."""
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="no fields to update")
    storage = app_state.state["storage"]
    try:
        storage.update_appliance(appliance_id, **fields)
    except KeyError:
        raise HTTPException(status_code=404, detail="appliance not found")
    return storage.get_appliance(appliance_id)


@router.delete("/appliances/{appliance_id}")
def delete_appliance(appliance_id: str):
    try:
        app_state.state["storage"].delete_appliance(appliance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="appliance not found")
    return {"appliance_id": appliance_id, "deleted": True}
