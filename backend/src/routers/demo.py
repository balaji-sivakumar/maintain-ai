"""Simulator/demo helpers — seed a fixed set of scenarios, or wipe tracked
state entirely, for exercising the dashboard without manual data entry.
"""

from datetime import date

from fastapi import APIRouter

import app_state

router = APIRouter()

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


@router.post("/demo/seed")
def seed_demo_data():
    """Clears tracked appliances and pending confirmations, then adds a
    fixed set of demo scenarios."""
    storage = app_state.state["storage"]
    for appliance in storage.list_appliances():
        storage.delete_appliance(appliance["id"])
    _clear_confirmations(storage)

    seeded = []
    for appliance in DEMO_APPLIANCES:
        appliance_id = storage.add_appliance(appliance)
        seeded.append({**appliance, "id": appliance_id})
    return {"seeded": seeded}


@router.post("/demo/reset")
def reset_demo_data():
    """Deletes all tracked appliances and any pending confirmations."""
    storage = app_state.state["storage"]
    ids = [a["id"] for a in storage.list_appliances()]
    for appliance_id in ids:
        storage.delete_appliance(appliance_id)
    _clear_confirmations(storage)
    return {"deleted": len(ids)}
