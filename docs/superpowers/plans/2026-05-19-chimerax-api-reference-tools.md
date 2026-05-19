# ChimeraX API Reference Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add skill-independent MCP tools for static ChimeraX API documentation lookup and live ChimeraX Python API introspection.

**Architecture:** Static documentation logic lives in a focused `api_docs.py` helper that discovers local docs/indexes and falls back to a packaged JSON index. Live API inspection lives in a focused `python_api.py` helper that generates bounded `runscript` introspection scripts and rejects unsafe symbol strings. `server.py` only wires these helpers into MCP tools.

**Tech Stack:** Python 3.12, FastMCP, httpx, `importlib.resources`, stdlib HTML parsing, pytest, uv.

---

## File Structure

- Create `src/chimerax_mcp/resources/__init__.py`: package marker for bundled resource loading.
- Create `src/chimerax_mcp/resources/chimerax-1.9.index.json`: initial packaged fallback index copied from `skills/explore-chimerax/assets/chimerax-1.9.index.json`.
- Create `src/chimerax_mcp/api_docs.py`: static index discovery, loading, search, target resolution, and HTML-to-text excerpt handling.
- Create `src/chimerax_mcp/python_api.py`: dotted-symbol validation, live introspection script generation, response parsing, and `runscript` execution helper.
- Modify `src/chimerax_mcp/server.py`: add four MCP tool functions that delegate to `api_docs.py` and `python_api.py`.
- Modify `README.md`: document the new API reference tools, static-source fallback behavior, and safety limits.
- Modify `pyproject.toml`: ensure packaged JSON resources are included in the wheel.
- Create `scripts/build_chimerax_doc_index.py`: release-time script for generating package index resources from local ChimeraX docs, based on the existing skill script.
- Create `tests/test_api_docs.py`: static documentation helper tests.
- Create `tests/test_python_api.py`: live-introspection helper tests with mocked ChimeraX client.
- Modify `tests/test_server.py`: MCP tool wiring tests for new tools.

---

### Task 1: Package a Skill-Independent Static Index

**Files:**
- Create: `src/chimerax_mcp/resources/__init__.py`
- Create: `src/chimerax_mcp/resources/chimerax-1.9.index.json`
- Modify: `pyproject.toml`
- Test: `tests/test_api_docs.py`

- [ ] **Step 1: Create the resource package marker**

Create `src/chimerax_mcp/resources/__init__.py` with exactly:

```python
"""Bundled ChimeraX documentation indexes."""
```

- [ ] **Step 2: Copy the existing generated index into package resources**

Run:

```bash
mkdir -p src/chimerax_mcp/resources
cp skills/explore-chimerax/assets/chimerax-1.9.index.json \
  src/chimerax_mcp/resources/chimerax-1.9.index.json
```

Expected: `src/chimerax_mcp/resources/chimerax-1.9.index.json` exists and is about 116KB.

- [ ] **Step 3: Add the package-data build setting**

Edit `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/pyproject.toml` and add this block after the existing `[tool.hatch.build.targets.wheel]` block:

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/chimerax_mcp/resources" = "chimerax_mcp/resources"
```

Keep the existing block:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/chimerax_mcp"]
```

- [ ] **Step 4: Write the failing packaged-resource test**

Create `tests/test_api_docs.py` with:

```python
"""Tests for ChimeraX static API documentation helpers."""

from chimerax_mcp.api_docs import load_packaged_index


def test_load_packaged_index_has_chimerax_metadata():
    index = load_packaged_index()

    assert index["version"] == "1.9"
    assert "atomic" in index["modules"]
    assert "color" in index["commands"]
    assert index["modules"]["atomic"]["path"].startswith("devel/modules/atomic/")
```

- [ ] **Step 5: Run the test and verify it fails because `api_docs.py` does not exist**

Run:

```bash
uv run pytest tests/test_api_docs.py::test_load_packaged_index_has_chimerax_metadata -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'chimerax_mcp.api_docs'`.

- [ ] **Step 6: Implement minimal packaged-index loading**

Create `src/chimerax_mcp/api_docs.py` with:

```python
"""Static ChimeraX documentation index lookup helpers."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

PACKAGED_INDEX_NAME = "chimerax-1.9.index.json"


def load_packaged_index() -> dict[str, Any]:
    """Load the bundled fallback ChimeraX documentation index."""
    index_path = resources.files("chimerax_mcp.resources").joinpath(PACKAGED_INDEX_NAME)
    return json.loads(index_path.read_text(encoding="utf-8"))
```

- [ ] **Step 7: Run the packaged-resource test and verify it passes**

Run:

```bash
uv run pytest tests/test_api_docs.py::test_load_packaged_index_has_chimerax_metadata -v
```

Expected: PASS.

- [ ] **Step 8: Verify the resource is included in a built wheel**

Run:

```bash
uv build --wheel
python - <<'PY'
import zipfile
from pathlib import Path
wheel = sorted(Path('dist').glob('chimerax_mcp_plus-*.whl'))[-1]
with zipfile.ZipFile(wheel) as zf:
    names = set(zf.namelist())
assert 'chimerax_mcp/resources/chimerax-1.9.index.json' in names
print(wheel)
PY
```

Expected: command prints the built wheel path without assertion errors.

- [ ] **Step 9: Commit Task 1**

Run:

```bash
git add pyproject.toml src/chimerax_mcp/resources tests/test_api_docs.py
git commit -m "feat: bundle ChimeraX API index"
```

---

### Task 2: Implement Static Documentation Discovery, Search, and Read

