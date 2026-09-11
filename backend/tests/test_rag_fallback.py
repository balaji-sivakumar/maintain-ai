from datetime import date
from typing import Any

from interfaces.vector_store import VectorStore
from tools.appliance_tools import create_orchestrator_tools


class FakeVectorStore(VectorStore):
    """In-memory VectorStore stand-in — no Chroma/OpenAI calls in tests."""

    def __init__(self, corpus: dict[str, list[str]] | None = None):
        self._corpus = corpus or {}

    def query(self, query_text: str, n_results: int = 3) -> list[str]:
        return self._corpus.get(query_text, [])[:n_results]

    def ingest(self, doc_id: str, text: str, metadata: dict[str, Any]) -> None:
        self._corpus.setdefault(doc_id, []).append(text)


def _make_rag_tools(storage, vector_store, extract_reference_data, today=None):
    (
        add_appliance,
        lookup_maintenance_interval,
        check_due_maintenance,
        draft_service_reminder,
        log_completed_service,
        estimate_cost,
        send_notification,
        submit_maintenance_request,
    ) = create_orchestrator_tools(
        storage,
        vector_store=vector_store,
        extract_reference_data=extract_reference_data,
        today=today,
    )
    return add_appliance, lookup_maintenance_interval, check_due_maintenance


def test_structured_hit_never_touches_vector_store(isolated_storage):
    def boom(*args, **kwargs):
        raise AssertionError("extract_reference_data should not be called on a structured hit")

    vector_store = FakeVectorStore({"hvac_system": ["should not be read"]})
    _, lookup_maintenance_interval, _ = _make_rag_tools(isolated_storage, vector_store, boom)

    result = lookup_maintenance_interval("hvac_system")
    assert result["service_interval_months"] == 12


def test_rag_hit_extracts_and_caches(isolated_storage):
    calls = []

    def fake_extract(appliance_type, excerpts):
        calls.append((appliance_type, excerpts))
        return {
            "display_name": "EV Charger",
            "service_interval_months": 12,
            "typical_lifespan_years": 10,
            "repair_cost_range_usd": [150, 400],
            "replacement_cost_range_usd": [500, 2200],
            "notes": "extracted from manual",
        }

    vector_store = FakeVectorStore({"ev_charger": ["manual excerpt text"]})
    _, lookup_maintenance_interval, _ = _make_rag_tools(isolated_storage, vector_store, fake_extract)

    result = lookup_maintenance_interval("ev_charger")
    assert result["display_name"] == "EV Charger"
    assert len(calls) == 1

    # Second lookup should hit the cache, not call extract again.
    result_again = lookup_maintenance_interval("ev_charger")
    assert result_again["display_name"] == "EV Charger"
    assert len(calls) == 1

    assert isolated_storage.get_reference_data("ev_charger")["display_name"] == "EV Charger"


def test_rag_miss_with_no_excerpts_returns_none_without_extracting(isolated_storage):
    def boom(*args, **kwargs):
        raise AssertionError("extract_reference_data should not be called with no excerpts")

    vector_store = FakeVectorStore({})  # no excerpts for any appliance_type
    _, lookup_maintenance_interval, _ = _make_rag_tools(isolated_storage, vector_store, boom)

    assert lookup_maintenance_interval("nonexistent_widget") is None


def test_no_vector_store_falls_back_to_structured_only(isolated_storage):
    lookup_maintenance_interval = create_orchestrator_tools(isolated_storage)[1]

    assert lookup_maintenance_interval("nonexistent_widget") is None


def test_check_due_maintenance_picks_up_rag_only_appliance_type(isolated_storage):
    def fake_extract(appliance_type, excerpts):
        return {
            "display_name": "EV Charger",
            "service_interval_months": 12,
            "typical_lifespan_years": 10,
            "repair_cost_range_usd": [150, 400],
            "replacement_cost_range_usd": [500, 2200],
            "notes": "extracted from manual",
        }

    vector_store = FakeVectorStore({"ev_charger": ["manual excerpt text"]})
    add_appliance, _, check_due_maintenance = _make_rag_tools(
        isolated_storage, vector_store, fake_extract, today=date(2026, 1, 1)
    )
    add_appliance("ev_charger", "ChargePoint", "Home Flex", "2024-01-01")  # overdue

    due = check_due_maintenance()
    assert len(due) == 1
    assert due[0]["appliance_type"] == "ev_charger"
