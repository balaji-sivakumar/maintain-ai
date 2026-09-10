"""Manual Day 3 demo: full loop including the Cost Estimator sub-agent.

Requires OPENAI_API_KEY in the environment (or backend/.env). Not part of the
automated test suite since it makes real model calls.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/demo_day3.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import load_dotenv

load_dotenv()

from agents.orchestrator import build_orchestrator
from impl.local_storage import LocalJsonStorage


def main() -> None:
    with TemporaryDirectory() as tmp:
        storage = LocalJsonStorage(state_path=Path(tmp) / "local_state.json")
        agent = build_orchestrator(storage)

        print("=== Add a water heater installed 11 years ago (near its 10yr lifespan) ===")
        agent(
            "Add a water heater: brand Rheem, model Performance Plus, "
            "appliance_type water_heater_tank, installed on 2015-01-01."
        )

        print("\n\n=== Check maintenance — expect a reminder AND a repair-vs-replace call ===")
        agent("Check if any of my appliances need maintenance.")
        print()


if __name__ == "__main__":
    main()