**Files:**
- Modify: `src/chimerax_mcp/api_docs.py`
- Modify: `tests/test_api_docs.py`

- [ ] **Step 1: Add failing tests for source discovery, search, and read**

Append this code to `tests/test_api_docs.py`:

```python
import json
from pathlib import Path

from chimerax_mcp.api_docs import (
    DocIndexSource,
    find_doc_sources,
    read_api_target,
    search_api_index,
)


def test_find_doc_sources_prefers_env_docs_path(tmp_path: Path, monkeypatch):
    docs = tmp_path.joinpath("docs")
    docs.joinpath("devel", "modules", "atomic").mkdir(parents=True)
    index = {
        "version": "test",
        "commands": {},
        "tutorials": {},
        "modules": {
            "atomic": {
                "path": "devel/modules/atomic/atomic.html",
                "title": "atomic test title",
                "description": "atomic test description",
            }
        },
        "keywords": {},
    }
    docs.joinpath("chimerax-test.index.json").write_text(json.dumps(index), encoding="utf-8")
    monkeypatch.setenv("CHIMERAX_DOCS_PATH", str(docs))

    sources = find_doc_sources()

    assert sources[0].kind == "env"
    assert sources[0].docs_root == docs
    assert sources[0].index_path == docs.joinpath("chimerax-test.index.json")


def test_search_api_index_finds_module_from_packaged_index():
    source = DocIndexSource.packaged()

    result = search_api_index("AtomicStructure residues", source=source, kind="modules", limit=5)

    assert result["status"] == "ok"
    assert result["source"]["kind"] == "packaged"
    assert result["version"] == "1.9"
    assert any(item["name"] == "atomic" and item["kind"] == "modules" for item in result["results"])


def test_search_api_index_rejects_invalid_kind():
    result = search_api_index("atomic", kind="bad-kind")

    assert result == {
        "status": "error",
        "message": "kind must be one of: all, commands, keywords, modules, tutorials",
    }


def test_read_api_target_returns_packaged_metadata_when_html_missing():
    result = read_api_target("atomic", source=DocIndexSource.packaged(), max_chars=500)

    assert result["status"] == "ok"
    assert result["source"]["kind"] == "packaged"
    assert result["target"] == "atomic"
    assert result["kind"] == "modules"
    assert "Atomic structures" in result["content"]
    assert result["truncated"] is False


def test_read_api_target_extracts_local_html(tmp_path: Path):
    docs = tmp_path.joinpath("docs")
    html_path = docs.joinpath("devel", "modules", "atomic", "atomic.html")
    html_path.parent.mkdir(parents=True)
    html_path.write_text(
        "<html><head><title>atomic</title></head><body>"
        "<h1>Atomic API</h1><p>Residue and atom objects.</p>"
        "</body></html>",
        encoding="utf-8",
    )
    index_path = docs.joinpath("chimerax-test.index.json")
    index_path.write_text(
        json.dumps(
            {
                "version": "test",
                "commands": {},
                "tutorials": {},
                "modules": {
                    "atomic": {
                        "path": "devel/modules/atomic/atomic.html",
                        "title": "atomic title",
                        "description": "fallback description",
                    }
                },
                "keywords": {},
            }
        ),
        encoding="utf-8",
    )
    source = DocIndexSource(kind="fixture", index_path=index_path, docs_root=docs)

    result = read_api_target("atomic", source=source, max_chars=1000)

    assert result["status"] == "ok"
    assert result["content"] == "atomic\nAtomic API\nResidue and atom objects."
    assert result["truncated"] is False
```

- [ ] **Step 2: Run tests and verify they fail on missing functions**

Run:

```bash
uv run pytest tests/test_api_docs.py -v
```

Expected: FAIL because `DocIndexSource`, `find_doc_sources`, `search_api_index`, and `read_api_target` are not implemented.

- [ ] **Step 3: Implement the static documentation helper**

Replace `src/chimerax_mcp/api_docs.py` with:

