# Document Semantic Search Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add semantic search over ChimeraX documentation to the MCP server so AI can find accurate command syntax from natural language queries.

**Architecture:** HTML docs are parsed, chunked, and embedded into ChromaDB (local, file-based). Two new MCP tools (`docs_search`, `docs_lookup`) query the vector store. A CLI subcommand builds the index manually; the server auto-builds on first use if missing.

**Tech Stack:** ChromaDB (vector store + default embedding), BeautifulSoup4 (HTML parsing), existing FastMCP server

**Design Doc:** `docs/plans/2026-02-22-docs-semantic-search-design.md`

---

## Task 1: Add Dependencies

**Files:**
- Modify: `pyproject.toml:9-12`

**Step 1: Add chromadb and beautifulsoup4 to dependencies**

In `pyproject.toml`, change the `dependencies` list to:

```toml
dependencies = [
    "fastmcp>=2.0.0",
    "httpx>=0.28.0",
    "chromadb>=1.0.0",
    "beautifulsoup4>=4.12.0",
]
```

**Step 2: Install updated dependencies**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv sync`
Expected: Dependencies install successfully, lock file updated.

**Step 3: Verify imports work**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run python -c "import chromadb; import bs4; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add chromadb and beautifulsoup4 dependencies"
```

---

## Task 2: Create docs module with store.py (ChromaDB wrapper)

**Files:**
- Create: `src/chimerax_mcp/docs/__init__.py`
- Create: `src/chimerax_mcp/docs/store.py`
- Create: `tests/test_docs_store.py`

**Step 1: Write the failing tests**

Create `tests/test_docs_store.py`:

```python
"""Tests for ChromaDB document store."""

import tempfile
from pathlib import Path

from chimerax_mcp.docs.store import DocStore


class TestDocStore:
    def test_create_store(self, tmp_path: Path):
        store = DocStore(data_dir=tmp_path)
        assert store is not None

    def test_add_and_query(self, tmp_path: Path):
        store = DocStore(data_dir=tmp_path)
        store.add_documents(
            ids=["doc1"],
            documents=["The color command changes the color of atoms and surfaces"],
            metadatas=[{"category": "commands", "command_name": "color", "title": "color"}],
        )
        results = store.search("how to change atom colors", max_results=1)
        assert len(results) == 1
        assert results[0]["id"] == "doc1"
        assert "color" in results[0]["document"]

    def test_search_with_category_filter(self, tmp_path: Path):
        store = DocStore(data_dir=tmp_path)
        store.add_documents(
            ids=["cmd1", "tut1"],
            documents=[
                "The color command changes colors",
                "Tutorial: coloring your first protein",
            ],
            metadatas=[
                {"category": "commands", "command_name": "color", "title": "color"},
                {"category": "tutorials", "command_name": "", "title": "tutorial"},
            ],
        )
        results = store.search("color", category="commands", max_results=5)
        assert all(r["metadata"]["category"] == "commands" for r in results)

    def test_lookup_by_command_name(self, tmp_path: Path):
        store = DocStore(data_dir=tmp_path)
        store.add_documents(
            ids=["c1", "c2", "c3"],
            documents=["color simple usage", "color rainbow usage", "open command usage"],
            metadatas=[
                {"category": "commands", "command_name": "color", "title": "color"},
                {"category": "commands", "command_name": "color", "title": "color"},
                {"category": "commands", "command_name": "open", "title": "open"},
            ],
        )
        results = store.lookup_command("color")
        assert len(results) == 2
        assert all(r["metadata"]["command_name"] == "color" for r in results)

    def test_search_empty_store(self, tmp_path: Path):
        store = DocStore(data_dir=tmp_path)
        results = store.search("anything")
        assert results == []

    def test_is_indexed(self, tmp_path: Path):
        store = DocStore(data_dir=tmp_path)
        assert store.is_indexed() is False
        store.add_documents(
            ids=["doc1"],
            documents=["test"],
            metadatas=[{"category": "commands", "command_name": "test", "title": "test"}],
        )
        assert store.is_indexed() is True

    def test_clear(self, tmp_path: Path):
        store = DocStore(data_dir=tmp_path)
        store.add_documents(
            ids=["doc1"],
            documents=["test"],
            metadatas=[{"category": "commands", "command_name": "test", "title": "test"}],
        )
        assert store.is_indexed() is True
        store.clear()
        assert store.is_indexed() is False
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run pytest tests/test_docs_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'chimerax_mcp.docs'`

