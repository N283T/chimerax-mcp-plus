"""Tests for ChimeraX static API documentation helpers."""

import json
from pathlib import Path

import chimerax_mcp.api_docs as api_docs
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


def test_find_doc_sources_detects_docs_from_chimerax_path_before_packaged(
    tmp_path, monkeypatch
):
    app_root = tmp_path.joinpath("ChimeraX.app")
    executable = app_root.joinpath("Contents", "MacOS", "ChimeraX")
    docs_root = app_root.joinpath("Contents", "share", "docs")
    executable.parent.mkdir(parents=True)
    docs_root.mkdir(parents=True)
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    index_path = docs_root.joinpath("chimerax-test.index.json")
    index_path.write_text(json.dumps({"version": "test"}), encoding="utf-8")
    monkeypatch.delenv("CHIMERAX_DOCS_PATH", raising=False)
    monkeypatch.setenv("CHIMERAX_PATH", str(executable))
    monkeypatch.setattr(api_docs, "_candidate_chimerax_docs_roots", lambda: [])
    monkeypatch.setattr(api_docs, "_repo_root", lambda: None)

    sources = find_doc_sources()

    assert sources[0].kind == "chimerax"
    assert sources[0].index_path == index_path
    assert sources[0].docs_root == docs_root
    assert sources[1].kind == "packaged"


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


def test_read_api_target_rejects_absolute_local_html_path(tmp_path):
    docs_root = tmp_path.joinpath("docs")
    docs_root.mkdir()
    escaped_path = tmp_path.joinpath("escaped.html")
    escaped_path.write_text(
        "<html><body><h1>Escaped secret contents</h1></body></html>",
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
                        "path": str(escaped_path),
                        "title": "atomic title",
                        "description": "safe metadata fallback",
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
    assert "safe metadata fallback" in result["content"]
    assert "Escaped secret contents" not in result["content"]


def test_read_api_target_rejects_parent_relative_local_html_path(tmp_path):
    docs_root = tmp_path.joinpath("docs")
    docs_root.mkdir()
    escaped_path = tmp_path.joinpath("escaped.html")
    escaped_path.write_text(
        "<html><body><h1>Escaped parent contents</h1></body></html>",
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
                        "path": "../escaped.html",
                        "title": "atomic title",
                        "description": "safe parent metadata fallback",
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
    assert "safe parent metadata fallback" in result["content"]
    assert "Escaped parent contents" not in result["content"]


def test_find_doc_sources_includes_env_docs_root_without_local_index(tmp_path, monkeypatch):
    docs_root = tmp_path.joinpath("docs")
    html_path = docs_root.joinpath("devel", "modules", "atomic", "atomic.html")
    html_path.parent.mkdir(parents=True)
    html_path.write_text(
        "<html><body><h1>Local Atomic HTML</h1><p>Packaged metadata path.</p></body></html>",
        encoding="utf-8",
    )
    monkeypatch.setenv("CHIMERAX_DOCS_PATH", str(docs_root))

    source = find_doc_sources()[0]
    result = read_api_target("atomic", source=source)

    assert source.kind == "env"
    assert source.index_path is None
    assert source.docs_root == docs_root
    assert result["status"] == "ok"
    assert result["content"] == "Local Atomic HTML\nPackaged metadata path."


def test_find_doc_sources_uses_repo_skill_docs_root_for_html(tmp_path, monkeypatch):
    assets_root = tmp_path.joinpath("skills", "explore-chimerax", "assets")
    docs_root = assets_root.joinpath("docs")
    html_path = docs_root.joinpath("devel", "modules", "atomic", "atomic.html")
    html_path.parent.mkdir(parents=True)
    html_path.write_text(
        "<html><body><h1>Repo Skill Atomic HTML</h1></body></html>",
        encoding="utf-8",
    )
    index_path = assets_root.joinpath("chimerax-test.index.json")
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
    monkeypatch.delenv("CHIMERAX_DOCS_PATH", raising=False)
    monkeypatch.setattr(api_docs, "detect_chimerax", lambda: None)
    monkeypatch.setattr(api_docs, "_candidate_chimerax_docs_roots", lambda: [])
    monkeypatch.setattr(api_docs, "_repo_root", lambda: tmp_path)

    source = find_doc_sources()[0]
    result = read_api_target("atomic", source=source)

    assert source.kind == "repo-skill"
    assert source.index_path == index_path
    assert source.docs_root == docs_root
    assert result["status"] == "ok"
    assert result["content"] == "Repo Skill Atomic HTML"


def test_read_api_target_returns_color_command_metadata_summary():
    result = read_api_target("color", source=DocIndexSource.packaged(), max_chars=500)

    assert result["status"] == "ok"
    assert result["target"] == "color"
    assert result["kind"] == "commands"
    assert "Command: color, rainbow" in result["content"]


def test_read_api_target_resolves_packaged_target_by_path():
    result = read_api_target(
        "devel/modules/atomic/atomic.html",
        source=DocIndexSource.packaged(),
        max_chars=500,
    )

    assert result["status"] == "ok"
    assert result["target"] == "atomic"
    assert result["kind"] == "modules"
    assert "Atomic structures" in result["content"]


def test_read_api_target_truncates_content_to_max_chars():
    result = read_api_target("atomic", source=DocIndexSource.packaged(), max_chars=12)

    assert result["status"] == "ok"
    assert result["content"] == "atomic\natomi"
    assert len(result["content"]) == 12
    assert result["truncated"] is True


def test_build_doc_index_script_exists():
    script = Path("scripts/build_chimerax_doc_index.py")

    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "def build_index" in text
    assert "def find_default_docs_path" in text
