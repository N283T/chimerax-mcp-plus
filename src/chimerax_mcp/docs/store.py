"""ChromaDB-backed document store for ChimeraX docs."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

COLLECTION_NAME = "chimerax_docs"

# Singleton embedding function — the underlying sentence-transformer model
# (all-MiniLM-L6-v2) is loaded once on first use and reused for all queries.
_embedding_fn = DefaultEmbeddingFunction()

DEFAULT_DATA_DIR = Path.home().joinpath(".local", "share", "chimerax-mcp", "chroma")


class DocStore:
    """Vector store for ChimeraX documentation chunks."""

    def __init__(self, data_dir: Path | None = None) -> None:
        data_dir = data_dir or DEFAULT_DATA_DIR
        data_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(data_dir))
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=_embedding_fn,  # type: ignore[arg-type]  # chromadb generic variance
        )

    def add_documents(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[Mapping[str, Any]],
    ) -> None:
        """Add document chunks to the store."""
        self._collection.add(ids=ids, documents=documents, metadatas=metadatas)

    def search(
        self,
        query: str,
        category: str | None = None,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Semantic search for documents matching the query."""
        if self._collection.count() == 0:
            return []

        where = {"category": category} if category else None
        n = min(max_results, self._collection.count())

        results = self._collection.query(
            query_texts=[query],
            n_results=n,
            where=where,
        )

        docs = results["documents"]
        metas = results["metadatas"]
        if not docs or not metas:
            return []

        return [
            {
                "id": results["ids"][0][i],
                "document": docs[0][i],
                "metadata": metas[0][i],
            }
            for i in range(len(results["ids"][0]))
        ]

    def lookup_command(self, command_name: str) -> list[dict[str, Any]]:
        """Look up all chunks for a specific command name."""
        if self._collection.count() == 0:
            return []

        results = self._collection.get(
            where={"command_name": command_name},
        )

        docs = results["documents"]
        metas = results["metadatas"]
        if not docs or not metas:
            return []

        return [
            {
                "id": results["ids"][i],
                "document": docs[i],
                "metadata": metas[i],
            }
            for i in range(len(results["ids"]))
        ]

    def is_indexed(self) -> bool:
        """Check if the store contains any documents."""
        return self._collection.count() > 0

    def clear(self) -> None:
        """Delete all documents and recreate the collection."""
        self._client.delete_collection(COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=_embedding_fn,  # type: ignore[arg-type]  # chromadb generic variance
        )
