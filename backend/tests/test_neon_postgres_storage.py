"""Live integration test against the real Neon database.

Skipped automatically when DATABASE_URL isn't set (e.g. in an environment
without deployment credentials) — this is the one exception to "no live
network calls in the test suite" because Postgres schema creation, JSONB
round-tripping, and the seed-on-empty logic are exactly the kind of thing
worth checking against the real thing rather than a mock. Cleans up every
row it writes.
"""

import os
import uuid

import pytest

from impl.neon_postgres_storage import NeonPostgresStorage

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="requires a live DATABASE_URL"
)


@pytest.fixture
def storage():
    return NeonPostgresStorage()


def test_reference_table_seeded_from_appliances_json(storage):
    reference = storage.get_reference_data("hvac_system")
    assert reference["service_interval_months"] == 12
    assert storage.get_reference_data("not_a_real_type") is None


def test_cache_reference_data_roundtrips_jsonb(storage):
    fake_type = f"test_widget_{uuid.uuid4().hex[:8]}"
    try:
        storage.cache_reference_data(
            fake_type,
            {"typical_lifespan_years": 5, "repair_cost_range_usd": [10, 20]},
        )
        assert storage.get_reference_data(fake_type)["typical_lifespan_years"] == 5
    finally:
        storage._conn.execute("DELETE FROM reference_data WHERE appliance_type = %s", (fake_type,))


def test_add_get_update_list_appliance_roundtrip(storage):
    appliance_id = storage.add_appliance(
        {"appliance_type": "hvac_system", "brand": "Carrier", "install_date": "2015-06-01"}
    )
    try:
        assert storage.get_appliance(appliance_id)["brand"] == "Carrier"

        storage.update_appliance(appliance_id, last_serviced_date="2026-01-15")
        assert storage.get_appliance(appliance_id)["last_serviced_date"] == "2026-01-15"

        assert any(a["id"] == appliance_id for a in storage.list_appliances())
    finally:
        storage._conn.execute("DELETE FROM appliances WHERE id = %s", (appliance_id,))


def test_update_unknown_appliance_raises(storage):
    with pytest.raises(KeyError):
        storage.update_appliance("does-not-exist", last_serviced_date="2026-01-01")


def test_delete_appliance(storage):
    appliance_id = storage.add_appliance(
        {"appliance_type": "hvac_system", "brand": "Carrier", "install_date": "2015-06-01"}
    )

    storage.delete_appliance(appliance_id)

    assert storage.get_appliance(appliance_id) is None
    with pytest.raises(KeyError):
        storage.delete_appliance(appliance_id)
