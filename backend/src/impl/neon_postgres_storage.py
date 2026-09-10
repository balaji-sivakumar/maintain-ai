"""Neon Postgres-backed Storage — Day 5 deployed implementation.

Same Storage contract as LocalJsonStorage (Stage A), so agent/tool code is
unaffected by which one is wired in. Appliance and reference-table records
are stored as JSONB blobs keyed by id/appliance_type, mirroring the
dict-shaped records LocalJsonStorage already used — no rigid column schema
to migrate as the appliance/reference shape evolves.
"""

import json
import os
import uuid
from pathlib import Path
from typing import Any, Optional

import psycopg
from psycopg.types.json import Jsonb

from interfaces.storage import Storage

# cwd-relative, not __file__-relative — see local_storage.py's DEFAULT_REFERENCE_PATH
# comment for why (this must resolve correctly from an installed wheel too).
DEFAULT_REFERENCE_SEED_PATH = Path.cwd() / "data" / "appliances.json"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reference_data (
    appliance_type TEXT PRIMARY KEY,
    data JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS appliances (
    id TEXT PRIMARY KEY,
    data JSONB NOT NULL
);
"""


class NeonPostgresStorage(Storage):
    def __init__(
        self,
        database_url: Optional[str] = None,
        reference_seed_path: Path = DEFAULT_REFERENCE_SEED_PATH,
    ):
        url = database_url or os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL is required for NeonPostgresStorage")

        self._conn = psycopg.connect(url, autocommit=True)
        self._conn.execute(_SCHEMA)
        self._seed_reference_data_if_empty(reference_seed_path)

    def _seed_reference_data_if_empty(self, reference_seed_path: Path) -> None:
        (count,) = self._conn.execute("SELECT count(*) FROM reference_data").fetchone()
        if count > 0:
            return

        seed_data = json.loads(reference_seed_path.read_text())
        for appliance_type, data in seed_data.items():
            self.cache_reference_data(appliance_type, data)

    def get_reference_data(self, appliance_type: str) -> Optional[dict[str, Any]]:
        row = self._conn.execute(
            "SELECT data FROM reference_data WHERE appliance_type = %s", (appliance_type,)
        ).fetchone()
        return row[0] if row else None

    def cache_reference_data(self, appliance_type: str, data: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO reference_data (appliance_type, data) VALUES (%s, %s) "
            "ON CONFLICT (appliance_type) DO UPDATE SET data = excluded.data",
            (appliance_type, Jsonb(data)),
        )

    def add_appliance(self, appliance: dict[str, Any]) -> str:
        appliance_id = str(uuid.uuid4())
        record = {**appliance, "id": appliance_id}
        self._conn.execute(
            "INSERT INTO appliances (id, data) VALUES (%s, %s)", (appliance_id, Jsonb(record))
        )
        return appliance_id

    def list_appliances(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT data FROM appliances").fetchall()
        return [row[0] for row in rows]

    def get_appliance(self, appliance_id: str) -> Optional[dict[str, Any]]:
        row = self._conn.execute(
            "SELECT data FROM appliances WHERE id = %s", (appliance_id,)
        ).fetchone()
        return row[0] if row else None

    def update_appliance(self, appliance_id: str, **fields: Any) -> None:
        existing = self.get_appliance(appliance_id)
        if existing is None:
            raise KeyError(f"No tracked appliance with id {appliance_id!r}")

        updated = {**existing, **fields}
        self._conn.execute(
            "UPDATE appliances SET data = %s WHERE id = %s", (Jsonb(updated), appliance_id)
        )
