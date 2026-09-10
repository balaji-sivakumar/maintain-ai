"""Home Maintenance Agent (orchestrator) — Day 2/3/4 scope.

Structured reference table first, RAG fallback second (Day 4, via an
optional vector_store — pass None to stay structured-table-only, e.g. if
Chroma isn't set up for a given run). The Cost Estimator sub-agent (Day 3)
is invoked via the estimate_cost tool, an Agent-as-Tool call.
"""

from datetime import date
from typing import Optional

from strands import Agent

from interfaces.storage import Storage
from interfaces.vector_store import VectorStore
from model import get_model
from tools.appliance_tools import create_orchestrator_tools

SYSTEM_PROMPT = """You are Maintain-AI, a quiet background agent that tracks a household's \
appliances and their maintenance schedules.

Behavior rules:
- Stay silent (respond with nothing more than a brief confirmation) for routine actions \
like adding an appliance or logging a completed service.
- When asked to check on maintenance, call check_due_maintenance. If it returns an empty \
list, say nothing is due — do not invent reminders.
- For every appliance check_due_maintenance returns due or overdue, call draft_service_reminder \
AND estimate_cost for that appliance, then present both the reminder and the repair-vs-replace \
recommendation together.
- Never fabricate service intervals or costs — always use lookup_maintenance_interval and \
estimate_cost for that data, and say so plainly if a tool returns nothing.
"""


def build_orchestrator(
    storage: Storage, vector_store: Optional[VectorStore] = None, today: date | None = None
) -> Agent:
    return Agent(
        model=get_model(),
        tools=create_orchestrator_tools(storage, vector_store=vector_store, today=today),
        system_prompt=SYSTEM_PROMPT,
    )
