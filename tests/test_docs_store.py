"""Tests for ChromaDB document store."""

from pathlib import Path

from chimerax_mcp.docs.store import DocStore


class TestDocStore:
    def test_create_store(self, tmp_path: Path):
        store = DocStore(data_dir=tmp_path)
        assert store is not None

    def test_add_and_query(self, tmp_path: Path):
        store = DocStore(data_dir=tmp_path)
        store.add_documents(
            ids=["doc1"],
            documents=["The color command changes the color of atoms and surfaces"],
            metadatas=[{"category": "commands", "command_name": "color", "title": "color"}],
        )
        results = store.search("how to change atom colors", max_results=1)
        assert len(results) == 1
        assert results[0]["id"] == "doc1"
        assert "color" in results[0]["document"]

    def test_search_with_category_filter(self, tmp_path: Path):
        store = DocStore(data_dir=tmp_path)
        store.add_documents(
            ids=["cmd1", "tut1"],
            documents=[
                "The color command changes colors",
                "Tutorial: coloring your first protein",
            ],
            metadatas=[
                {"category": "commands", "command_name": "color", "title": "color"},
                {"category": "tutorials", "command_name": "", "title": "tutorial"},
            ],
        )
        results = store.search("color", category="commands", max_results=5)
        assert all(r["metadata"]["category"] == "commands" for r in results)

    def test_lookup_by_command_name(self, tmp_path: Path):
        store = DocStore(data_dir=tmp_path)
        store.add_documents(
            ids=["c1", "c2", "c3"],
            documents=["color simple usage", "color rainbow usage", "open command usage"],
            metadatas=[
                {"category": "commands", "command_name": "color", "title": "color"},
                {"category": "commands", "command_name": "color", "title": "color"},
                {"category": "commands", "command_name": "open", "title": "open"},
            ],
        )
        results = store.lookup_command("color")
        assert len(results) == 2
        assert all(r["metadata"]["command_name"] == "color" for r in results)

    def test_search_empty_store(self, tmp_path: Path):
        store = DocStore(data_dir=tmp_path)
        results = store.search("anything")
        assert results == []

    def test_is_indexed(self, tmp_path: Path):
        store = DocStore(data_dir=tmp_path)
        assert store.is_indexed() is False
        store.add_documents(
            ids=["doc1"],
            documents=["test"],
            metadatas=[{"category": "commands", "command_name": "test", "title": "test"}],
        )
        assert store.is_indexed() is True

    def test_clear(self, tmp_path: Path):
        store = DocStore(data_dir=tmp_path)
        store.add_documents(
            ids=["doc1"],
            documents=["test"],
            metadatas=[{"category": "commands", "command_name": "test", "title": "test"}],
        )
        assert store.is_indexed() is True
        store.clear()
        assert store.is_indexed() is False
