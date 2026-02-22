"""HTML document parser and chunker for ChimeraX documentation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

MIN_CHUNK_SIZE = 50
MAX_CHUNK_SIZE = 1500
OVERLAP_SIZE = 100

DEFAULT_DOCS_PATH = Path.home().joinpath(".claude", "skills", "explore-chimerax", "assets", "docs")

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
    match = re.match(r"Command:\s*(\w+)", title)
    return match.group(1) if match else ""


def parse_html(html_content: str) -> tuple[str, str]:
    """Parse HTML and return (title, full_text)."""
    soup = BeautifulSoup(html_content, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    body = soup.find("body")
    text = (
        body.get_text(separator="\n", strip=True)
        if body
        else soup.get_text(separator="\n", strip=True)
    )
    return title, text


def _split_by_headings(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """Split HTML body into sections by heading tags."""
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
        para_len = len(para) + 1
        if current_len + para_len > max_size and current:
            chunks.append("\n".join(current))
            current = [para]
            current_len = para_len
        else:
            current.append(para)
            current_len += para_len

    if current:
        chunks.append("\n".join(current))

    return chunks


def chunk_html(html_content: str, source_file: str) -> list[DocChunk]:
    """Parse HTML and split into searchable chunks with metadata."""
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
    """Find all HTML files under the docs directory."""
    return sorted(docs_path.rglob("*.html"))