**Step 3: Create the module**

Create `src/chimerax_mcp/docs/__init__.py`:

```python
"""Document search module for ChimeraX documentation."""
```

Create `src/chimerax_mcp/docs/store.py`:

```python
"""ChromaDB-backed document store for ChimeraX docs."""

from __future__ import annotations

from pathlib import Path

import chromadb


COLLECTION_NAME = "chimerax_docs"

# Default data directory follows XDG Base Directory spec
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
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run pytest tests/test_docs_store.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add src/chimerax_mcp/docs/ tests/test_docs_store.py
git commit -m "feat: add ChromaDB document store for docs search"
```

---

## Task 3: Create indexer.py (HTML parsing + chunking)

**Files:**
- Create: `src/chimerax_mcp/docs/indexer.py`
- Create: `tests/test_docs_indexer.py`

The indexer parses HTML files into text chunks with metadata. The chunking
strategy splits by heading elements (`<h3>`, `<h4>`, `<h5>`) and falls back
to paragraph splitting for large sections.

The default docs path is `~/.claude/skills/explore-chimerax/assets/docs/`.

**Step 1: Write the failing tests**

Create `tests/test_docs_indexer.py`:

```python
"""Tests for HTML document indexer."""

import tempfile
from pathlib import Path

from chimerax_mcp.docs.indexer import DocChunk, categorize_file, chunk_html, parse_html


SAMPLE_COMMAND_HTML = """\
<html>
<head><title>Command: color, rainbow</title></head>
<body>
<h3><a href="../index.html#commands">Command</a>: color, rainbow</h3>
<p>The <b>color</b> command changes the color of atoms, bonds, and surfaces.</p>

<h4><a name="simple">Simple Coloring</a></h4>
<p>Usage: <b>color</b> <i>spec</i> <i>color-spec</i></p>
<p>Colors the specified items with the given color.</p>

<h4><a name="sequential">Sequential Coloring (Rainbow)</a></h4>
<p>Usage: <b>rainbow</b> <i>spec</i></p>
<p>Colors residues sequentially using a rainbow palette.</p>
</body>
</html>
"""

SAMPLE_TOOL_HTML = """\
<html>
<head><title>Tool: Model Panel</title></head>
<body>
<h3>Tool: Model Panel</h3>
<p>The Model Panel lists the currently open models.</p>
<p>It shows model number, name, and display status.</p>
</body>
</html>
"""


class TestCategorizeFile:
    def test_command_file(self):
        p = Path("user/commands/color.html")
        assert categorize_file(p) == "commands"

    def test_tool_file(self):
        p = Path("user/tools/modelpanel.html")
        assert categorize_file(p) == "tools"

    def test_tutorial_file(self):
        p = Path("user/tutorials/intro.html")
        assert categorize_file(p) == "tutorials"

    def test_devel_file(self):
        p = Path("devel/bundles.html")
        assert categorize_file(p) == "devel"

    def test_user_top_level(self):
        p = Path("user/attributes.html")
        assert categorize_file(p) == "concepts"

    def test_unknown_file(self):
        p = Path("other/random.html")
        assert categorize_file(p) == "other"


class TestParseHtml:
    def test_extracts_title(self):
        title, _ = parse_html(SAMPLE_COMMAND_HTML)
        assert title == "Command: color, rainbow"

    def test_extracts_text_content(self):
        _, text = parse_html(SAMPLE_COMMAND_HTML)
        assert "color" in text
        assert "rainbow" in text
        # HTML tags should be stripped
        assert "<b>" not in text


class TestChunkHtml:
    def test_returns_chunks(self):
        chunks = chunk_html(SAMPLE_COMMAND_HTML, source_file="user/commands/color.html")
        assert len(chunks) > 0
        assert all(isinstance(c, DocChunk) for c in chunks)

    def test_chunk_has_metadata(self):
        chunks = chunk_html(SAMPLE_COMMAND_HTML, source_file="user/commands/color.html")
        for chunk in chunks:
            assert chunk.source_file == "user/commands/color.html"
            assert chunk.category == "commands"
            assert chunk.title == "Command: color, rainbow"
            assert chunk.command_name == "color"

    def test_command_name_extracted(self):
        chunks = chunk_html(SAMPLE_COMMAND_HTML, source_file="user/commands/color.html")
        assert all(c.command_name == "color" for c in chunks)

    def test_non_command_has_empty_command_name(self):
        chunks = chunk_html(SAMPLE_TOOL_HTML, source_file="user/tools/modelpanel.html")
        assert all(c.command_name == "" for c in chunks)

    def test_chunks_have_section_names(self):
        chunks = chunk_html(SAMPLE_COMMAND_HTML, source_file="user/commands/color.html")
        sections = [c.section for c in chunks]
        # Should have at least the main section and subsections
        assert any("Simple Coloring" in s for s in sections)

    def test_chunk_content_is_text(self):
        chunks = chunk_html(SAMPLE_COMMAND_HTML, source_file="user/commands/color.html")
        for chunk in chunks:
            assert "<" not in chunk.content or "&lt;" in chunk.content  # no raw HTML tags
            assert len(chunk.content) > 0
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run pytest tests/test_docs_indexer.py -v`
Expected: FAIL — `ImportError`

