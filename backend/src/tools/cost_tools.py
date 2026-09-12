"""Cost Estimator sub-agent tools (Day 3 scope): estimate_repair_cost,
estimate_replacement_cost, recommend_repair_or_replace.

Structured data only — pulls ranges from the same reference table used by
the orchestrator (backend/data/appliances.json). No RAG fallback yet (Day 4).
"""

from datetime import date

from strands import tool

from core.dates import age_years, parse_date
from interfaces.storage import Storage

# "50% rule": if repair cost is at least half of replacement cost, replacing
# is usually the better value — a common rule of thumb for household repairs.
REPAIR_TO_REPLACE_COST_RATIO_THRESHOLD = 0.5

# Consider an appliance near end-of-life once it's used up this fraction of
# its typical lifespan, even if the cost ratio alone wouldn't tip it.
END_OF_LIFE_FRACTION = 0.9


def _cost_midpoint(cost_range: list[float]) -> float:
    return sum(cost_range) / len(cost_range)


def create_cost_estimator_tools(storage: Storage, today: date | None = None) -> list:
    def _today() -> date:
        return today or date.today()

    @tool
    def estimate_repair_cost(appliance_type: str) -> dict | None:
        """Estimate the repair cost range for an appliance type from the reference table."""
        reference = storage.get_reference_data(appliance_type)
        if not reference:
            return None
        return {
            "repair_cost_range_usd": reference["repair_cost_range_usd"],
            "repair_cost_midpoint_usd": _cost_midpoint(reference["repair_cost_range_usd"]),
        }

    @tool
    def estimate_replacement_cost(appliance_type: str) -> dict | None:
        """Estimate the replacement cost range for an appliance type from the reference table."""
        reference = storage.get_reference_data(appliance_type)
        if not reference:
            return None
        return {
            "replacement_cost_range_usd": reference["replacement_cost_range_usd"],
            "replacement_cost_midpoint_usd": _cost_midpoint(reference["replacement_cost_range_usd"]),
        }

    @tool
    def recommend_repair_or_replace(appliance_type: str, install_date: str) -> dict | None:
        """Recommend repair or replace for an appliance, with the reasoning behind it.

        Args:
            appliance_type: Reference table key, e.g. "hvac_system".
            install_date: Installation date as YYYY-MM-DD, used to compute age.
        """
        reference = storage.get_reference_data(appliance_type)
        if not reference:
            return None

        age = age_years(parse_date(install_date), _today())
        lifespan = reference.get("typical_lifespan_years")
        repair_mid = _cost_midpoint(reference["repair_cost_range_usd"])
        replace_mid = _cost_midpoint(reference["replacement_cost_range_usd"])

        cost_ratio = repair_mid / replace_mid if replace_mid else 0
        near_end_of_life = bool(lifespan) and age >= lifespan * END_OF_LIFE_FRACTION
        poor_cost_ratio = cost_ratio >= REPAIR_TO_REPLACE_COST_RATIO_THRESHOLD

        recommendation = "replace" if (near_end_of_life or poor_cost_ratio) else "repair"

        reasons = []
        if near_end_of_life:
            reasons.append(
                f"appliance is {age:.1f} years old, at or beyond {END_OF_LIFE_FRACTION:.0%} "
                f"of its {lifespan}-year typical lifespan"
            )
        if poor_cost_ratio:
            reasons.append(
                f"repair cost (~${repair_mid:.0f}) is at least "
                f"{REPAIR_TO_REPLACE_COST_RATIO_THRESHOLD:.0%} of replacement cost (~${replace_mid:.0f})"
            )
        if not reasons:
            reasons.append(
                f"appliance is {age:.1f} years old (well within its {lifespan}-year lifespan) "
                f"and repair cost (~${repair_mid:.0f}) is well below replacement cost (~${replace_mid:.0f})"
            )

        return {
            "recommendation": recommendation,
            "age_years": round(age, 1),
            "repair_cost_midpoint_usd": repair_mid,
            "replacement_cost_midpoint_usd": replace_mid,
            "reasons": reasons,
        }

    return [estimate_repair_cost, estimate_replacement_cost, recommend_repair_or_replace]
