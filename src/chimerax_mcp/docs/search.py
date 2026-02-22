"""High-level search orchestration for ChimeraX documentation."""

from __future__ import annotations

import logging
from pathlib import Path

from chimerax_mcp.docs.indexer import DEFAULT_DOCS_PATH, chunk_html, discover_html_files
from chimerax_mcp.docs.store import DocStore

logger = logging.getLogger(__name__)


class DocSearch:
    """Orchestrates document indexing and search."""

    def __init__(
        self,
        docs_path: Path | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self._docs_path = docs_path or DEFAULT_DOCS_PATH
        self._store = DocStore(data_dir=data_dir)

    def build_index(self) -> dict[str, int]:
        """Build the search index from HTML documentation files."""
        self._store.clear()

        html_files = discover_html_files(self._docs_path)
        total_chunks = 0

        for html_file in html_files:
            relative = html_file.relative_to(self._docs_path)
            try:
                html_content = html_file.read_text(encoding="utf-8", errors="replace")
                chunks = chunk_html(html_content, source_file=str(relative))
            except Exception:
                logger.warning("Failed to parse %s, skipping", relative)
                continue

            if not chunks:
                continue

            ids = [f"{relative}#{i}" for i in range(len(chunks))]
            documents = [c.content for c in chunks]
            metadatas = [
                {
                    "source_file": c.source_file,
                    "category": c.category,
                    "title": c.title,
                    "section": c.section,
                    "command_name": c.command_name,
                }
                for c in chunks
            ]

            self._store.add_documents(ids=ids, documents=documents, metadatas=metadatas)
            total_chunks += len(chunks)

        logger.info("Indexed %d files, %d chunks", len(html_files), total_chunks)
        return {"files_processed": len(html_files), "chunks_created": total_chunks}

    def search(
        self,
        query: str,
        category: str | None = None,
        max_results: int = 5,
    ) -> list[dict]:
        """Semantic search over indexed documentation."""
        return self._store.search(query=query, category=category, max_results=max_results)

    def lookup(self, command_name: str) -> list[dict]:
        """Look up all documentation chunks for a specific command."""
        return self._store.lookup_command(command_name)

    def is_indexed(self) -> bool:
        """Check if the index has been built."""
        return self._store.is_indexed()

    def ensure_index(self) -> None:
        """Build the index if it has not been built yet."""
        if not self.is_indexed():
            logger.info("Index not found, building...")
            self.build_index()
