"""FastAPI service — Day 5 deployment target for Railway.

Wraps the orchestrator built in agents/orchestrator.py behind a small HTTP
API: manual add/update endpoints, plus /check, which the Railway cron
service (scripts/cron_check.py) also drives for the daily trigger.
"""

from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agents.orchestrator import build_orchestrator
from runtime import build_storage, build_vector_store

_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = build_storage()
    vector_store = build_vector_store()
    _state["storage"] = storage
    _state["agent"] = build_orchestrator(storage, vector_store=vector_store)
    yield
    _state.clear()


app = FastAPI(title="Maintain-AI", lifespan=lifespan)


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


@app.post("/check")
def check_maintenance():
    """Runs the orchestrator's daily maintenance check.

    Called manually via the API, or by the Railway cron service.
    """
    result = _state["agent"]("Check if any of my appliances need maintenance.")
    return {"response": str(result)}
