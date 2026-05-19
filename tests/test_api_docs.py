"""Tests for ChimeraX static API documentation helpers."""

import json

from chimerax_mcp.api_docs import (
    DocIndexSource,
    find_doc_sources,
    load_packaged_index,
    read_api_target,
    search_api_index,
)


def test_load_packaged_index_has_chimerax_metadata():
    index = load_packaged_index()

    assert index["version"] == "1.9"
    assert "atomic" in index["modules"]
    assert "color" in index["commands"]
    assert index["modules"]["atomic"]["path"].startswith("devel/modules/atomic/")


def test_find_doc_sources_prefers_env_docs_with_test_index(tmp_path, monkeypatch):
    docs_root = tmp_path.joinpath("docs")
    docs_root.mkdir()
    index_path = docs_root.joinpath("chimerax-test.index.json")
    index_path.write_text(json.dumps({"version": "test"}), encoding="utf-8")
    monkeypatch.setenv("CHIMERAX_DOCS_PATH", str(docs_root))

    sources = find_doc_sources()

    assert sources[0].kind == "env"
    assert sources[0].index_path == index_path
    assert sources[0].docs_root == docs_root


def test_search_api_index_finds_atomic_modules_from_packaged_source():
    result = search_api_index(
        "AtomicStructure residues",
        source=DocIndexSource.packaged(),
        kind="modules",
        limit=5,
    )

    assert result["status"] == "ok"
    assert result["source"]["kind"] == "packaged"
    assert result["version"] == "1.9"
    assert any(item["kind"] == "modules" and item["name"] == "atomic" for item in result["results"])


def test_search_api_index_rejects_invalid_kind():
    result = search_api_index("atomic", source=DocIndexSource.packaged(), kind="bad")

    assert result == {
        "status": "error",
        "message": "kind must be one of: all, commands, keywords, modules, tutorials",
    }


def test_read_api_target_returns_packaged_metadata_summary():
    result = read_api_target("atomic", source=DocIndexSource.packaged(), max_chars=500)

    assert result["status"] == "ok"
    assert result["source"]["kind"] == "packaged"
    assert result["target"] == "atomic"
    assert result["kind"] == "modules"
    assert "Atomic structures" in result["content"]
    assert result["truncated"] is False


def test_read_api_target_extracts_local_html(tmp_path):
    docs_root = tmp_path.joinpath("docs")
    html_path = docs_root.joinpath("devel", "modules", "atomic", "atomic.html")
    html_path.parent.mkdir(parents=True)
    html_path.write_text(
        "<html><head><title>atomic</title></head>"
        "<body><h1>Atomic API</h1><p>Residue and atom objects.</p></body></html>",
        encoding="utf-8",
    )
    index_path = docs_root.joinpath("chimerax-test.index.json")
    index_path.write_text(
        json.dumps(
            {
                "version": "test",
                "commands": {},
                "tutorials": {},
                "modules": {
                    "atomic": {
                        "path": "devel/modules/atomic/atomic.html",
                        "title": "atomic",
                        "description": "fallback",
                    },
                },
                "keywords": {},
            }
        ),
        encoding="utf-8",
    )
    source = DocIndexSource(kind="local", index_path=index_path, docs_root=docs_root)

    result = read_api_target("atomic", source=source)

    assert result["status"] == "ok"
    assert result["content"] == "atomic\nAtomic API\nResidue and atom objects."
