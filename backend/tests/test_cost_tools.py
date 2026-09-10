from datetime import date

from tools.cost_tools import create_cost_estimator_tools


def _make_tools(storage, today=None):
    return create_cost_estimator_tools(storage, today=today)


def test_estimate_costs_from_real_reference_table(isolated_storage):
    estimate_repair_cost, estimate_replacement_cost, _ = _make_tools(isolated_storage)

    repair = estimate_repair_cost("hvac_system")
    assert repair["repair_cost_range_usd"] == [150, 1200]
    assert repair["repair_cost_midpoint_usd"] == 675

    replacement = estimate_replacement_cost("hvac_system")
    assert replacement["replacement_cost_range_usd"] == [4000, 12000]

    assert estimate_repair_cost("not_a_real_type") is None
    assert estimate_replacement_cost("not_a_real_type") is None


def test_recommends_repair_when_young_and_cheap_to_fix(isolated_storage):
    _, _, recommend_repair_or_replace = _make_tools(isolated_storage, today=date(2026, 1, 1))
    isolated_storage.cache_reference_data(
        "test_widget",
        {
            "typical_lifespan_years": 10,
            "repair_cost_range_usd": [100, 200],
            "replacement_cost_range_usd": [1000, 2000],
        },
    )

    result = recommend_repair_or_replace("test_widget", "2025-01-01")  # 1 year old

    assert result["recommendation"] == "repair"


def test_recommends_replace_when_near_end_of_life(isolated_storage):
    _, _, recommend_repair_or_replace = _make_tools(isolated_storage, today=date(2026, 1, 1))
    isolated_storage.cache_reference_data(
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


def test_recommends_replace_when_repair_cost_close_to_replacement(isolated_storage):
    _, _, recommend_repair_or_replace = _make_tools(isolated_storage, today=date(2026, 1, 1))
    isolated_storage.cache_reference_data(
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


def test_recommend_repair_or_replace_unknown_type(isolated_storage):
    _, _, recommend_repair_or_replace = _make_tools(isolated_storage)
    assert recommend_repair_or_replace("not_a_real_type", "2020-01-01") is None