**Step 3: Implement the indexer**

Create `src/chimerax_mcp/docs/indexer.py`:

```python
"""HTML document parser and chunker for ChimeraX documentation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag


# Chunk size limits (characters)
MIN_CHUNK_SIZE = 100
MAX_CHUNK_SIZE = 1500
OVERLAP_SIZE = 100

# Default docs location
DEFAULT_DOCS_PATH = Path.home().joinpath(
    ".claude", "skills", "explore-chimerax", "assets", "docs"
)

# Heading tags that trigger chunk splits
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5"}


@dataclass(frozen=True)
class DocChunk:
    """A chunk of documentation with metadata."""

    content: str
    source_file: str
    category: str
    title: str
    section: str
    command_name: str


def categorize_file(relative_path: Path) -> str:
    """Determine the category of a doc file from its relative path."""
    parts = relative_path.parts
    if len(parts) >= 2 and parts[0] == "user":
        if parts[1] == "commands":
            return "commands"
        if parts[1] == "tools":
            return "tools"
        if parts[1] == "tutorials":
            return "tutorials"
        if len(parts) == 2:
            return "concepts"
        return "concepts"
    if len(parts) >= 1 and parts[0] == "devel":
        return "devel"
    return "other"


def _extract_command_name(title: str, category: str) -> str:
    """Extract the primary command name from a page title."""
    if category != "commands":
        return ""
    # Title format: "Command: color, rainbow" or "Command: open"
    match = re.match(r"Command:\s*(\w+)", title)
    return match.group(1) if match else ""


def parse_html(html_content: str) -> tuple[str, str]:
    """Parse HTML and return (title, full_text).

    Returns:
        Tuple of (page title, plain text content).
    """
    soup = BeautifulSoup(html_content, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    body = soup.find("body")
    text = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)
    return title, text


def _split_by_headings(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """Split HTML body into sections by heading tags.

    Returns:
        List of (section_name, text_content) tuples.
    """
    body = soup.find("body") or soup
    sections: list[tuple[str, list[str]]] = []
    current_heading = ""
    current_texts: list[str] = []

    for element in body.children:
        if isinstance(element, Tag) and element.name in HEADING_TAGS:
            if current_texts:
                sections.append((current_heading, current_texts))
            current_heading = element.get_text(strip=True)
            current_texts = []
        elif isinstance(element, Tag):
            text = element.get_text(separator=" ", strip=True)
            if text:
                current_texts.append(text)
        elif isinstance(element, NavigableString):
            text = str(element).strip()
            if text:
                current_texts.append(text)

    if current_texts:
        sections.append((current_heading, current_texts))

    return [(heading, "\n".join(texts)) for heading, texts in sections]


def _split_large_text(text: str, max_size: int = MAX_CHUNK_SIZE) -> list[str]:
    """Split text that exceeds max_size into smaller pieces at paragraph boundaries."""
    if len(text) <= max_size:
        return [text]

    paragraphs = text.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para) + 1  # +1 for newline
        if current_len + para_len > max_size and current:
            chunks.append("\n".join(current))
            # Add overlap from end of previous chunk
            overlap_text = para
            current = [overlap_text] if len(overlap_text) <= OVERLAP_SIZE else []
            current_len = len(overlap_text) + 1 if current else 0
        current.append(para)
        current_len += para_len

    if current:
        chunks.append("\n".join(current))

    return chunks


def chunk_html(html_content: str, source_file: str) -> list[DocChunk]:
    """Parse HTML and split into searchable chunks with metadata.

    Args:
        html_content: Raw HTML string.
        source_file: Relative path of the source file (e.g., "user/commands/color.html").

    Returns:
        List of DocChunk objects.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    category = categorize_file(Path(source_file))
    command_name = _extract_command_name(title, category)

    sections = _split_by_headings(soup)
    chunks: list[DocChunk] = []

    for section_name, text in sections:
        if len(text.strip()) < MIN_CHUNK_SIZE:
            continue

        for piece in _split_large_text(text):
            if len(piece.strip()) < MIN_CHUNK_SIZE:
                continue
            chunks.append(
                DocChunk(
                    content=piece.strip(),
                    source_file=source_file,
                    category=category,
                    title=title,
                    section=section_name or title,
                    command_name=command_name,
                )
            )

    # If no chunks were created (small page), create one from the full text
    if not chunks:
        _, full_text = parse_html(html_content)
        if full_text.strip():
            chunks.append(
                DocChunk(
                    content=full_text.strip(),
                    source_file=source_file,
                    category=category,
                    title=title,
                    section=title,
                    command_name=command_name,
                )
            )

    return chunks


def discover_html_files(docs_path: Path) -> list[Path]:
    """Find all HTML files under the docs directory.

    Args:
        docs_path: Root directory of documentation.

    Returns:
        List of HTML file paths.
    """
    return sorted(docs_path.rglob("*.html"))
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run pytest tests/test_docs_indexer.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/chimerax_mcp/docs/indexer.py tests/test_docs_indexer.py
git commit -m "feat: add HTML parser and chunker for docs indexing"
```

