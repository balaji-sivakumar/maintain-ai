"""Ingest backend/data/manuals/*.txt into the Chroma vector store.

Requires OPENAI_API_KEY (used both for Chroma's embedding function and,
later, by the RAG extraction step). Not part of the automated test suite —
this is a one-off admin action per ARCHITECTURE.md's ingestion path, separate
from the real-time query path.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/ingest_manuals.py
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from impl.chroma_vector_store import ChromaVectorStore

MANUALS_DIR = Path(__file__).resolve().parents[1] / "data" / "manuals"


def main() -> None:
    vector_store = ChromaVectorStore()

    manual_paths = sorted(MANUALS_DIR.glob("*.txt"))
    if not manual_paths:
        print(f"No manuals found in {MANUALS_DIR}")
        return

    for path in manual_paths:
        appliance_type = path.stem
        text = path.read_text()
        vector_store.ingest(doc_id=appliance_type, text=text, metadata={"appliance_type": appliance_type})
        print(f"Ingested {appliance_type} ({len(text)} chars)")

    print(f"\nDone. {len(manual_paths)} manuals ingested into Chroma at data/chroma/.")


if __name__ == "__main__":
    main()
