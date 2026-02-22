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
        for r in results:
            assert r["metadata"]["category"] == "tutorials"
