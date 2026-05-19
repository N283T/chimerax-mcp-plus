#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Build a lightweight ChimeraX documentation index from local HTML docs."""

from __future__ import annotations

import html.parser
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict


class HtmlInfo(TypedDict):
    """Extracted HTML metadata used by the index."""

    title: str
    headings: list[tuple[str, str]]
    text: str
    description: str


class DocIndex(TypedDict):
    """JSON-serializable ChimeraX docs index."""

    version: str
    created: str
    commands: dict[str, dict[str, str]]
    tutorials: dict[str, dict[str, str]]
    modules: dict[str, dict[str, str]]
    keywords: dict[str, list[str]]


class HTMLTextExtractor(html.parser.HTMLParser):
    """Extract title, headings, and visible text from an HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.headings: list[tuple[str, str]] = []
        self.text_parts: list[str] = []
        self._in_title = False
        self._title_parts: list[str] = []
        self._heading_level = ""
        self._heading_parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        normalized = tag.lower()
        if normalized in {"script", "style", "noscript"}:
            self._skip_depth += 1
        elif normalized == "title":
            self._in_title = True
            self._title_parts = []
        elif normalized in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._heading_level = normalized
            self._heading_parts = []

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        elif normalized == "title":
            self._in_title = False
            title = _normalize_spaces(" ".join(self._title_parts))
            if title:
                self.title = title
        elif normalized == self._heading_level:
            heading = _normalize_spaces(" ".join(self._heading_parts))
            if heading:
                self.headings.append((self._heading_level, heading))
            self._heading_level = ""
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = _normalize_spaces(data)
        if not text:
            return
        if self._in_title:
            self._title_parts.append(text)
        if self._heading_level:
            self._heading_parts.append(text)
        self.text_parts.append(text)


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _relative_html_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _short_description(text: str, limit: int = 300) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def extract_html_info(filepath: Path) -> HtmlInfo | None:
    """Extract title, headings, and text metadata from an HTML file."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    parser = HTMLTextExtractor()
    parser.feed(content)

    text = _normalize_spaces(" ".join(parser.text_parts))
    title = parser.title or (parser.headings[0][1] if parser.headings else filepath.stem)
    if not title and not text:
        return None

    return {
        "title": title,
        "headings": parser.headings[:10],
        "text": text,
        "description": _short_description(text),
    }


def parse_command_title(title: str) -> list[str]:
    """Extract command names from titles like ``Command: color, rainbow``."""
    match = re.match(r"Command:\s*(.+)", title, re.IGNORECASE)
    if not match:
        return []

    names = []
    for name in match.group(1).split(","):
        clean_name = name.strip()
        if clean_name and not clean_name.startswith("("):
            names.append(clean_name)
    return names


def build_commands_index(commands_dir: Path) -> dict[str, dict[str, str]]:
    """Index ChimeraX command reference HTML files."""
    commands: dict[str, dict[str, str]] = {}
    docs_root = commands_dir.parent.parent

    for html_file in sorted(commands_dir.glob("*.html")):
        info = extract_html_info(html_file)
        if info is None:
            continue

        command_names = parse_command_title(info["title"]) or [html_file.stem]
        rel_path = _relative_html_path(html_file, docs_root)
        for command_name in command_names:
            commands[command_name] = {
                "path": rel_path,
                "title": info["title"],
                "description": _short_description(info["description"], 200),
            }

    return commands


def build_tutorials_index(devel_dir: Path) -> dict[str, dict[str, str]]:
    """Index developer tutorial HTML files."""
    tutorials: dict[str, dict[str, str]] = {}
    tutorials_dir = devel_dir.joinpath("tutorials")
    docs_root = devel_dir.parent
    if not tutorials_dir.exists():
        return tutorials

    for html_file in sorted(tutorials_dir.glob("*.html")):
        info = extract_html_info(html_file)
        if info is None:
            continue

        tutorials[html_file.stem] = {
            "path": _relative_html_path(html_file, docs_root),
            "title": info["title"],
            "description": _short_description(info["description"], 200),
        }

    return tutorials


def build_modules_index(devel_dir: Path) -> dict[str, dict[str, str]]:
    """Index developer API module HTML files."""
    modules: dict[str, dict[str, str]] = {}
    modules_dir = devel_dir.joinpath("modules")
    docs_root = devel_dir.parent
    if not modules_dir.exists():
        return modules

    for module_dir in sorted(modules_dir.iterdir()):
        if not module_dir.is_dir():
            continue

        html_file = module_dir.joinpath("index.html")
        if not html_file.exists():
            html_file = module_dir.joinpath(f"{module_dir.name}.html")
        if not html_file.exists():
            candidates = sorted(module_dir.glob("*.html"))
            if not candidates:
                continue
            html_file = candidates[0]

        info = extract_html_info(html_file)
        if info is None:
            continue

        modules[module_dir.name] = {
            "path": _relative_html_path(html_file, docs_root),
            "title": info["title"],
            "description": _short_description(info["description"], 200),
        }

    return modules


