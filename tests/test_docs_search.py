"""Tests for document search orchestration."""

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
        search.ensure_index()  # should not raise
        assert search.is_indexed() is True

    def test_build_index_nonexistent_docs_path(self, tmp_path: Path):
        data_dir = tmp_path.joinpath("chroma")
        search = DocSearch(docs_path=tmp_path.joinpath("no-such-dir"), data_dir=data_dir)
        with pytest.raises(FileNotFoundError):
            search.build_index()

    def test_ensure_index_wraps_error(self, tmp_path: Path):
        data_dir = tmp_path.joinpath("chroma")
        search = DocSearch(docs_path=tmp_path.joinpath("no-such-dir"), data_dir=data_dir)
        with pytest.raises(RuntimeError, match="Failed to build"):
            search.ensure_index()
