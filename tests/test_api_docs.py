"""Tests for ChimeraX static API documentation helpers."""

from chimerax_mcp.api_docs import load_packaged_index


def test_load_packaged_index_has_chimerax_metadata():
    index = load_packaged_index()

    assert index["version"] == "1.9"
    assert "atomic" in index["modules"]
    assert "color" in index["commands"]
    assert index["modules"]["atomic"]["path"].startswith("devel/modules/atomic/")
