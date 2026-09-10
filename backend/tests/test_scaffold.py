import pytest

from impl.local_storage import LocalJsonStorage
from model import get_model


def test_reference_table_loads_and_has_20_plus_appliances():
    storage = LocalJsonStorage()
    assert len(storage._reference) >= 20


def test_reference_lookup_hit_and_miss():
    storage = LocalJsonStorage()
    assert storage.get_reference_data("hvac_system")["service_interval_months"] == 12
    assert storage.get_reference_data("nonexistent_appliance") is None


def test_add_get_update_appliance(tmp_path):
    state_path = tmp_path / "local_state.json"
    storage = LocalJsonStorage(state_path=state_path)

    appliance_id = storage.add_appliance(
        {"appliance_type": "hvac_system", "brand": "Carrier", "install_date": "2015-06-01"}
    )
    assert storage.get_appliance(appliance_id)["brand"] == "Carrier"

    storage.update_appliance(appliance_id, last_serviced_date="2026-01-15")
    assert storage.get_appliance(appliance_id)["last_serviced_date"] == "2026-01-15"

    assert len(storage.list_appliances()) == 1


def test_delete_appliance(tmp_path):
    storage = LocalJsonStorage(state_path=tmp_path / "local_state.json")
    appliance_id = storage.add_appliance(
        {"appliance_type": "hvac_system", "brand": "Carrier", "install_date": "2015-06-01"}
    )

    storage.delete_appliance(appliance_id)

    assert storage.get_appliance(appliance_id) is None
    assert storage.list_appliances() == []
    with pytest.raises(KeyError):
        storage.delete_appliance(appliance_id)


def test_get_model_requires_api_key_for_openai(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        get_model()


def test_get_model_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "not-a-real-provider")
    with pytest.raises(ValueError):
        get_model()
