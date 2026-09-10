"""VectorStore interface — RAG fallback over appliance manuals.

Implementations: ChromaVectorStore (Day 4). Agent/tool code depends only on
this interface, matching the pluggable-interface design in ARCHITECTURE.md.
"""

from abc import ABC, abstractmethod
from typing import Any


class VectorStore(ABC):
    @abstractmethod
    def query(self, query_text: str, n_results: int = 3) -> list[str]:
        """Return the n_results most relevant manual excerpts for query_text.

        Returns an empty list on no match — callers should treat that the
        same as a structured-table miss with nothing to fall back on.
        """

    @abstractmethod
    def ingest(self, doc_id: str, text: str, metadata: dict[str, Any]) -> None:
        """Add or replace one manual excerpt in the store."""
