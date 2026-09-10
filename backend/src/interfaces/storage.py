"""Storage interface.

Holds two distinct concerns behind one contract:
- the structured reference table (service intervals, cost ranges per appliance type)
- per-household tracked appliance state (install dates, last-serviced dates)

Implementations: LocalJsonStorage (Stage A) -> DynamoDB (Option A) / Railway
Postgres (Option B). Agent tools depend only on this interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class Storage(ABC):
    @abstractmethod
    def get_reference_data(self, appliance_type: str) -> Optional[dict[str, Any]]:
        """Look up service interval / cost range data for an appliance type.

        Returns None on a miss, signaling callers to fall back to RAG.
        """

    @abstractmethod
    def cache_reference_data(self, appliance_type: str, data: dict[str, Any]) -> None:
        """Cache a RAG-derived answer back into the structured table."""

    @abstractmethod
    def add_appliance(self, appliance: dict[str, Any]) -> str:
        """Add a tracked appliance, returning its id."""

    @abstractmethod
    def list_appliances(self) -> list[dict[str, Any]]:
        """List all tracked appliances."""

    @abstractmethod
    def get_appliance(self, appliance_id: str) -> Optional[dict[str, Any]]:
        """Fetch one tracked appliance by id."""

    @abstractmethod
    def update_appliance(self, appliance_id: str, **fields: Any) -> None:
        """Update fields on a tracked appliance (e.g. last_serviced_date)."""

    @abstractmethod
    def delete_appliance(self, appliance_id: str) -> None:
        """Remove a tracked appliance (e.g. for demo/simulator reset)."""