```python
"""Static ChimeraX documentation index lookup helpers."""

from __future__ import annotations

import html.parser
import json
import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from chimerax_mcp.chimerax import detect_chimerax

PACKAGED_INDEX_NAME = "chimerax-1.9.index.json"
VALID_SEARCH_KINDS = {"all", "commands", "keywords", "modules", "tutorials"}
_INDEX_KINDS = ("commands", "tutorials", "modules")


@dataclass(frozen=True)
class DocIndexSource:
    """A static ChimeraX documentation index source."""

    kind: str
    index_path: Path | None = None
    docs_root: Path | None = None

    @classmethod
    def packaged(cls) -> DocIndexSource:
        """Return the bundled fallback source."""
        return cls(kind="packaged")

    def describe(self) -> dict[str, str | None]:
        """Return JSON-serializable source metadata."""
        return {
            "kind": self.kind,
            "index_path": str(self.index_path) if self.index_path is not None else None,
            "docs_root": str(self.docs_root) if self.docs_root is not None else None,
        }


class _HTMLTextExtractor(html.parser.HTMLParser):
    """Small HTML-to-text extractor for local ChimeraX documentation."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        _ = attrs
        if tag in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text)


def load_packaged_index() -> dict[str, Any]:
    """Load the bundled fallback ChimeraX documentation index."""
    index_path = resources.files("chimerax_mcp.resources").joinpath(PACKAGED_INDEX_NAME)
    return json.loads(index_path.read_text(encoding="utf-8"))


def _load_source_index(source: DocIndexSource) -> dict[str, Any]:
    if source.kind == "packaged" or source.index_path is None:
        return load_packaged_index()
    return json.loads(source.index_path.read_text(encoding="utf-8"))


def _find_index_file(docs_root: Path) -> Path | None:
    candidates = sorted(docs_root.glob("chimerax-*.index.json"), reverse=True)
    if candidates:
        return candidates[0]
    return None


def _docs_from_chimerax_executable(executable: Path) -> Path | None:
    mac_docs = executable.parent.parent.joinpath("share", "docs")
    if mac_docs.exists():
        return mac_docs
    linux_docs = executable.parent.parent.joinpath("share", "doc", "ChimeraX")
    if linux_docs.exists():
        return linux_docs
    sibling_docs = executable.parent.joinpath("..", "share", "docs").resolve()
    if sibling_docs.exists():
        return sibling_docs
    return None


def find_doc_sources() -> list[DocIndexSource]:
    """Find static documentation index sources in priority order."""
    sources: list[DocIndexSource] = []

    env_docs = os.environ.get("CHIMERAX_DOCS_PATH")
    if env_docs:
        docs_root = Path(env_docs).expanduser()
        index_path = _find_index_file(docs_root)
        if index_path is not None:
            sources.append(DocIndexSource(kind="env", index_path=index_path, docs_root=docs_root))

    info = detect_chimerax()
    if info is not None:
        docs_root = _docs_from_chimerax_executable(info.path)
        if docs_root is not None:
            index_path = _find_index_file(docs_root)
            if index_path is not None:
                sources.append(
                    DocIndexSource(kind="installed", index_path=index_path, docs_root=docs_root)
                )

    repo_docs = Path.cwd().joinpath("skills", "explore-chimerax", "assets", "docs")
    repo_index = Path.cwd().joinpath("skills", "explore-chimerax", "assets", PACKAGED_INDEX_NAME)
    if repo_index.exists():
        sources.append(
            DocIndexSource(
                kind="repo-skill",
                index_path=repo_index,
                docs_root=repo_docs if repo_docs.exists() else None,
            )
        )

    sources.append(DocIndexSource.packaged())
    return sources


def _best_source() -> DocIndexSource:
    return find_doc_sources()[0]


def _record_score(query_terms: list[str], name: str, record: dict[str, Any]) -> int:
    haystack = " ".join(
        [name, str(record.get("title", "")), str(record.get("description", "")), str(record.get("path", ""))]
    ).lower()
    score = 0
    for term in query_terms:
        if term == name.lower():
            score += 10
        if term in name.lower():
            score += 6
        if term in haystack:
            score += 2
    return score


def _metadata_content(name: str, kind: str, record: dict[str, Any]) -> str:
    parts = [str(record.get("title") or name)]
    description = str(record.get("description") or "").strip()
    path = str(record.get("path") or "").strip()
    if description:
        parts.append(description)
    if path:
        parts.append(f"Path: {path}")
    parts.append(
        "Full local HTML documentation was not available; this is the packaged metadata summary."
    )
    parts.append(f"Kind: {kind}")
    return "\n".join(parts)


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars < 1:
        max_chars = 1
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars].rstrip(), True


def _html_to_text(path: Path) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
    lines: list[str] = []
    for part in parser.parts:
        if part not in lines:
            lines.append(part)
    return "\n".join(lines)


def search_api_index(
    query: str,
    *,
    source: DocIndexSource | None = None,
    kind: str = "all",
    limit: int = 10,
) -> dict[str, Any]:
    """Search ChimeraX static documentation metadata."""
    normalized_kind = kind.strip().lower()
    if normalized_kind not in VALID_SEARCH_KINDS:
        return {
            "status": "error",
            "message": "kind must be one of: all, commands, keywords, modules, tutorials",
        }

    selected_source = source or _best_source()
    index = _load_source_index(selected_source)
    query_terms = [part.lower() for part in query.split() if part.strip()]
    bounded_limit = max(1, min(limit, 50))
    results: list[dict[str, Any]] = []

    if normalized_kind in {"all", "keywords"}:
        keyword_map = index.get("keywords", {})
        for term in query_terms:
            for path in keyword_map.get(term, []):
                results.append(
                    {
                        "kind": "keywords",
                        "name": term,
                        "path": path,
                        "title": f"Keyword: {term}",
                        "description": f"Keyword match for {term}",
                        "score": 1,
                    }
                )

    for record_kind in _INDEX_KINDS:
        if normalized_kind not in {"all", record_kind}:
            continue
        for name, record in index.get(record_kind, {}).items():
            score = _record_score(query_terms, name, record)
            if score > 0 or not query_terms:
                results.append(
                    {
                        "kind": record_kind,
                        "name": name,
                        "path": record.get("path"),
                        "title": record.get("title"),
                        "description": record.get("description"),
                        "score": score,
                    }
                )

    results.sort(key=lambda item: (-int(item.get("score", 0)), item["kind"], item["name"]))
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None]] = set()
    for item in results:
        key = (str(item["kind"]), str(item["name"]), item.get("path"))
        if key in seen:
            continue
        seen.add(key)
        item.pop("score", None)
        deduped.append(item)
        if len(deduped) >= bounded_limit:
            break

    return {
        "status": "ok",
        "source": selected_source.describe(),
        "version": index.get("version"),
        "results": deduped,
    }


def _resolve_target(index: dict[str, Any], target: str) -> tuple[str, str, dict[str, Any]] | None:
    stripped = target.strip()
    for record_kind in _INDEX_KINDS:
        records = index.get(record_kind, {})
        if stripped in records:
            return stripped, record_kind, records[stripped]
        for name, record in records.items():
            if stripped == record.get("path"):
                return name, record_kind, record
    return None


def read_api_target(
    target: str,
    *,
    source: DocIndexSource | None = None,
    max_chars: int = 6000,
) -> dict[str, Any]:
    """Read static documentation for a command, module, tutorial, or path."""
    selected_source = source or _best_source()
    index = _load_source_index(selected_source)
    resolved = _resolve_target(index, target)
    if resolved is None:
        return {"status": "error", "message": f"No documentation target found: {target}"}

    name, record_kind, record = resolved
    path_value = str(record.get("path") or "")
    content = _metadata_content(name, record_kind, record)
    if selected_source.docs_root is not None and path_value:
        html_path = selected_source.docs_root.joinpath(path_value)
        if html_path.exists() and html_path.is_file():
            content = _html_to_text(html_path)

    content, truncated = _truncate(content, max_chars)
    return {
        "status": "ok",
        "source": selected_source.describe(),
        "version": index.get("version"),
        "target": name,
        "kind": record_kind,
        "path": path_value,
        "content": content,
        "truncated": truncated,
    }
```

