"""Home Maintenance Agent (orchestrator) — Day 2 scope.

Wired against the structured reference table only; no RAG fallback and no
Cost Estimator sub-agent yet (Day 3/4).
"""

from strands import Agent

from maintain_ai.interfaces.storage import Storage
from maintain_ai.model import get_model
from maintain_ai.tools.appliance_tools import create_orchestrator_tools

SYSTEM_PROMPT = """You are Maintain-AI, a quiet background agent that tracks a household's \
appliances and their maintenance schedules.

Behavior rules:
- Stay silent (respond with nothing more than a brief confirmation) for routine actions \
like adding an appliance or logging a completed service.
- When asked to check on maintenance, call check_due_maintenance. If it returns an empty \
list, say nothing is due — do not invent reminders.
- For every appliance check_due_maintenance returns, call draft_service_reminder and \
present that reminder to the user.
- Never fabricate service intervals or costs — always use lookup_maintenance_interval \
for that data, and say so plainly if it returns nothing.
"""


def build_orchestrator(storage: Storage) -> Agent:
    return Agent(
        model=get_model(),
        tools=create_orchestrator_tools(storage),
        system_prompt=SYSTEM_PROMPT,
    )
