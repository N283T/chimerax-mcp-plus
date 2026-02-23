#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# ///
"""Build index for ChimeraX HTML documentation.

Generates a JSON index containing:
- Commands: name, synopsis, file path
- Tutorials: title, description, path
- Modules: API module info
- Keywords: searchable terms mapped to files
"""

from __future__ import annotations

import html.parser
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


class HTMLTextExtractor(html.parser.HTMLParser):
    """Extract text and structure from HTML."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.headings: list[tuple[str, str]] = []  # (level, text)
        self.text_parts: list[str] = []
        self._current_tag = ""
        self._in_title = False
        self._in_heading = False
        self._heading_level = ""

    def handle_starttag(self, tag, attrs):
        self._current_tag = tag
        if tag == "title":
            self._in_title = True
        elif tag in ("h1", "h2", "h3", "h4"):
            self._in_heading = True
            self._heading_level = tag

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in ("h1", "h2", "h3", "h4"):
            self._in_heading = False
        self._current_tag = ""

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title = text
        elif self._in_heading:
            self.headings.append((self._heading_level, text))
        self.text_parts.append(text)


def extract_html_info(filepath: Path) -> dict | None:
    """Extract title, headings, and text from HTML file."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return None

    parser = HTMLTextExtractor()
    try:
        parser.feed(content)
    except Exception:
        return None

    if not parser.title:
        return None

    # Get first paragraph as description
    text = " ".join(parser.text_parts)
    # Limit description length
    description = text[:300] + "..." if len(text) > 300 else text

    return {
        "title": parser.title,
        "headings": parser.headings[:10],
        "description": description,
    }


def parse_command_title(title: str) -> list[str]:
    """Extract command names from title like 'Command: color, rainbow'."""
    match = re.match(r"Command:\s*(.+)", title, re.IGNORECASE)
    if match:
        # Split by comma and clean
        names = [n.strip() for n in match.group(1).split(",")]
        return [n for n in names if n and not n.startswith("(")]
    return []


def build_commands_index(commands_dir: Path) -> dict[str, dict]:
    """Index command documentation files."""
    commands: dict[str, dict] = {}

    for html_file in sorted(commands_dir.glob("*.html")):
        info = extract_html_info(html_file)
        if not info:
            continue

        # Parse command names from title
        cmd_names = parse_command_title(info["title"])
        if not cmd_names:
            # Use filename as fallback
            cmd_names = [html_file.stem]

        rel_path = f"user/commands/{html_file.name}"

        for cmd_name in cmd_names:
            commands[cmd_name] = {
                "path": rel_path,
                "title": info["title"],
                "description": info["description"][:200],
            }

    return commands


def build_tutorials_index(devel_dir: Path) -> dict[str, dict]:
    """Index tutorial documentation."""
    tutorials: dict[str, dict] = {}

    tutorials_dir = devel_dir / "tutorials"
    if not tutorials_dir.exists():
        return tutorials

    for html_file in sorted(tutorials_dir.glob("*.html")):
        info = extract_html_info(html_file)
        if not info:
            continue

        rel_path = f"devel/tutorials/{html_file.name}"
        tutorials[html_file.stem] = {
            "path": rel_path,
            "title": info["title"],
            "description": info["description"][:200],
        }

    return tutorials


def build_modules_index(devel_dir: Path) -> dict[str, dict]:
    """Index API module documentation."""
    modules: dict[str, dict] = {}

    modules_dir = devel_dir / "modules"
    if not modules_dir.exists():
        return modules

    for item in sorted(modules_dir.iterdir()):
        if not item.is_dir():
            continue

        # Try index.html first, then module_name.html
        index_file = item / "index.html"
        if not index_file.exists():
            index_file = item / f"{item.name}.html"
        if not index_file.exists():
            # Use first HTML file found
            html_files = list(item.glob("*.html"))
            if html_files:
                index_file = html_files[0]
            else:
                continue

        info = extract_html_info(index_file)
        if not info:
            continue

        rel_path = f"devel/modules/{item.name}/{index_file.name}"
        modules[item.name] = {
            "path": rel_path,
            "title": info["title"],
            "description": info["description"][:200],
        }

    return modules


def build_keywords_index(
    commands: dict, tutorials: dict, modules: dict
) -> dict[str, list[str]]:
    """Build keyword to path mapping."""
    keywords: dict[str, list[str]] = {}

    def add_keywords(text: str, path: str):
        # Extract words
        words = re.findall(r"\b[a-z]{4,}\b", text.lower())
        stop_words = {
            "this",
            "that",
            "with",
            "from",
            "have",
            "been",
            "will",
            "which",
            "their",
            "they",
            "there",
            "these",
            "those",
            "when",
            "where",
            "command",
            "commands",
            "chimerax",
            "html",
        }
        for word in set(words):
            if word not in stop_words:
                keywords.setdefault(word, []).append(path)

    # Index commands
    for name, info in commands.items():
        add_keywords(name, info["path"])
        add_keywords(info.get("description", ""), info["path"])

    # Index tutorials
    for name, info in tutorials.items():
        add_keywords(name, info["path"])
        add_keywords(info.get("title", ""), info["path"])

    # Index modules
    for name, info in modules.items():
        add_keywords(name, info["path"])
        add_keywords(info.get("title", ""), info["path"])

    # Deduplicate and limit
    for key in keywords:
        keywords[key] = list(set(keywords[key]))[:10]

    return keywords


def build_index(docs_path: Path, version: str) -> dict:
    """Build complete index for ChimeraX documentation."""
    commands_dir = docs_path / "user" / "commands"
    devel_dir = docs_path / "devel"

    commands = build_commands_index(commands_dir) if commands_dir.exists() else {}
    tutorials = build_tutorials_index(devel_dir) if devel_dir.exists() else {}
    modules = build_modules_index(devel_dir) if devel_dir.exists() else {}
    keywords = build_keywords_index(commands, tutorials, modules)

    return {
        "version": version,
        "created": datetime.now(timezone.utc).isoformat(),
        "commands": commands,
        "tutorials": tutorials,
        "modules": modules,
        "keywords": {k: v for k, v in sorted(keywords.items()) if len(v) > 0},
    }


def main():
    """CLI entry point."""
    if len(sys.argv) < 3:
        print("Usage: build_doc_index.py <docs_path> <version> [output_path]")
        print("  docs_path: Path to ChimeraX docs directory")
        print("  version: ChimeraX version string (e.g., 1.9)")
        print(
            "  output_path: Output JSON file (default: docs_path/../chimerax-<version>.index.json)"
        )
        sys.exit(1)

    docs_path = Path(sys.argv[1]).resolve()
    version = sys.argv[2]
    output_path = Path(sys.argv[3]) if len(sys.argv) > 3 else None

    if not docs_path.exists():
        print(f"Error: Path does not exist: {docs_path}")
        sys.exit(1)

    if output_path is None:
        output_path = docs_path.parent / f"chimerax-{version}.index.json"

    print(f"Building index for ChimeraX v{version}...")
    index = build_index(docs_path, version)

    output_path.write_text(json.dumps(index, indent=2, ensure_ascii=False))
    print(f"Index written to: {output_path}")
    print(f"  Commands: {len(index['commands'])}")
    print(f"  Tutorials: {len(index['tutorials'])}")
    print(f"  Modules: {len(index['modules'])}")
    print(f"  Keywords: {len(index['keywords'])}")


if __name__ == "__main__":
    main()