- [ ] **Step 4: Run static helper tests and verify they pass**

Run:

```bash
uv run pytest tests/test_api_docs.py -v
```

Expected: PASS.

- [ ] **Step 5: Run lint on the new helper**

Run:

```bash
uv run ruff check src/chimerax_mcp/api_docs.py tests/test_api_docs.py
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add src/chimerax_mcp/api_docs.py tests/test_api_docs.py
git commit -m "feat: add ChimeraX API doc lookup"
```

---

### Task 3: Add Live Python API Introspection Helper

**Files:**
- Create: `src/chimerax_mcp/python_api.py`
- Create: `tests/test_python_api.py`

- [ ] **Step 1: Write failing symbol-validation and script tests**

Create `tests/test_python_api.py` with:

```python
"""Tests for live ChimeraX Python API introspection helpers."""

import json
from pathlib import Path

from chimerax_mcp.python_api import (
    build_python_dir_script,
    build_python_inspect_script,
    parse_introspection_result,
    validate_symbol,
)


def test_validate_symbol_accepts_dotted_import_path():
    assert validate_symbol("chimerax.atomic.AtomicStructure") is None


def test_validate_symbol_rejects_code_execution_text():
    assert validate_symbol("__import__('os').system('id')") == (
        "symbol must be a dotted import path such as chimerax.atomic.AtomicStructure"
    )


def test_validate_symbol_rejects_dunder_segment():
    assert validate_symbol("chimerax.atomic.__class__") == "symbol must not contain dunder segments"


def test_build_python_inspect_script_contains_json_marker_and_symbol():
    script = build_python_inspect_script(
        "chimerax.atomic.AtomicStructure", include_dir=True, max_doc_chars=123
    )

    assert "CHIMERAX_MCP_PYTHON_API_JSON=" in script
    assert "chimerax.atomic.AtomicStructure" in script
    assert "max_doc_chars = 123" in script
    assert "eval(" not in script
    assert "exec(" not in script


def test_build_python_dir_script_contains_filter_and_limit():
    script = build_python_dir_script("chimerax.atomic", filter_text="res", limit=25)

    assert "filter_text = 'res'" in script
    assert "limit = 25" in script
    assert "CHIMERAX_MCP_PYTHON_API_JSON=" in script


def test_parse_introspection_result_reads_json_from_log_messages():
    payload = {"status": "ok", "symbol": "chimerax.atomic", "attributes": ["AtomicStructure"]}
    result = {
        "log_messages": {
            "note": ["noise", "CHIMERAX_MCP_PYTHON_API_JSON=" + json.dumps(payload)]
        }
    }

    assert parse_introspection_result(result) == payload


def test_parse_introspection_result_reports_missing_payload():
    result = {"log_messages": {"note": ["only noise"]}}

    assert parse_introspection_result(result) == {
        "status": "error",
        "message": "No introspection JSON payload found in ChimeraX output",
    }
```

- [ ] **Step 2: Run tests and verify they fail because `python_api.py` does not exist**

Run:

```bash
uv run pytest tests/test_python_api.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'chimerax_mcp.python_api'`.

- [ ] **Step 3: Implement live introspection helper**

Create `src/chimerax_mcp/python_api.py` with:

