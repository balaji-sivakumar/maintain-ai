"""Chroma-backed VectorStore — Day 4 RAG fallback over appliance manuals.

Uses Chroma Cloud when CHROMA_API_KEY is set (the deployed path — persists
independently of Railway's ephemeral filesystem), otherwise falls back to
chromadb's local PersistentClient for local dev. Either way the
query()/ingest() contract is identical, so callers never know which backend
is in play.
"""

import os
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.utils import embedding_functions

from interfaces.vector_store import VectorStore

# cwd-relative, not __file__-relative — see local_storage.py's DEFAULT_REFERENCE_PATH
# comment for why. Only used for the local PersistentClient fallback.
DEFAULT_PERSIST_PATH = Path(os.environ.get("CHROMA_PERSIST_PATH", Path.cwd() / "data" / "chroma"))
COLLECTION_NAME = "appliance_manuals"


class ChromaVectorStore(VectorStore):
    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        chroma_api_key: Optional[str] = None,
        chroma_tenant: Optional[str] = None,
        chroma_database: Optional[str] = None,
        persist_path: Path = DEFAULT_PERSIST_PATH,
    ):
        api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for Chroma's embedding function")

        cloud_api_key = chroma_api_key or os.environ.get("CHROMA_API_KEY")
        if cloud_api_key:
            client = chromadb.CloudClient(
                api_key=cloud_api_key,
                tenant=chroma_tenant or os.environ.get("CHROMA_TENANT"),
                database=chroma_database or os.environ.get("CHROMA_DATABASE"),
            )
        else:
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
