import shutil
from datetime import date

from impl.local_storage import DEFAULT_REFERENCE_PATH, LocalJsonStorage
from tools.cost_tools import create_cost_estimator_tools


def _make_tools(tmp_path, today=None):
    # Copy the reference table so tests using cache_reference_data() (a write)
    # never touch the real backend/data/appliances.json.
    reference_path = tmp_path / "appliances.json"
    shutil.copy(DEFAULT_REFERENCE_PATH, reference_path)

    storage = LocalJsonStorage(reference_path=reference_path, state_path=tmp_path / "local_state.json")
    estimate_repair_cost, estimate_replacement_cost, recommend_repair_or_replace = (
        create_cost_estimator_tools(storage, today=today)
    )
    return storage, estimate_repair_cost, estimate_replacement_cost, recommend_repair_or_replace


def test_estimate_costs_from_real_reference_table(tmp_path):
    _, estimate_repair_cost, estimate_replacement_cost, _ = _make_tools(tmp_path)

    repair = estimate_repair_cost("hvac_system")
    assert repair["repair_cost_range_usd"] == [150, 1200]
    assert repair["repair_cost_midpoint_usd"] == 675

    replacement = estimate_replacement_cost("hvac_system")
    assert replacement["replacement_cost_range_usd"] == [4000, 12000]

    assert estimate_repair_cost("not_a_real_type") is None
    assert estimate_replacement_cost("not_a_real_type") is None


def test_recommends_repair_when_young_and_cheap_to_fix(tmp_path):
    storage, _, _, recommend_repair_or_replace = _make_tools(tmp_path, today=date(2026, 1, 1))
    storage.cache_reference_data(
        "test_widget",
        {
            "typical_lifespan_years": 10,
            "repair_cost_range_usd": [100, 200],
            "replacement_cost_range_usd": [1000, 2000],
        },
    )

    result = recommend_repair_or_replace("test_widget", "2025-01-01")  # 1 year old

    assert result["recommendation"] == "repair"


def test_recommends_replace_when_near_end_of_life(tmp_path):
    storage, _, _, recommend_repair_or_replace = _make_tools(tmp_path, today=date(2026, 1, 1))
    storage.cache_reference_data(
        "test_widget",
        {
            "typical_lifespan_years": 10,
            "repair_cost_range_usd": [100, 200],
            "replacement_cost_range_usd": [1000, 2000],
        },
    )

    result = recommend_repair_or_replace("test_widget", "2016-01-01")  # 10 years old

    assert result["recommendation"] == "replace"
    assert any("lifespan" in reason for reason in result["reasons"])


def test_recommends_replace_when_repair_cost_close_to_replacement(tmp_path):
    storage, _, _, recommend_repair_or_replace = _make_tools(tmp_path, today=date(2026, 1, 1))
    storage.cache_reference_data(
        "test_widget",
        {
            "typical_lifespan_years": 20,
            "repair_cost_range_usd": [600, 600],
            "replacement_cost_range_usd": [1000, 1000],
        },
    )

    result = recommend_repair_or_replace("test_widget", "2025-01-01")  # young, but 60% cost ratio

    assert result["recommendation"] == "replace"
    assert any("repair cost" in reason for reason in result["reasons"])


def test_recommend_repair_or_replace_unknown_type(tmp_path):
    _, _, _, recommend_repair_or_replace = _make_tools(tmp_path)
    assert recommend_repair_or_replace("not_a_real_type", "2020-01-01") is None