```python
"""Live ChimeraX Python API introspection helpers."""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import httpx

from chimerax_mcp.chimerax import ChimeraXClient

_PAYLOAD_PREFIX = "CHIMERAX_MCP_PYTHON_API_JSON="
_SYMBOL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")


def validate_symbol(symbol: str) -> str | None:
    """Validate a dotted Python symbol path for safe introspection."""
    stripped = symbol.strip()
    if not _SYMBOL_RE.match(stripped):
        return "symbol must be a dotted import path such as chimerax.atomic.AtomicStructure"
    if any(part.startswith("__") and part.endswith("__") for part in stripped.split(".")):
        return "symbol must not contain dunder segments"
    return None


def _quote_chimerax_path(path: Path) -> str:
    path_str = str(path)
    if not any(char.isspace() for char in path_str) and '"' not in path_str and "\\" not in path_str:
        return path_str
    escaped = path_str.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _resolver_script(symbol: str) -> str:
    return f"""
symbol = {symbol!r}
parts = symbol.split(".")
last_error = None
obj = None
module_name = None
attr_parts = []
for split_at in range(len(parts), 0, -1):
    candidate = ".".join(parts[:split_at])
    try:
        obj = importlib.import_module(candidate)
        module_name = candidate
        attr_parts = parts[split_at:]
        break
    except Exception as exc:
        last_error = exc
if obj is None:
    raise last_error or ImportError(symbol)
for attr in attr_parts:
    obj = getattr(obj, attr)
""".strip()


def build_python_inspect_script(symbol: str, *, include_dir: bool, max_doc_chars: int) -> str:
    """Build a ChimeraX Python script that inspects one dotted symbol."""
    bounded_doc_chars = max(1, min(max_doc_chars, 20000))
    return f"""
import importlib
import inspect
import json

payload_prefix = {_PAYLOAD_PREFIX!r}
max_doc_chars = {bounded_doc_chars}
try:
    {_resolver_script(symbol).replace(chr(10), chr(10) + '    ')}
    try:
        signature = str(inspect.signature(obj))
    except Exception:
        signature = None
    doc = inspect.getdoc(obj)
    if doc is not None and len(doc) > max_doc_chars:
        doc = doc[:max_doc_chars].rstrip()
    payload = {{
        "status": "ok",
        "symbol": symbol,
        "module": getattr(obj, "__module__", module_name),
        "type": type(obj).__name__,
        "signature": signature,
        "doc": doc,
    }}
    if {include_dir!r}:
        attrs = [name for name in dir(obj) if not (name.startswith("__") and name.endswith("__"))]
        payload["attributes"] = attrs[:100]
        payload["attributes_truncated"] = len(attrs) > 100
except Exception as exc:
    payload = {{"status": "error", "symbol": {symbol!r}, "message": f"{{type(exc).__name__}}: {{exc}}"}}
session.logger.info(payload_prefix + json.dumps(payload, ensure_ascii=False))
""".strip()


def build_python_dir_script(symbol: str, *, filter_text: str | None, limit: int) -> str:
    """Build a ChimeraX Python script that lists attributes for one dotted symbol."""
    bounded_limit = max(1, min(limit, 1000))
    return f"""
import importlib
import json

payload_prefix = {_PAYLOAD_PREFIX!r}
filter_text = {filter_text!r}
limit = {bounded_limit}
try:
    {_resolver_script(symbol).replace(chr(10), chr(10) + '    ')}
    attrs = [name for name in dir(obj) if not (name.startswith("__") and name.endswith("__"))]
    if filter_text:
        attrs = [name for name in attrs if filter_text.lower() in name.lower()]
    payload = {{
        "status": "ok",
        "symbol": symbol,
        "attributes": attrs[:limit],
        "truncated": len(attrs) > limit,
    }}
except Exception as exc:
    payload = {{"status": "error", "symbol": {symbol!r}, "message": f"{{type(exc).__name__}}: {{exc}}"}}
session.logger.info(payload_prefix + json.dumps(payload, ensure_ascii=False))
""".strip()


def parse_introspection_result(result: dict[str, Any]) -> dict[str, Any]:
    """Extract the JSON payload emitted by an introspection script."""
    messages = result.get("log_messages", {})
    for level in ("info", "note", "warning", "error"):
        for line in messages.get(level, []):
            if isinstance(line, str) and line.startswith(_PAYLOAD_PREFIX):
                return json.loads(line[len(_PAYLOAD_PREFIX) :])
    return {
        "status": "error",
        "message": "No introspection JSON payload found in ChimeraX output",
    }


def run_python_api_script(client: ChimeraXClient, script: str) -> dict[str, Any]:
    """Run an introspection script in ChimeraX and parse its JSON payload."""
    fd, script_path_str = tempfile.mkstemp(suffix=".py", prefix="chimerax_python_api_")
    os.close(fd)
    script_path = Path(script_path_str)
    try:
        script_path.write_text(script, encoding="utf-8")
        result = client.run_command(f"runscript {_quote_chimerax_path(script_path)}")
    except httpx.HTTPError as exc:
        return {"status": "error", "message": f"HTTP error: {exc}"}
    finally:
        with contextlib.suppress(OSError):
            script_path.unlink()

    if result.get("error") is not None:
        err = result["error"]
        if isinstance(err, dict):
            return {
                "status": "error",
                "error_type": err.get("type", "Unknown"),
                "message": err.get("message", "Unknown error"),
            }
        return {"status": "error", "message": str(err)}
    return parse_introspection_result(result)
```

- [ ] **Step 4: Run helper tests and verify they pass**

Run:

```bash
uv run pytest tests/test_python_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Run lint on the helper**

Run:

```bash
uv run ruff check src/chimerax_mcp/python_api.py tests/test_python_api.py
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add src/chimerax_mcp/python_api.py tests/test_python_api.py
git commit -m "feat: add ChimeraX Python API introspection helper"
```

---

### Task 4: Wire API Reference Tools into the MCP Server

**Files:**
- Modify: `src/chimerax_mcp/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Add failing server-tool tests**

Append this code to `tests/test_server.py`:

```python
from chimerax_mcp.server import (
    chimerax_api_read,
    chimerax_api_search,
    chimerax_python_dir,
    chimerax_python_inspect,
)


class TestApiReferenceTools:
    def test_chimerax_api_search_finds_atomic_module(self):
        result = chimerax_api_search.fn(query="AtomicStructure residues", kind="modules", limit=5)

        assert result["status"] == "ok"
        assert any(item["name"] == "atomic" for item in result["results"])

    def test_chimerax_api_read_reads_atomic_metadata(self):
        result = chimerax_api_read.fn(target="atomic", max_chars=500)

        assert result["status"] == "ok"
        assert result["target"] == "atomic"
        assert "Atomic structures" in result["content"]

    def test_chimerax_python_inspect_not_running(self):
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: False  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_python_inspect.fn(symbol="chimerax.atomic.AtomicStructure")

        assert result == {"status": "error", "message": "ChimeraX is not running"}

    def test_chimerax_python_inspect_rejects_unsafe_symbol(self):
        result = chimerax_python_inspect.fn(symbol="__import__('os').system('id')")

        assert result["status"] == "error"
        assert "dotted import path" in result["message"]

    def test_chimerax_python_dir_delegates_to_runscript(self):
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]

        def fake_run_command(command: str):
            assert command.startswith("runscript ")
            return {
                "log_messages": {
                    "note": [
                        'CHIMERAX_MCP_PYTHON_API_JSON={"status":"ok","symbol":"chimerax.atomic","attributes":["AtomicStructure"],"truncated":false}'
                    ]
                },
                "error": None,
            }

        mock_client.run_command = fake_run_command  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_python_dir.fn(symbol="chimerax.atomic", filter="Atomic", limit=10)

        assert result == {
            "status": "ok",
            "symbol": "chimerax.atomic",
            "attributes": ["AtomicStructure"],
            "truncated": False,
        }
```

- [ ] **Step 2: Run server tests and verify they fail on missing imports/tools**

Run:

```bash
uv run pytest tests/test_server.py::TestApiReferenceTools -v
```

Expected: FAIL because the new MCP tool functions do not exist.

- [ ] **Step 3: Add imports to `server.py`**

In `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/src/chimerax_mcp/server.py`, add these imports near the existing project imports:

```python
from chimerax_mcp.api_docs import read_api_target, search_api_index
from chimerax_mcp.python_api import (
    build_python_dir_script,
    build_python_inspect_script,
    run_python_api_script,
    validate_symbol,
)
```

- [ ] **Step 4: Add static API MCP tools to `server.py`**

Add this code after `chimerax_models` or near the other information-oriented tools:

```python
@mcp.tool()
def chimerax_api_search(
    query: str,
    kind: str = "all",
    limit: int = 10,
) -> dict[str, Any]:
    """Search static ChimeraX command, tutorial, and Python API module metadata.

    This tool works without optional local skills by falling back to a packaged
    lightweight ChimeraX documentation index.
    """
    return search_api_index(query=query, kind=kind, limit=limit)


@mcp.tool()
def chimerax_api_read(target: str, max_chars: int = 6000) -> dict[str, Any]:
    """Read a static ChimeraX documentation entry or packaged metadata summary."""
    return read_api_target(target=target, max_chars=max_chars)
```

- [ ] **Step 5: Add live Python API MCP tools to `server.py`**

Add this code after the static API tools:

```python
@mcp.tool()
def chimerax_python_inspect(
    symbol: str,
    include_dir: bool = True,
    max_doc_chars: int = 4000,
) -> dict[str, Any]:
    """Inspect a live ChimeraX Python API symbol via a bounded runscript helper."""
    validation_error = validate_symbol(symbol)
    if validation_error is not None:
        return {"status": "error", "message": validation_error}

    client = get_client()
    if not client.is_running():
        return {"status": "error", "message": "ChimeraX is not running"}

    script = build_python_inspect_script(
        symbol.strip(), include_dir=include_dir, max_doc_chars=max_doc_chars
    )
    return run_python_api_script(client, script)


@mcp.tool()
def chimerax_python_dir(
    symbol: str,
    filter: str | None = None,  # noqa: A002
    limit: int = 100,
) -> dict[str, Any]:
    """List attributes of a live ChimeraX Python API symbol via runscript."""
    validation_error = validate_symbol(symbol)
    if validation_error is not None:
        return {"status": "error", "message": validation_error}

    client = get_client()
    if not client.is_running():
        return {"status": "error", "message": "ChimeraX is not running"}

    script = build_python_dir_script(symbol.strip(), filter_text=filter, limit=limit)
    return run_python_api_script(client, script)
```

- [ ] **Step 6: Run new server-tool tests and verify they pass**

Run:

```bash
uv run pytest tests/test_server.py::TestApiReferenceTools -v
```

Expected: PASS.

- [ ] **Step 7: Run all server tests**

Run:

```bash
uv run pytest tests/test_server.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 4**

Run:

```bash
git add src/chimerax_mcp/server.py tests/test_server.py
git commit -m "feat: expose ChimeraX API reference tools"
```

---

### Task 5: Add Release-Time Index Generation Script

**Files:**
- Create: `scripts/build_chimerax_doc_index.py`
- Test: `tests/test_api_docs.py`

- [ ] **Step 1: Add a failing smoke test for script importability**

Append this code to `tests/test_api_docs.py`:

```python
def test_build_doc_index_script_exists():
    script = Path("scripts/build_chimerax_doc_index.py")

    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "def build_index" in text
    assert "def find_default_docs_path" in text