---

## Task 4: Create search.py (search orchestration)

**Files:**
- Create: `src/chimerax_mcp/docs/search.py`
- Create: `tests/test_docs_search.py`

This module ties the indexer and store together: builds the index from HTML
files, and provides the high-level search API used by MCP tools.

**Step 1: Write the failing tests**

Create `tests/test_docs_search.py`:

```python
"""Tests for document search orchestration."""

import tempfile
from pathlib import Path

import pytest

from chimerax_mcp.docs.search import DocSearch


def _create_test_docs(tmp_path: Path) -> Path:
    """Create a minimal set of test HTML docs."""
    docs_dir = tmp_path.joinpath("docs")
    commands_dir = docs_dir.joinpath("user", "commands")
    commands_dir.mkdir(parents=True)

    color_html = """\
<html><head><title>Command: color, rainbow</title></head>
<body>
<h3>Command: color, rainbow</h3>
<p>The color command changes the color of atoms, bonds, and surfaces.
It supports simple coloring, rainbow coloring, and coloring by attribute values.
Use color to set the appearance of molecular structures in ChimeraX.</p>
<h4>Simple Coloring</h4>
<p>Usage: color spec color-spec. Colors atoms, bonds, cartoons, surfaces, and other items.</p>
</body></html>
"""

    open_html = """\
<html><head><title>Command: open</title></head>
<body>
<h3>Command: open</h3>
<p>The open command reads data from files or fetches structures from databases.
It can open PDB files, mmCIF files, maps, and session files.
Use open to load molecular structures into ChimeraX for visualization.</p>
</body></html>
"""

    commands_dir.joinpath("color.html").write_text(color_html)
    commands_dir.joinpath("open.html").write_text(open_html)
    return docs_dir


class TestDocSearch:
    def test_build_index(self, tmp_path: Path):
        docs_dir = _create_test_docs(tmp_path)
        data_dir = tmp_path.joinpath("chroma")
        search = DocSearch(docs_path=docs_dir, data_dir=data_dir)
        stats = search.build_index()
        assert stats["files_processed"] == 2
        assert stats["chunks_created"] > 0

    def test_search_after_index(self, tmp_path: Path):
        docs_dir = _create_test_docs(tmp_path)
        data_dir = tmp_path.joinpath("chroma")
        search = DocSearch(docs_path=docs_dir, data_dir=data_dir)
        search.build_index()
        results = search.search("how to change atom colors")
        assert len(results) > 0
        assert any("color" in r["metadata"].get("command_name", "") for r in results)

    def test_lookup_command(self, tmp_path: Path):
        docs_dir = _create_test_docs(tmp_path)
        data_dir = tmp_path.joinpath("chroma")
        search = DocSearch(docs_path=docs_dir, data_dir=data_dir)
        search.build_index()
        results = search.lookup("color")
        assert len(results) > 0
        assert all(r["metadata"]["command_name"] == "color" for r in results)

    def test_lookup_nonexistent_command(self, tmp_path: Path):
        docs_dir = _create_test_docs(tmp_path)
        data_dir = tmp_path.joinpath("chroma")
        search = DocSearch(docs_path=docs_dir, data_dir=data_dir)
        search.build_index()
        results = search.lookup("nonexistent")
        assert results == []

    def test_is_indexed(self, tmp_path: Path):
        docs_dir = _create_test_docs(tmp_path)
        data_dir = tmp_path.joinpath("chroma")
        search = DocSearch(docs_path=docs_dir, data_dir=data_dir)
        assert search.is_indexed() is False
        search.build_index()
        assert search.is_indexed() is True

    def test_ensure_index_builds_if_missing(self, tmp_path: Path):
        docs_dir = _create_test_docs(tmp_path)
        data_dir = tmp_path.joinpath("chroma")
        search = DocSearch(docs_path=docs_dir, data_dir=data_dir)
        assert search.is_indexed() is False
        search.ensure_index()
        assert search.is_indexed() is True

    def test_ensure_index_skips_if_exists(self, tmp_path: Path):
        docs_dir = _create_test_docs(tmp_path)
        data_dir = tmp_path.joinpath("chroma")
        search = DocSearch(docs_path=docs_dir, data_dir=data_dir)
        search.build_index()
        # Second call should not rebuild
        search.ensure_index()  # should not raise
        assert search.is_indexed() is True
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run pytest tests/test_docs_search.py -v`
Expected: FAIL — `ImportError`

