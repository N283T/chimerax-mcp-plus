"""Static ChimeraX documentation index lookup helpers."""

from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from importlib import resources
from pathlib import Path
from typing import Any

PACKAGED_INDEX_NAME = "chimerax-1.9.index.json"
VALID_KINDS = ("all", "commands", "keywords", "modules", "tutorials")
SEARCH_KINDS = ("commands", "tutorials", "modules")
KIND_ERROR = "kind must be one of: all, commands, keywords, modules, tutorials"


@dataclass(frozen=True)
class DocIndexSource:
    """Location metadata for a ChimeraX documentation index."""

    kind: str
    index_path: Path | None = None
    docs_root: Path | None = None

    @classmethod
    def packaged(cls) -> DocIndexSource:
        """Return the bundled fallback index source."""
        return cls(kind="packaged")

    def describe(self) -> dict[str, str | None]:
        """Return JSON-serializable source metadata."""
        return {
            "kind": self.kind,
            "index_path": str(self.index_path) if self.index_path is not None else None,
            "docs_root": str(self.docs_root) if self.docs_root is not None else None,
        }


def load_packaged_index() -> dict[str, Any]:
    """Load the bundled fallback ChimeraX documentation index."""
    index_path = resources.files("chimerax_mcp.resources").joinpath(PACKAGED_INDEX_NAME)
    return json.loads(index_path.read_text(encoding="utf-8"))


def find_doc_sources() -> list[DocIndexSource]:
    """Find available ChimeraX documentation index sources in priority order."""
    sources: list[DocIndexSource] = []
    seen: set[str] = set()

    env_docs = os.environ.get("CHIMERAX_DOCS_PATH")
    if env_docs:
        sources.extend(_sources_from_docs_root(Path(env_docs), kind="env", seen=seen))

    for docs_root in _candidate_chimerax_docs_roots():
        sources.extend(_sources_from_docs_root(docs_root, kind="chimerax", seen=seen))

    repo_root = _repo_root()
    if repo_root is not None:
        skill_assets = repo_root.joinpath("skills", "explore-chimerax", "assets")
        skill_docs_root = skill_assets.joinpath("docs")
        sources.extend(
            _sources_from_docs_root(
                skill_docs_root if skill_docs_root.exists() else skill_assets,
                kind="repo-skill",
                seen=seen,
                index_root=skill_assets,
            )
        )

    sources.append(DocIndexSource.packaged())
    return sources


def search_api_index(
    query: str,
    source: DocIndexSource | None = None,
    kind: str = "all",
    limit: int = 10,
) -> dict[str, Any]:
    """Search a ChimeraX API documentation index."""
    if kind not in VALID_KINDS:
        return {"status": "error", "message": KIND_ERROR}

    source = source or find_doc_sources()[0]
    index = _load_source_index(source)
    bounded_limit = min(max(limit, 1), 50)
    tokens = _query_tokens(query)
    results = _rank_index_records(index, tokens, kind)[:bounded_limit]
    return {
        "status": "ok",
        "source": source.describe(),
        "version": index.get("version"),
        "query": query,
        "kind": kind,
        "limit": bounded_limit,
        "results": results,
    }


def read_api_target(
    target: str,
    source: DocIndexSource | None = None,
    max_chars: int = 6000,
) -> dict[str, Any]:
    """Read a ChimeraX API documentation target as bounded plain text."""
    source = source or find_doc_sources()[0]
    index = _load_source_index(source)
    resolved = _resolve_target(index, target)
    if resolved is None:
        return {
            "status": "error",
            "message": f"target not found: {target}",
            "source": source.describe(),
            "target": target,
        }

    resolved_kind, name, record = resolved
    content = _metadata_summary(name, record)
    html_path = _local_html_path(source, record)
    if html_path is not None and html_path.exists():
        content = _html_to_text(html_path.read_text(encoding="utf-8", errors="replace"))

    bounded_max_chars = max(max_chars, 0)
    truncated = len(content) > bounded_max_chars
    if truncated:
        content = content[:bounded_max_chars]

    return {
        "status": "ok",
        "source": source.describe(),
        "version": index.get("version"),
        "target": name,
        "kind": resolved_kind,
        "path": record.get("path"),
        "title": record.get("title"),
        "content": content,
        "truncated": truncated,
    }


def _sources_from_docs_root(
    docs_root: Path,
    kind: str,
    seen: set[str],
    index_root: Path | None = None,
) -> list[DocIndexSource]:
    if not docs_root.exists():
        return []
    index_root = index_root or docs_root
    found: list[DocIndexSource] = []
    for index_path in sorted(index_root.glob("chimerax-*.index.json")):
        key = str(index_path.resolve())
        if key in seen:
            continue
        seen.add(key)
        found.append(DocIndexSource(kind=kind, index_path=index_path, docs_root=docs_root))
    if not found:
        key = f"{kind}:{docs_root.resolve()}"
        if key not in seen:
            seen.add(key)
            found.append(DocIndexSource(kind=kind, index_path=None, docs_root=docs_root))
    return found


