"""Pydantic request bodies for the FastAPI service (api.py)."""

from pydantic import BaseModel


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
