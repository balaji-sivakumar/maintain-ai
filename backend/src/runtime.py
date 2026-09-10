"""Runtime wiring shared by the FastAPI service and the cron script.

Picks concrete Storage/VectorStore implementations based on what's
configured in the environment — DATABASE_URL present means Neon, otherwise
falls back to LocalJsonStorage; OPENAI_API_KEY present means Chroma RAG is
available, otherwise the orchestrator runs structured-table-only. This is
the one place that decides "deployed" vs "local" so api.py and the cron
script never diverge on it.
"""

import os
from typing import Optional

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
