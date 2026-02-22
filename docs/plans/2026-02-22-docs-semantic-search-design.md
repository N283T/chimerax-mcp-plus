# Design: Document Semantic Search for chimerax-mcp-plus

Date: 2026-02-22

## Goal

Add semantic search over ChimeraX documentation to the MCP server,
enabling AI to find accurate command syntax and usage information
from natural language queries.

## Background

The current MCP server has 18 tools for controlling ChimeraX but no way
to look up documentation. AI must already know command syntax to use
`chimerax_run()`. This makes it fragile and limits natural language
interaction.

ChimeraX documentation already exists locally as 913 HTML files (28 MB)
in the `explore-chimerax` skill's `assets/docs/` directory.

## Approach: Full RAG Pipeline

```
HTML docs (913 files)
  → indexer (parse + chunk + metadata)
    → ChromaDB (local file-based)
      → MCP tools: docs_search / docs_lookup
        → relevant chunks returned to AI
```

## Architecture

```
┌─────────────────────────────────────────┐
│          chimerax-mcp-plus              │
├─────────────────────────────────────────┤
│  server.py (existing 18 tools)          │
│    + docs_search()      ← NEW          │
│    + docs_lookup()      ← NEW          │
├─────────────────────────────────────────┤
│  docs/                  ← NEW module   │
│    indexer.py    HTML parse + chunking  │
│    store.py      ChromaDB operations   │
│    search.py     search logic          │
├─────────────────────────────────────────┤
│  ChromaDB (file-based, in-process)      │
│    ~/.local/share/chimerax-mcp/chroma/  │
└─────────────────────────────────────────┘
```

## Document Categories

| Category | Path | Files | Content |
|----------|------|-------|---------|
| `commands` | `user/commands/*.html` | ~138 | Command reference |
| `tools` | `user/tools/*.html` | ~40 | GUI tool descriptions |
| `tutorials` | `user/tutorials/*.html` | few | Tutorials |
| `concepts` | `user/*.html` (top-level) | few | Concept explanations |
| `devel` | `devel/**/*.html` | ~100 | Bundle development guide |

## Chunking Strategy

- Parse HTML with BeautifulSoup, split by heading elements (`<h3>`, `<h4>`)
- Target chunk size: 500-1500 characters
- Overlap: 100 characters between adjacent chunks
- Large sections further split at paragraph level

### Chunk Metadata

```python
{
    "source_file": "user/commands/color.html",
    "category": "commands",
    "title": "Command: color, rainbow",
    "section": "Sequential Coloring (Rainbow)",
    "command_name": "color",        # command pages only
    "url_fragment": "#sequential",
}
```

## Embedding Model

**`all-MiniLM-L6-v2`** via ChromaDB's default embedding function.
- 80 MB model, fast inference
- Sufficient quality for English technical documentation
- No additional configuration needed

## New MCP Tools

### `docs_search` — Semantic Search

```python
docs_search(
    query: str,              # "how to color protein by chain"
    category: str | None,    # "commands" | "tools" | "tutorials" | "concepts" | "devel"
    max_results: int = 5,
) -> list[dict]
# Returns: [{title, section, content, category, source_file}, ...]
```

### `docs_lookup` — Direct Command Lookup

```python
docs_lookup(
    command_name: str,       # "color"
) -> list[dict]
# Returns: all chunks for that command
```

## Index Construction

- **CLI**: `chimerax-mcp index-docs [--docs-path PATH]`
- **Auto**: On server startup, if DB does not exist, build automatically
- **Staleness**: Version file tracks doc freshness; rebuild if stale

## Dependencies Added

```toml
dependencies = [
    "fastmcp>=2.0.0",
    "httpx>=0.28.0",
    "chromadb>=1.0.0",        # NEW
    "beautifulsoup4>=4.12.0", # NEW
]
```

## File Structure

```
src/chimerax_mcp/
├── __init__.py          # main() + index-docs CLI
├── server.py            # existing tools + docs_search, docs_lookup
├── chimerax.py          # existing (no changes)
└── docs/                # NEW
    ├── __init__.py
    ├── indexer.py        # HTML parse + chunking
    ├── store.py          # ChromaDB init + operations
    └── search.py         # search logic
```

## Alternatives Considered

**B. Structured JSON + SQLite FTS5**: Lighter dependencies but keyword-only
search cannot handle natural language queries like "color protein by chain".

**C. Hybrid (vector + keyword)**: ChromaDB already supports metadata filtering,
so Approach A effectively covers this without extra complexity.

---
- [ ] **DONE** - Design approved