```

- [ ] **Step 2: Run the test and verify it fails because the script does not exist**

Run:

```bash
uv run pytest tests/test_api_docs.py::test_build_doc_index_script_exists -v
```

Expected: FAIL with `AssertionError` on `script.exists()`.

- [ ] **Step 3: Create the generation script**

Create `scripts/build_chimerax_doc_index.py` with this implementation, reusing the existing parser logic and adding docs auto-detection:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Build a lightweight ChimeraX documentation index for package resources."""

from __future__ import annotations

import html.parser
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path


class HTMLTextExtractor(html.parser.HTMLParser):
    """Extract title, headings, and plain text from HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.headings: list[tuple[str, str]] = []
        self.text_parts: list[str] = []
        self._in_title = False
        self._in_heading = False
        self._heading_level = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        _ = attrs
        if tag == "title":
            self._in_title = True
        elif tag in {"h1", "h2", "h3", "h4"}:
            self._in_heading = True
            self._heading_level = tag

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag in {"h1", "h2", "h3", "h4"}:
            self._in_heading = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title = text
        elif self._in_heading:
            self.headings.append((self._heading_level, text))
        self.text_parts.append(text)


def extract_html_info(filepath: Path) -> dict[str, object] | None:
    """Extract searchable metadata from one HTML file."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    parser = HTMLTextExtractor()
    parser.feed(content)
    if not parser.title:
        return None
    text = " ".join(parser.text_parts)
    description = text[:300] + "..." if len(text) > 300 else text
    return {"title": parser.title, "headings": parser.headings[:10], "description": description}


def parse_command_title(title: str) -> list[str]:
    """Extract command names from a ChimeraX command documentation title."""
    match = re.match(r"Command:\s*(.+)", title, re.IGNORECASE)
    if not match:
        return []
    names = [name.strip() for name in match.group(1).split(",")]
    return [name for name in names if name and not name.startswith("(")]


def build_commands_index(commands_dir: Path) -> dict[str, dict[str, str]]:
    """Index ChimeraX user command documentation files."""
    commands: dict[str, dict[str, str]] = {}
    for html_file in sorted(commands_dir.glob("*.html")):
        info = extract_html_info(html_file)
        if not info:
            continue
        names = parse_command_title(str(info["title"])) or [html_file.stem]
        rel_path = f"user/commands/{html_file.name}"
        for name in names:
            commands[name] = {
                "path": rel_path,
                "title": str(info["title"]),
                "description": str(info["description"])[:200],
            }
    return commands


def build_tutorials_index(devel_dir: Path) -> dict[str, dict[str, str]]:
    """Index ChimeraX developer tutorials."""
    tutorials: dict[str, dict[str, str]] = {}
    tutorials_dir = devel_dir.joinpath("tutorials")
    if not tutorials_dir.exists():
        return tutorials
    for html_file in sorted(tutorials_dir.glob("*.html")):
        info = extract_html_info(html_file)
        if not info:
            continue
        tutorials[html_file.stem] = {
            "path": f"devel/tutorials/{html_file.name}",
            "title": str(info["title"]),
            "description": str(info["description"])[:200],
        }
    return tutorials


def build_modules_index(devel_dir: Path) -> dict[str, dict[str, str]]:
    """Index ChimeraX Python API module documentation."""
    modules: dict[str, dict[str, str]] = {}
    modules_dir = devel_dir.joinpath("modules")
    if not modules_dir.exists():
        return modules
    for item in sorted(modules_dir.iterdir()):
        if not item.is_dir():
            continue
        index_file = item.joinpath("index.html")
        if not index_file.exists():
            index_file = item.joinpath(f"{item.name}.html")
        if not index_file.exists():
            html_files = list(item.glob("*.html"))
            if not html_files:
                continue
            index_file = html_files[0]
        info = extract_html_info(index_file)
        if not info:
            continue
        modules[item.name] = {
            "path": f"devel/modules/{item.name}/{index_file.name}",
            "title": str(info["title"]),
            "description": str(info["description"])[:200],
        }
    return modules


def build_keywords_index(
    commands: dict[str, dict[str, str]],
    tutorials: dict[str, dict[str, str]],
    modules: dict[str, dict[str, str]],
) -> dict[str, list[str]]:
    """Build a keyword-to-path lookup from indexed metadata."""
    keywords: dict[str, list[str]] = {}
    stop_words = {
        "this", "that", "with", "from", "have", "been", "will", "which", "their",
        "they", "there", "these", "those", "when", "where", "command", "commands",
        "chimerax", "html",
    }

    def add_keywords(text: str, path: str) -> None:
        words = re.findall(r"\b[a-z]{4,}\b", text.lower())
        for word in set(words):
            if word not in stop_words:
                keywords.setdefault(word, []).append(path)

    for name, info in commands.items():
        add_keywords(name, info["path"])
        add_keywords(info.get("description", ""), info["path"])
    for name, info in tutorials.items():
        add_keywords(name, info["path"])
        add_keywords(info.get("title", ""), info["path"])
    for name, info in modules.items():
        add_keywords(name, info["path"])
        add_keywords(info.get("title", ""), info["path"])

    return {key: sorted(set(paths))[:10] for key, paths in sorted(keywords.items()) if paths}


def build_index(docs_path: Path, version: str) -> dict[str, object]:
    """Build the complete lightweight ChimeraX documentation index."""
    commands_dir = docs_path.joinpath("user", "commands")
    devel_dir = docs_path.joinpath("devel")
    commands = build_commands_index(commands_dir) if commands_dir.exists() else {}
    tutorials = build_tutorials_index(devel_dir) if devel_dir.exists() else {}
    modules = build_modules_index(devel_dir) if devel_dir.exists() else {}
    return {
        "version": version,
        "created": datetime.now(UTC).isoformat(),
        "commands": commands,
        "tutorials": tutorials,
        "modules": modules,
        "keywords": build_keywords_index(commands, tutorials, modules),
    }


def find_default_docs_path() -> Path | None:
    """Find a local ChimeraX docs directory for release-time index generation."""
    candidates = sorted(Path("/Applications").glob("ChimeraX*.app/Contents/share/docs"), reverse=True)
    candidates.extend(sorted(Path("/Applications").glob("UCSF-ChimeraX*.app/Contents/share/docs"), reverse=True))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def main() -> int:
    """CLI entry point."""
    if len(sys.argv) not in {3, 4}:
        print("Usage: build_chimerax_doc_index.py <docs_path|auto> <version> [output_path]")
        return 1
    docs_arg = sys.argv[1]
    docs_path = find_default_docs_path() if docs_arg == "auto" else Path(docs_arg).expanduser()
    if docs_path is None or not docs_path.exists():
        print(f"Error: docs path not found: {docs_arg}")
        return 1
    version = sys.argv[2]
    output_path = (
        Path(sys.argv[3])
        if len(sys.argv) == 4
        else Path("src/chimerax_mcp/resources").joinpath(f"chimerax-{version}.index.json")
    )
    index = build_index(docs_path, version)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Index written to: {output_path}")
    print(f"  Commands: {len(index['commands'])}")
    print(f"  Tutorials: {len(index['tutorials'])}")
    print(f"  Modules: {len(index['modules'])}")
    print(f"  Keywords: {len(index['keywords'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Make the script executable**

Run:

```bash
chmod +x scripts/build_chimerax_doc_index.py
```

- [ ] **Step 5: Run the script test and lint**

Run:

```bash
uv run pytest tests/test_api_docs.py::test_build_doc_index_script_exists -v
uv run ruff check scripts/build_chimerax_doc_index.py tests/test_api_docs.py
```

Expected: both commands PASS.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add scripts/build_chimerax_doc_index.py tests/test_api_docs.py
git commit -m "chore: add ChimeraX doc index builder"
```