**Step 3: Implement search.py**

Create `src/chimerax_mcp/docs/search.py`:

```python
"""High-level search orchestration for ChimeraX documentation."""

from __future__ import annotations

import logging
from pathlib import Path

from chimerax_mcp.docs.indexer import DEFAULT_DOCS_PATH, DocChunk, chunk_html, discover_html_files
from chimerax_mcp.docs.store import DEFAULT_DATA_DIR, DocStore

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
        """Build the search index from HTML documentation files.

        Returns:
            Stats dict with files_processed and chunks_created counts.
        """
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
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run pytest tests/test_docs_search.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/chimerax_mcp/docs/search.py tests/test_docs_search.py
git commit -m "feat: add search orchestration with index build and query"
```

---

## Task 5: Add MCP tools (docs_search, docs_lookup)

**Files:**
- Modify: `src/chimerax_mcp/server.py`
- Create: `tests/test_docs_tools.py`

**Step 1: Write the failing tests**

Create `tests/test_docs_tools.py`:

```python
"""Tests for docs MCP tools."""

from unittest.mock import MagicMock, patch

from chimerax_mcp.server import docs_lookup, docs_search


class TestDocsSearchTool:
    @patch("chimerax_mcp.server.get_doc_search")
    def test_search_returns_results(self, mock_get):
        mock_search = MagicMock()
        mock_search.is_indexed.return_value = True
        mock_search.search.return_value = [
            {
                "id": "doc1",
                "document": "The color command",
                "metadata": {
                    "title": "color",
                    "section": "Simple Coloring",
                    "category": "commands",
                    "source_file": "user/commands/color.html",
                    "command_name": "color",
                },
            }
        ]
        mock_get.return_value = mock_search

        result = docs_search.fn(query="how to color atoms")
        assert result["status"] == "ok"
        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "color"

    @patch("chimerax_mcp.server.get_doc_search")
    def test_search_with_category(self, mock_get):
        mock_search = MagicMock()
        mock_search.is_indexed.return_value = True
        mock_search.search.return_value = []
        mock_get.return_value = mock_search

        result = docs_search.fn(query="color", category="tutorials")
        mock_search.search.assert_called_once_with(
            query="color", category="tutorials", max_results=5
        )

    @patch("chimerax_mcp.server.get_doc_search")
    def test_search_not_indexed(self, mock_get):
        mock_search = MagicMock()
        mock_search.is_indexed.return_value = False
        mock_search.ensure_index.return_value = None
        mock_search.search.return_value = []
        mock_get.return_value = mock_search

        result = docs_search.fn(query="test")
        mock_search.ensure_index.assert_called_once()


class TestDocsLookupTool:
    @patch("chimerax_mcp.server.get_doc_search")
    def test_lookup_returns_chunks(self, mock_get):
        mock_search = MagicMock()
        mock_search.is_indexed.return_value = True
        mock_search.lookup.return_value = [
            {
                "id": "c1",
                "document": "color simple usage",
                "metadata": {
                    "title": "color",
                    "section": "Simple",
                    "category": "commands",
                    "source_file": "user/commands/color.html",
                    "command_name": "color",
                },
            }
        ]
        mock_get.return_value = mock_search

        result = docs_lookup.fn(command_name="color")
        assert result["status"] == "ok"
        assert len(result["results"]) == 1

    @patch("chimerax_mcp.server.get_doc_search")
    def test_lookup_not_found(self, mock_get):
        mock_search = MagicMock()
        mock_search.is_indexed.return_value = True
        mock_search.lookup.return_value = []
        mock_get.return_value = mock_search

        result = docs_lookup.fn(command_name="nonexistent")
        assert result["status"] == "ok"
        assert result["results"] == []
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run pytest tests/test_docs_tools.py -v`
Expected: FAIL — `ImportError: cannot import name 'docs_search'`

