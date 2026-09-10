"""Manual Day 4 demo: RAG fallback for an appliance type not in the
structured table, backed by the manuals ingested via ingest_manuals.py.

Requires OPENAI_API_KEY (for the model, the RAG extraction call, and
Chroma's embedding function) and that you've already run:
    python scripts/ingest_manuals.py

Usage:
    cd backend && source .venv/bin/activate
    python scripts/demo_day4.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import load_dotenv

load_dotenv()

from agents.orchestrator import build_orchestrator
from impl.chroma_vector_store import ChromaVectorStore
from impl.local_storage import LocalJsonStorage


def main() -> None:
    vector_store = ChromaVectorStore()  # reads data/chroma/, ingested manuals

    with TemporaryDirectory() as tmp:
        storage = LocalJsonStorage(state_path=Path(tmp) / "local_state.json")
        agent = build_orchestrator(storage, vector_store=vector_store)

        print("=== Add an EV charger — 'ev_charger' isn't in appliances.json ===")
        agent(
            "Add an EV charger: brand ChargePoint, model Home Flex, "
            "appliance_type ev_charger, installed on 2015-01-01."
        )

        print("\n\n=== Check maintenance — expect a RAG-derived reminder + cost estimate ===")
        agent("Check if any of my appliances need maintenance.")
        print()

        cached = storage.get_reference_data("ev_charger")
        print("=== Cache-back check: ev_charger now in this run's structured table ===")
        print(cached)


if __name__ == "__main__":
    main()
