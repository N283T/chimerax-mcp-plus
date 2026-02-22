"""ChromaDB-backed document store for ChimeraX docs."""

from __future__ import annotations

from pathlib import Path

import chromadb

COLLECTION_NAME = "chimerax_docs"

DEFAULT_DATA_DIR = Path.home().joinpath(".local", "share", "chimerax-mcp", "chroma")


class DocStore:
    """Vector store for ChimeraX documentation chunks."""

    def __init__(self, data_dir: Path | None = None) -> None:
        data_dir = data_dir or DEFAULT_DATA_DIR
        data_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(data_dir))
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
        )

    def add_documents(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, str]],
    ) -> None:
        """Add document chunks to the store."""
        self._collection.add(ids=ids, documents=documents, metadatas=metadatas)

    def search(
        self,
        query: str,
        category: str | None = None,
        max_results: int = 5,
    ) -> list[dict]:
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

        return [
            {
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
            }
            for i in range(len(results["ids"][0]))
        ]

    def lookup_command(self, command_name: str) -> list[dict]:
        """Look up all chunks for a specific command name."""
        if self._collection.count() == 0:
            return []

        results = self._collection.get(
            where={"command_name": command_name},
        )

        return [
            {
                "id": results["ids"][i],
                "document": results["documents"][i],
                "metadata": results["metadatas"][i],
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
        )