**Step 3: Add the tools to server.py**

At the top of `server.py`, add import:

```python
from chimerax_mcp.docs.search import DocSearch
```

Add a singleton accessor (after `get_client`):

```python
_doc_search: DocSearch | None = None


def get_doc_search() -> DocSearch:
    """Get or create the document search instance."""
    global _doc_search
    if _doc_search is None:
        _doc_search = DocSearch()
    return _doc_search
```

Add the two new tools at the end of `server.py` (before the bundle tools):

```python
@mcp.tool()
def docs_search(
    query: str,
    category: str | None = None,
    max_results: int = 5,
) -> dict[str, Any]:
    """Search ChimeraX documentation using natural language.

    Use this tool to find relevant documentation before running ChimeraX
    commands. Supports semantic search over commands, tools, tutorials,
    and developer guides.

    Args:
        query: Natural language query (e.g., "how to color protein by chain")
        category: Filter by category - "commands", "tools", "tutorials",
                  "concepts", or "devel" (default: search all)
        max_results: Maximum number of results (default: 5)

    Returns:
        Matching documentation chunks with metadata.
    """
    search = get_doc_search()
    if not search.is_indexed():
        search.ensure_index()

    results = search.search(query=query, category=category, max_results=max_results)
    return {
        "status": "ok",
        "results": [
            {
                "title": r["metadata"]["title"],
                "section": r["metadata"]["section"],
                "content": r["document"],
                "category": r["metadata"]["category"],
                "source_file": r["metadata"]["source_file"],
            }
            for r in results
        ],
    }


@mcp.tool()
def docs_lookup(
    command_name: str,
) -> dict[str, Any]:
    """Look up documentation for a specific ChimeraX command by name.

    Use this to get the full reference for a known command name.

    Args:
        command_name: Exact command name (e.g., "color", "open", "surface")

    Returns:
        All documentation chunks for that command.
    """
    search = get_doc_search()
    if not search.is_indexed():
        search.ensure_index()

    results = search.lookup(command_name)
    return {
        "status": "ok",
        "results": [
            {
                "title": r["metadata"]["title"],
                "section": r["metadata"]["section"],
                "content": r["document"],
                "category": r["metadata"]["category"],
                "source_file": r["metadata"]["source_file"],
            }
            for r in results
        ],
    }
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run pytest tests/test_docs_tools.py -v`
Expected: All tests PASS

