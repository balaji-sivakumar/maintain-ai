"""Home Maintenance Agent (orchestrator) — Day 2/3/4/5 scope.

Structured reference table first, RAG fallback second (Day 4, via an
optional vector_store — pass None to stay structured-table-only, e.g. if
Chroma isn't set up for a given run). The Cost Estimator sub-agent (Day 3)
is invoked via the estimate_cost tool, an Agent-as-Tool call. Email
notifications (Day 5) go out via the optional notifier — pass None to skip
them (e.g. local dev without Resend configured).
"""

from datetime import date
from typing import Optional

from strands import Agent

from interfaces.notifier import Notifier
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
list, say nothing is due — do not invent reminders, and do not send a notification.
- For every appliance check_due_maintenance returns due or overdue, call draft_service_reminder \
AND estimate_cost for that appliance, then present both the reminder and the repair-vs-replace \
recommendation together.
- If (and only if) at least one appliance is due or overdue, call send_notification once at the \
end with a subject line and a message summarizing every due appliance's reminder and cost \
recommendation gathered above — this is the actual notification that reaches the household, so \
don't skip it when something is due.
- Cost recommendations are advisory only — you are suggesting repair or replace, never booking, \
ordering, or purchasing anything on the user's behalf.
- Never fabricate service intervals or costs — always use lookup_maintenance_interval and \
estimate_cost for that data, and say so plainly if a tool returns nothing.
"""


def build_orchestrator(
    storage: Storage,
    vector_store: Optional[VectorStore] = None,
    notifier: Optional[Notifier] = None,
    today: date | None = None,
) -> Agent:
    return Agent(
        model=get_model(),
        tools=create_orchestrator_tools(
            storage, vector_store=vector_store, notifier=notifier, today=today
        ),
        system_prompt=SYSTEM_PROMPT,
    )
