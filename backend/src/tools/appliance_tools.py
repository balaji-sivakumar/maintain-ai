"""Orchestrator tools: add_appliance, check_due_maintenance, log_completed_service,
lookup_maintenance_interval, draft_service_reminder (Day 2), estimate_cost, which
delegates to the Cost Estimator sub-agent (Day 3, Agent-as-Tool pattern), the
Day 4 RAG fallback in lookup_maintenance_interval, and send_notification (Day 5).

Built as a factory (`create_orchestrator_tools`) so tools close over concrete
Storage/VectorStore/Notifier implementations without the Strands Agent needing
to know which ones — matches the pluggable-interface design in ARCHITECTURE.md.
"""

from datetime import date
from typing import Callable, Optional

from strands import tool

from dates import add_months, parse_date
from interfaces.notifier import Notifier
from interfaces.storage import Storage
from interfaces.vector_store import VectorStore


def create_orchestrator_tools(
    storage: Storage,
    vector_store: Optional[VectorStore] = None,
    extract_reference_data: Optional[Callable[[str, list[str]], Optional[dict]]] = None,
    notifier: Optional[Notifier] = None,
    today: date | None = None,
) -> list:
    def _today() -> date:
        return today or date.today()

    def _extract(appliance_type: str, excerpts: list[str]) -> Optional[dict]:
        if extract_reference_data is not None:
            return extract_reference_data(appliance_type, excerpts)
        from rag import extract_reference_data as default_extract_reference_data

        return default_extract_reference_data(appliance_type, excerpts)

    def _lookup_reference(appliance_type: str) -> Optional[dict]:
        """Structured table first, RAG fallback second — the same logic the
        lookup_maintenance_interval tool exposes, reused internally so
        check_due_maintenance and draft_service_reminder also pick up
        RAG-only appliance types."""
        reference = storage.get_reference_data(appliance_type)
        if reference:
            return reference

        if not vector_store:
            return None

        excerpts = vector_store.query(appliance_type)
        if not excerpts:
            return None

        extracted = _extract(appliance_type, excerpts)
        if extracted:
            storage.cache_reference_data(appliance_type, extracted)
        return extracted

    @tool
    def add_appliance(appliance_type: str, brand: str, model: str, install_date: str) -> dict:
        """Register a new appliance to track.

        Args:
            appliance_type: Reference table key, e.g. "hvac_system" or "water_heater_tank".
            brand: Manufacturer brand name.
            model: Manufacturer model number.
            install_date: Installation date as YYYY-MM-DD.
        """
        appliance_id = storage.add_appliance(
            {
                "appliance_type": appliance_type,
                "brand": brand,
                "model": model,
                "install_date": install_date,
            }
        )
        return {"appliance_id": appliance_id}

    @tool
    def lookup_maintenance_interval(appliance_type: str) -> dict | None:
        """Look up service interval and cost range data for an appliance type.

        Checks the structured reference table first. On a miss, falls back to
        RAG over appliance manuals (if a vector store is configured) and
        caches a successful extraction back into the reference table so the
        same lookup skips RAG next time. Returns None if nothing is found
        either way.
        """
        return _lookup_reference(appliance_type)

    @tool
    def check_due_maintenance() -> list[dict]:
        """Return only the tracked appliances that are due or overdue for service.

        An empty list means nothing is due right now — stay silent in that case.
        """
        due = []
        for appliance in storage.list_appliances():
            reference = _lookup_reference(appliance["appliance_type"])
            if not reference or not reference.get("service_interval_months"):
                continue

            last_service_str = appliance.get("last_serviced_date") or appliance["install_date"]
            last_service_date = parse_date(last_service_str)
            next_due_date = add_months(last_service_date, reference["service_interval_months"])

            if _today() >= next_due_date:
                due.append(
                    {
                        "appliance_id": appliance["id"],
                        "appliance_type": appliance["appliance_type"],
                        "brand": appliance["brand"],
                        "model": appliance["model"],
                        "last_serviced_date": last_service_str,
                        "due_since": next_due_date.isoformat(),
                        "reference": reference,
                    }
                )
        return due

    @tool
    def draft_service_reminder(appliance_id: str) -> str:
        """Compose a human-readable maintenance reminder for a tracked appliance."""
        appliance = storage.get_appliance(appliance_id)
        if not appliance:
            return f"No tracked appliance found with id {appliance_id}."

        reference = _lookup_reference(appliance["appliance_type"])
        display_name = reference.get("display_name", appliance["appliance_type"]) if reference else appliance["appliance_type"]

        return (
            f"Your {appliance['brand']} {appliance['model']} ({display_name}) is due for service. "
            f"Recommended interval: every {reference['service_interval_months']} months."
            if reference
            else f"Your {appliance['brand']} {appliance['model']} is due for service."
        )

    @tool
    def log_completed_service(appliance_id: str, service_date: str | None = None) -> dict:
        """Record that an appliance was serviced.

        Args:
            appliance_id: The tracked appliance's id.
            service_date: Date serviced, as YYYY-MM-DD. Defaults to today.
        """
        resolved_date = service_date or _today().isoformat()
        storage.update_appliance(appliance_id, last_serviced_date=resolved_date)
        return {"appliance_id": appliance_id, "last_serviced_date": resolved_date}

    @tool
    def estimate_cost(appliance_id: str) -> str:
        """Get a repair-vs-replace cost recommendation for a tracked appliance.

        Delegates to the Cost Estimator sub-agent — call this for appliances
        that check_due_maintenance flagged as due or overdue.
        """
        from agents.cost_estimator import build_cost_estimator

        appliance = storage.get_appliance(appliance_id)
        if not appliance:
            return f"No tracked appliance found with id {appliance_id}."

        cost_estimator = build_cost_estimator(storage, today=today)
        result = cost_estimator(
            f"Recommend repair or replace for appliance_type={appliance['appliance_type']!r}, "
            f"install_date={appliance['install_date']!r}."
        )
        return str(result)

    @tool
    def send_notification(subject: str, message: str) -> str:
        """Send the household an email notification (only when something is
        actually due — never for routine/no-op checks).

        Args:
            subject: Short email subject line.
            message: Full notification body — the reminders and cost
                recommendations gathered for the due appliance(s).
        """
        if notifier is None:
            return "No notifier configured; notification skipped."
        notifier.send(subject, message)
        return "Notification sent."

    return [
        add_appliance,
        lookup_maintenance_interval,
        check_due_maintenance,
        draft_service_reminder,
        log_completed_service,
        estimate_cost,
        send_notification,
    ]