---

### Task 6: Update README and Run Final Verification

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md` if this repository keeps unreleased user-visible changes there.

- [ ] **Step 1: Update README feature list**

In `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/README.md`, add this bullet to the Features list:

```markdown
- **API Reference**: Search packaged/local ChimeraX docs and inspect live Python API symbols via safe `runscript` helpers
```

- [ ] **Step 2: Add README tool table section**

After the `Rich Log Output` tool table, add:

```markdown
### API Reference and Python Introspection

| Tool | Description |
|------|-------------|
| `chimerax_api_search` | Search static ChimeraX command, tutorial, and Python API module metadata; works without optional skills by using a packaged lightweight index |
| `chimerax_api_read` | Read a static documentation entry from local docs when available, or return the packaged metadata summary |
| `chimerax_python_inspect` | Inspect a live ChimeraX Python API symbol via `runscript` using bounded `inspect` output |
| `chimerax_python_dir` | List attributes of a live ChimeraX Python API symbol with optional substring filtering |

Static lookup uses `CHIMERAX_DOCS_PATH` first, then detected local ChimeraX docs, then repository-local skill docs when running from a checkout, and finally the packaged fallback index. Live introspection requires ChimeraX to be running and accepts only dotted symbols such as `chimerax.atomic.AtomicStructure`; it does not expose arbitrary Python evaluation.
```

- [ ] **Step 3: Add README examples**

After the existing Rich Log Examples section, add:

```markdown
## API Reference Examples

Search the packaged/local static index:

```json
{
  "query": "AtomicStructure residues",
  "kind": "modules",
  "limit": 5
}
```

Read a module entry:

```json
{
  "target": "atomic",
  "max_chars": 4000
}
```

Inspect the live API in a running ChimeraX session:

```json
{
  "symbol": "chimerax.atomic.AtomicStructure",
  "include_dir": true,
  "max_doc_chars": 4000
}
```
```

- [ ] **Step 4: Update CHANGELOG if it has an Unreleased section**

Open `/Users/nagaet/ghq/github.com/N283T/chimerax-mcp-plus/CHANGELOG.md`. If it contains an `Unreleased` heading, add this bullet under it:

```markdown
- Add skill-independent ChimeraX API reference tools with packaged static lookup and live `runscript` introspection.
```

If there is no `Unreleased` heading, do not edit `CHANGELOG.md` in this task.

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/test_api_docs.py tests/test_python_api.py tests/test_server.py -v
```

Expected: PASS.

- [ ] **Step 6: Run full test suite**

Run:

```bash
uv run pytest
```

Expected: `134` existing tests plus new tests pass. The final count will be higher than 134.

- [ ] **Step 7: Run lint and type checks**

Run:

```bash
uv run ruff check .
uv run ty check .
```

Expected: both commands PASS.

- [ ] **Step 8: Build the wheel and verify resource inclusion**

Run:

```bash
rm -rf dist
uv build --wheel
python - <<'PY'
import zipfile
from pathlib import Path
wheel = sorted(Path('dist').glob('chimerax_mcp_plus-*.whl'))[-1]
with zipfile.ZipFile(wheel) as zf:
    names = set(zf.namelist())
assert 'chimerax_mcp/resources/chimerax-1.9.index.json' in names
print(f'Verified resource in {wheel}')
PY
```

Expected: `Verified resource in dist/chimerax_mcp_plus-...whl`.

- [ ] **Step 9: Commit Task 6**

Run:

```bash
git add README.md CHANGELOG.md pyproject.toml src/chimerax_mcp tests scripts
git commit -m "docs: document ChimeraX API reference tools"
```

If `CHANGELOG.md` was not edited, `git add CHANGELOG.md` is harmless and stages nothing.

---

## Final Review Checklist

- [ ] `chimerax_api_search` works without optional skills by using the packaged index.
- [ ] `chimerax_api_read` returns local HTML text when docs are available and packaged metadata otherwise.
- [ ] `chimerax_python_inspect` and `chimerax_python_dir` reject unsafe symbols before checking ChimeraX state.
- [ ] Live introspection uses temporary files and `runscript`, then cleans up the files.
- [ ] Full tests, lint, type checks, and wheel build pass.
- [ ] README explains source priority and the no-arbitrary-eval safety boundary.