def _candidate_chimerax_docs_roots() -> list[Path]:
    candidates = [
        Path("/Applications/ChimeraX.app").joinpath("Contents", "share", "docs"),
    ]
    applications = Path("/Applications")
    if applications.exists():
        candidates.extend(
            app.joinpath("Contents", "share", "docs")
            for app in sorted(applications.glob("ChimeraX*.app"))
        )
    return candidates


def _repo_root() -> Path | None:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if parent.joinpath("pyproject.toml").exists() and parent.joinpath("skills").exists():
            return parent
    return None


def _load_source_index(source: DocIndexSource) -> dict[str, Any]:
    if source.kind == "packaged" or source.index_path is None:
        return load_packaged_index()
    return json.loads(source.index_path.read_text(encoding="utf-8"))


def _query_tokens(query: str) -> list[str]:
    expanded = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", query)
    return [token.lower() for token in re.findall(r"[A-Za-z0-9]+", expanded)]


def _rank_index_records(
    index: dict[str, Any],
    tokens: list[str],
    kind: str,
) -> list[dict[str, Any]]:
    candidates: list[tuple[int, str, str, dict[str, Any]]] = []
    kinds = SEARCH_KINDS if kind == "all" else (kind,)
    for candidate_kind in kinds:
        if candidate_kind == "keywords":
            continue
        for name, record in index.get(candidate_kind, {}).items():
            score = _record_score(name, record, tokens)
            if score > 0:
                candidates.append((score, candidate_kind, name, record))

    if kind in ("all", "keywords"):
        for name, paths in index.get("keywords", {}).items():
            score = _keyword_score(name, paths, tokens)
            if score > 0:
                candidates.append((score, "keywords", name, {"paths": paths}))

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [
        _result_item(score, candidate_kind, name, record)
        for score, candidate_kind, name, record in candidates
    ]


def _record_score(name: str, record: dict[str, Any], tokens: list[str]) -> int:
    haystacks = {
        "name": name.lower(),
        "path": str(record.get("path", "")).lower(),
        "title": str(record.get("title", "")).lower(),
        "description": str(record.get("description", "")).lower(),
    }
    score = 0
    for token in tokens:
        if token == haystacks["name"]:
            score += 100
        if token in haystacks["name"]:
            score += 40
        if token in haystacks["title"]:
            score += 20
        if token in haystacks["path"]:
            score += 10
        if token in haystacks["description"]:
            score += 5
    return score


def _keyword_score(name: str, paths: list[str], tokens: list[str]) -> int:
    haystack = " ".join([name, *paths]).lower()
    return sum(30 if token == name.lower() else 10 for token in tokens if token in haystack)


def _result_item(score: int, kind: str, name: str, record: dict[str, Any]) -> dict[str, Any]:
    item: dict[str, Any] = {"kind": kind, "name": name, "score": score}
    for key in ("path", "title", "description", "paths"):
        if key in record:
            item[key] = record[key]
    return item


def _resolve_target(index: dict[str, Any], target: str) -> tuple[str, str, dict[str, Any]] | None:
    normalized = target.strip().lower()
    for kind in SEARCH_KINDS:
        records = index.get(kind, {})
        for name, record in records.items():
            path = str(record.get("path", ""))
            if normalized in {name.lower(), path.lower()} or Path(path).name.lower() == normalized:
                return kind, name, record
    return None


def _metadata_summary(name: str, record: dict[str, Any]) -> str:
    parts = [name, str(record.get("title", "")), str(record.get("description", ""))]
    return _dedupe_parts(part.strip() for part in parts if part.strip())


def _local_html_path(source: DocIndexSource, record: dict[str, Any]) -> Path | None:
    docs_root = source.docs_root
    path = record.get("path")
    if docs_root is None or not path:
        return None
    relative_path = Path(str(path))
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return None
    docs_root_resolved = docs_root.resolve()
    candidate = docs_root_resolved.joinpath(*relative_path.parts).resolve()
    try:
        candidate.relative_to(docs_root_resolved)
    except ValueError:
        return None
    return candidate


class _PlainTextHTMLParser(HTMLParser):
    _SEPARATOR = "\n"
    _BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "title",
        "tr",
        "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style"}:
            self._ignored_depth += 1
            return
        if tag in self._BLOCK_TAGS:
            self.parts.append(self._SEPARATOR)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if tag in self._BLOCK_TAGS:
            self.parts.append(self._SEPARATOR)

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        text = _normalize_whitespace(html.unescape(data))
        if text:
            self.parts.append(text)


def _html_to_text(source: str) -> str:
    parser = _PlainTextHTMLParser()
    parser.feed(source)
    parser.close()
    lines: list[str] = []
    current: list[str] = []
    for part in parser.parts:
        if part == parser._SEPARATOR:
            if current:
                lines.append(_normalize_whitespace(" ".join(current)))
                current = []
            continue
        current.append(part)
    if current:
        lines.append(_normalize_whitespace(" ".join(current)))
    return _dedupe_parts(line for line in lines if line)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _dedupe_parts(parts: Any) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for part in parts:
        normalized = _normalize_whitespace(str(part))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        lines.append(normalized)
    return "\n".join(lines)
