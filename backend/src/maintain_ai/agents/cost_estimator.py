"""Cost Estimator Agent (sub-agent) — Day 3 scope.

Invoked by the orchestrator as an Agent-as-Tool call; never talks to the
user directly.
"""

from datetime import date

from strands import Agent

from maintain_ai.interfaces.storage import Storage
from maintain_ai.model import get_model
from maintain_ai.tools.cost_tools import create_cost_estimator_tools

SYSTEM_PROMPT = """You are the Cost Estimator sub-agent for Maintain-AI. You are called by \
another agent, not the end user directly.

Given an appliance type and install date:
1. Call recommend_repair_or_replace to get the deterministic recommendation and reasoning.
2. Present the recommendation (repair or replace) with the cost figures and reasoning already \
computed by the tool — never invent your own cost numbers or override the tool's recommendation.
3. Keep the response short: the recommendation, the two cost figures, and one sentence of reasoning.
"""


def build_cost_estimator(storage: Storage, today: date | None = None) -> Agent:
    return Agent(
        model=get_model(),
        tools=create_cost_estimator_tools(storage, today=today),
        system_prompt=SYSTEM_PROMPT,
    )
