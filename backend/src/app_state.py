"""Shared FastAPI application state.

storage/vector_store/notifier are built once in api.py's lifespan handler
(the expensive, stateful pieces — DB connections) and read from here by
every router — pulled out of api.py so router modules can use them without
importing the app itself, which would be a circular import.
"""

from agents.orchestrator import build_orchestrator
from runtime import setup_telemetry

CHECK_PROMPT = "Check if any of my appliances need maintenance."

telemetry = setup_telemetry()
state: dict = {}


def flush_telemetry() -> None:
    # Not correctness-critical here (unlike the cron script, this process
    # stays alive and the batch timer would flush eventually) — just makes
    # spans show up in Honeycomb immediately after a check, rather than
    # trailing behind the WebSocket trace by the batch interval.
    if telemetry:
        telemetry.tracer_provider.force_flush()


def build_agent():
    # Fresh Agent per call, not a shared instance: Strands agents carry
    # conversation history and raise ConcurrencyException if the same
    # instance is invoked concurrently — both wrong for a multi-request API.
    # Storage/vector_store are still built once in lifespan and shared here;
    # notifier is stateless.
    return build_orchestrator(
        state["storage"], vector_store=state["vector_store"], notifier=state["notifier"]
    )
