"""Chroma-backed VectorStore — Day 4 RAG fallback over appliance manuals.

Self-hosted via chromadb's local PersistentClient (no separate server to
run), which satisfies the "self-hosted Chroma" leg of the Railway + Neon +
Chroma stack for a hackathon build. Swap for Chroma Cloud by changing only
how the client is constructed — the query()/ingest() contract doesn't change.
"""

import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils import embedding_functions

from interfaces.vector_store import VectorStore

# cwd-relative, not __file__-relative — see local_storage.py's DEFAULT_REFERENCE_PATH
# comment for why. On Railway this must be a mounted Volume path, or the
# ingested manuals are lost on every redeploy/restart (ephemeral filesystem).
DEFAULT_PERSIST_PATH = Path(os.environ.get("CHROMA_PERSIST_PATH", Path.cwd() / "data" / "chroma"))
COLLECTION_NAME = "appliance_manuals"


class ChromaVectorStore(VectorStore):
    def __init__(self, persist_path: Path = DEFAULT_PERSIST_PATH, openai_api_key: str | None = None):
        api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for Chroma's embedding function")

        client = chromadb.PersistentClient(path=str(persist_path))
        embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key, model_name="text-embedding-3-small"
        )
        self._collection = client.get_or_create_collection(
            name=COLLECTION_NAME, embedding_function=embedding_fn
        )

    def query(self, query_text: str, n_results: int = 3) -> list[str]:
        if self._collection.count() == 0:
            return []
        result = self._collection.query(
            query_texts=[query_text], n_results=min(n_results, self._collection.count())
        )
        return result["documents"][0] if result["documents"] else []

    def ingest(self, doc_id: str, text: str, metadata: dict[str, Any]) -> None:
        self._collection.upsert(ids=[doc_id], documents=[text], metadatas=[metadata])
