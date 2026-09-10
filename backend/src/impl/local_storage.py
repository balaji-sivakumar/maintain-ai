"""Local JSON-file storage — Stage A implementation of the Storage interface.

Swap for a DynamoDB or Railway Postgres implementation in Stage B without
touching any agent/tool code, since both would satisfy the same interface.
"""

import json
import uuid
from pathlib import Path
from typing import Any, Optional

from interfaces.storage import Storage

# Resolved against the process's working directory, not __file__ — in a real
# installed package (e.g. deployed on Railway), __file__ points into
# site-packages, which has no data/ directory. Every entrypoint (pytest,
# scripts/, and Railway's configured Root Directory) runs with cwd at
# backend/, so this resolves correctly everywhere it's actually used.
DEFAULT_REFERENCE_PATH = Path.cwd() / "data" / "appliances.json"
DEFAULT_STATE_PATH = Path.cwd() / "data" / "local_state.json"


class LocalJsonStorage(Storage):
    def __init__(
        self,
        reference_path: Path = DEFAULT_REFERENCE_PATH,
        state_path: Path = DEFAULT_STATE_PATH,
    ):
        self._reference_path = reference_path
        self._state_path = state_path
        self._reference: dict[str, Any] = json.loads(reference_path.read_text())
        self._state: dict[str, Any] = (
            json.loads(state_path.read_text()) if state_path.exists() else {}
        )

    def _persist_state(self) -> None:
        self._state_path.write_text(json.dumps(self._state, indent=2, default=str))

    def get_reference_data(self, appliance_type: str) -> Optional[dict[str, Any]]:
        return self._reference.get(appliance_type)

    def cache_reference_data(self, appliance_type: str, data: dict[str, Any]) -> None:
        self._reference[appliance_type] = data
        self._reference_path.write_text(json.dumps(self._reference, indent=2, default=str))

    def add_appliance(self, appliance: dict[str, Any]) -> str:
        appliance_id = str(uuid.uuid4())
        self._state[appliance_id] = {**appliance, "id": appliance_id}
        self._persist_state()
        return appliance_id

    def list_appliances(self) -> list[dict[str, Any]]:
        return list(self._state.values())

    def get_appliance(self, appliance_id: str) -> Optional[dict[str, Any]]:
        return self._state.get(appliance_id)

    def update_appliance(self, appliance_id: str, **fields: Any) -> None:
        if appliance_id not in self._state:
            raise KeyError(f"No tracked appliance with id {appliance_id!r}")
        self._state[appliance_id].update(fields)
        self._persist_state()

    def delete_appliance(self, appliance_id: str) -> None:
        if appliance_id not in self._state:
            raise KeyError(f"No tracked appliance with id {appliance_id!r}")
        del self._state[appliance_id]
        self._persist_state()
