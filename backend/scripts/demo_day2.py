"""Manual Day 2 demo: run the orchestrator against mock appliance data.

Requires OPENAI_API_KEY in the environment (or backend/.env). Not part of the
automated test suite since it makes real model calls.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/demo_day2.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import load_dotenv

load_dotenv()

from maintain_ai.agents.orchestrator import build_orchestrator
from maintain_ai.impl.local_storage import LocalJsonStorage


def main() -> None:
    with TemporaryDirectory() as tmp:
        storage = LocalJsonStorage(state_path=Path(tmp) / "local_state.json")
        agent = build_orchestrator(storage)

        print("\n=== Scenario 1: no appliances tracked yet (expect silence) ===")
        print(agent("Check if any of my appliances need maintenance."))

        print("\n=== Scenario 2: add a badly overdue HVAC system ===")
        print(
            agent(
                "Add an HVAC system: brand Carrier, model Infinity, "
                "appliance_type hvac_system, installed on 2024-01-01."
            )
        )

        print("\n=== Scenario 3: check again (expect a reminder) ===")
        print(agent("Check if any of my appliances need maintenance."))


if __name__ == "__main__":
    main()