**Step 5: Run ALL tests to verify nothing is broken**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run pytest -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/chimerax_mcp/server.py tests/test_docs_tools.py
git commit -m "feat: add docs_search and docs_lookup MCP tools"
```

---

## Task 6: Add CLI subcommand for index building

**Files:**
- Modify: `src/chimerax_mcp/__init__.py`
- Create: `tests/test_cli.py`

**Step 1: Write the failing tests**

Create `tests/test_cli.py`:

```python
"""Tests for CLI commands."""

import subprocess
import sys


class TestIndexDocsCli:
    def test_help_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "chimerax_mcp", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "index-docs" in result.stdout

    def test_index_docs_with_nonexistent_path(self):
        result = subprocess.run(
            [sys.executable, "-m", "chimerax_mcp", "index-docs", "--docs-path", "/nonexistent"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run pytest tests/test_cli.py -v`
Expected: FAIL — "index-docs" not found in help output

**Step 3: Implement CLI**

Replace `src/chimerax_mcp/__init__.py`:

```python
"""ChimeraX MCP Server - Control UCSF ChimeraX through Model Context Protocol."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from chimerax_mcp.server import mcp


def _run_server() -> None:
    """Run the MCP server."""
    mcp.run()


def _index_docs(args: argparse.Namespace) -> None:
    """Build the documentation search index."""
    from chimerax_mcp.docs.search import DocSearch

    docs_path = Path(args.docs_path) if args.docs_path else None
    data_dir = Path(args.data_dir) if args.data_dir else None

    if docs_path and not docs_path.exists():
        print(f"Error: docs path does not exist: {docs_path}", file=sys.stderr)
        sys.exit(1)

    search = DocSearch(docs_path=docs_path, data_dir=data_dir)
    print("Building documentation index...")
    stats = search.build_index()
    print(f"Done: {stats['files_processed']} files, {stats['chunks_created']} chunks indexed.")


def main() -> None:
    """Entry point for the MCP server and CLI commands."""
    parser = argparse.ArgumentParser(
        prog="chimerax-mcp",
        description="MCP server for UCSF ChimeraX",
    )
    subparsers = parser.add_subparsers(dest="command")

    # index-docs subcommand
    index_parser = subparsers.add_parser(
        "index-docs",
        help="Build the documentation search index",
    )
    index_parser.add_argument(
        "--docs-path",
        help="Path to ChimeraX HTML documentation directory",
    )
    index_parser.add_argument(
        "--data-dir",
        help="Path to store the ChromaDB database",
    )

    args = parser.parse_args()

    if args.command == "index-docs":
        _index_docs(args)
    else:
        _run_server()


__all__ = ["main", "mcp"]
```

Also create `src/chimerax_mcp/__main__.py` to support `python -m chimerax_mcp`:

```python
"""Allow running as python -m chimerax_mcp."""

from chimerax_mcp import main

main()
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run pytest tests/test_cli.py -v`
Expected: All tests PASS

**Step 5: Run ALL tests**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run pytest -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/chimerax_mcp/__init__.py src/chimerax_mcp/__main__.py tests/test_cli.py
git commit -m "feat: add index-docs CLI subcommand"
```

---

## Task 7: Integration test with real docs

**Files:**
- Create: `tests/test_integration.py`

This test runs against the actual ChimeraX documentation on disk.
It is skipped if the docs directory does not exist.

**Step 1: Write the integration test**

Create `tests/test_integration.py`:

```python
"""Integration tests using real ChimeraX documentation."""

from pathlib import Path

import pytest

from chimerax_mcp.docs.search import DocSearch

REAL_DOCS_PATH = Path.home().joinpath(
    ".claude", "skills", "explore-chimerax", "assets", "docs"
)

pytestmark = pytest.mark.skipif(
    not REAL_DOCS_PATH.exists(),
    reason="ChimeraX docs not found locally",
)


@pytest.fixture(scope="module")
def search(tmp_path_factory):
    """Build index from real docs once for the module."""
    data_dir = tmp_path_factory.mktemp("chroma")
    s = DocSearch(docs_path=REAL_DOCS_PATH, data_dir=data_dir)
    s.build_index()
    return s


class TestRealDocsSearch:
    def test_search_color_command(self, search):
        results = search.search("how to color protein by chain")
        assert len(results) > 0
        # Should find color-related documentation
        texts = " ".join(r["document"] for r in results).lower()
        assert "color" in texts

    def test_search_open_command(self, search):
        results = search.search("open a PDB structure file")
        assert len(results) > 0

    def test_lookup_color(self, search):
        results = search.lookup("color")
        assert len(results) > 0
        assert all(r["metadata"]["command_name"] == "color" for r in results)

    def test_search_with_category_filter(self, search):
        results = search.search("surface", category="commands")
        assert len(results) > 0
        assert all(r["metadata"]["category"] == "commands" for r in results)

    def test_search_tutorials(self, search):
        results = search.search("getting started tutorial", category="tutorials")
        # May or may not find results depending on docs content
        for r in results:
            assert r["metadata"]["category"] == "tutorials"
```

**Step 2: Run the integration test**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run pytest tests/test_integration.py -v`
Expected: All tests PASS (or skip if docs not found)

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests with real ChimeraX docs"
```

---

## Task 8: Update README and run final checks

**Files:**
- Modify: `README.md`

**Step 1: Add docs search section to README**

Add a "Documentation Search" section to the README after the existing tools
section, documenting the two new tools and the `index-docs` CLI command.

**Step 2: Run full lint and type check**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run ruff format . && uv run ruff check --fix .`
Expected: No errors

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run ty check`
Expected: No errors (or only pre-existing ones)

**Step 3: Run all tests**

Run: `cd /Users/nagaet/chimerax-mcp-plus && uv run pytest -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add documentation search feature to README"
```

---

- [ ] **DONE** - Plan complete
