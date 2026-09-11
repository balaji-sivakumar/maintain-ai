"""Runtime wiring shared by the FastAPI service and the cron script.

Picks concrete Storage/VectorStore/Notifier implementations based on what's
configured in the environment — DATABASE_URL present means Neon, otherwise
falls back to LocalJsonStorage; OPENAI_API_KEY present means Chroma RAG is
available, otherwise the orchestrator runs structured-table-only;
RESEND_API_KEY+NOTIFY_EMAIL present means real emails, otherwise
notifications just print to stdout. This is the one place that decides
"deployed" vs "local" so api.py and the cron script never diverge on it.
"""

import os
from typing import Optional

from interfaces.notifier import Notifier
from interfaces.storage import Storage
from interfaces.vector_store import VectorStore


def build_storage() -> Storage:
    if os.environ.get("DATABASE_URL"):
        from impl.neon_postgres_storage import NeonPostgresStorage

        return NeonPostgresStorage()

    from impl.local_storage import LocalJsonStorage

    return LocalJsonStorage()


def build_vector_store() -> Optional[VectorStore]:
    if not os.environ.get("OPENAI_API_KEY"):
        return None

    from impl.chroma_vector_store import ChromaVectorStore

    return ChromaVectorStore()


def build_notifier() -> Notifier:
    if os.environ.get("RESEND_API_KEY") and os.environ.get("NOTIFY_EMAIL"):
        from impl.resend_notifier import ResendNotifier

        return ResendNotifier()

    from impl.console_notifier import ConsoleNotifier

    return ConsoleNotifier()


def setup_telemetry() -> Optional["StrandsTelemetry"]:  # noqa: F821
    """Wires Strands' already-running internal OTel instrumentation to an
    OTLP backend (e.g. Honeycomb) — Strands emits spans for every chat turn,
    tool call, and event-loop cycle regardless of this call; it just gives
    them somewhere to go. No-op (returns None) if OTEL_EXPORTER_OTLP_ENDPOINT
    isn't set, so local dev/tests stay quiet (no verbose span JSON) by default.

    Returns the StrandsTelemetry instance so short-lived callers (the cron
    script) can force-flush its BatchSpanProcessor before exiting — the
    processor flushes on a background timer, which a process that exits
    immediately after one check would otherwise race and silently drop.
    """
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return None

    from strands.telemetry import StrandsTelemetry

    return StrandsTelemetry().setup_otlp_exporter()