def build_keywords_index(
    commands: dict[str, dict[str, str]],
    tutorials: dict[str, dict[str, str]],
    modules: dict[str, dict[str, str]],
) -> dict[str, list[str]]:
    """Build a compact keyword-to-path lookup from indexed entries."""
    keywords: dict[str, set[str]] = {}
    stop_words = {
        "been",
        "command",
        "commands",
        "from",
        "have",
        "html",
        "that",
        "their",
        "there",
        "these",
        "they",
        "this",
        "those",
        "when",
        "where",
        "which",
        "will",
        "with",
        "chimerax",
    }

    def add_keywords(text: str, path: str) -> None:
        for word in set(re.findall(r"\b[a-z][a-z0-9_]{3,}\b", text.lower())):
            if word not in stop_words:
                keywords.setdefault(word, set()).add(path)

    for entries in (commands, tutorials, modules):
        for name, info in entries.items():
            path = info["path"]
            add_keywords(name, path)
            add_keywords(info.get("title", ""), path)
            add_keywords(info.get("description", ""), path)

    return {key: sorted(paths)[:10] for key, paths in sorted(keywords.items()) if paths}


def build_index(docs_path: Path, version: str) -> DocIndex:
    """Build the complete ChimeraX documentation index."""
    docs_path = docs_path.resolve()
    commands_dir = docs_path.joinpath("user", "commands")
    devel_dir = docs_path.joinpath("devel")

    commands = build_commands_index(commands_dir) if commands_dir.exists() else {}
    tutorials = build_tutorials_index(devel_dir) if devel_dir.exists() else {}
    modules = build_modules_index(devel_dir) if devel_dir.exists() else {}
    keywords = build_keywords_index(commands, tutorials, modules)

    return {
        "version": version,
        "created": datetime.now(UTC).isoformat(),
        "commands": commands,
        "tutorials": tutorials,
        "modules": modules,
        "keywords": keywords,
    }


def _chimerax_path_docs_candidate(executable_path: str) -> Path | None:
    executable = Path(executable_path).expanduser()
    contents_dir = executable.parent.parent
    docs_dir = contents_dir.joinpath("share", "docs")
    return docs_dir if docs_dir.exists() else None


def find_default_docs_path() -> Path | None:
    """Find a likely local ChimeraX docs directory."""
    env_docs = os.environ.get("CHIMERAX_DOCS_PATH")
    if env_docs:
        docs_path = Path(env_docs).expanduser()
        if docs_path.exists():
            return docs_path

    chimerax_path = os.environ.get("CHIMERAX_PATH")
    if chimerax_path:
        docs_path = _chimerax_path_docs_candidate(chimerax_path)
        if docs_path is not None:
            return docs_path

    applications_dir = Path("/Applications")
    patterns = [
        "ChimeraX*.app/Contents/share/docs",
        "UCSF-ChimeraX*.app/Contents/share/docs",
    ]
    for pattern in patterns:
        for docs_path in sorted(applications_dir.glob(pattern)):
            if docs_path.exists():
                return docs_path

    return None


def _default_output_path(version: str) -> Path:
    return Path("src").joinpath("chimerax_mcp", "resources", f"chimerax-{version}.index.json")


def main() -> int:
    """Command-line entry point."""
    if len(sys.argv) < 3:
        print(
            "Usage: build_chimerax_doc_index.py <docs_path|auto> <version> [output_path]",
            file=sys.stderr,
        )
        return 2

    docs_arg = sys.argv[1]
    version = sys.argv[2]
    output_path = Path(sys.argv[3]) if len(sys.argv) > 3 else _default_output_path(version)

    if docs_arg == "auto":
        docs_path = find_default_docs_path()
        if docs_path is None:
            print("Error: could not auto-detect a local ChimeraX docs path", file=sys.stderr)
            return 2
    else:
        docs_path = Path(docs_arg).expanduser()

    if not docs_path.exists():
        print(f"Error: path does not exist: {docs_path}", file=sys.stderr)
        return 2
    if not docs_path.is_dir():
        print(f"Error: path is not a directory: {docs_path}", file=sys.stderr)
        return 2

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
    sys.exit(main())
