"""Tests for docs MCP tools."""

from unittest.mock import MagicMock, patch

from chimerax_mcp.server import docs_lookup, docs_search


class TestDocsSearchTool:
    @patch("chimerax_mcp.server.get_doc_search")
    def test_search_returns_results(self, mock_get):
        mock_search = MagicMock()
        mock_search.is_indexed.return_value = True
        mock_search.search.return_value = [
            {
                "id": "doc1",
                "document": "The color command",
                "metadata": {
                    "title": "color",
                    "section": "Simple Coloring",
                    "category": "commands",
                    "source_file": "user/commands/color.html",
                    "command_name": "color",
                },
            }
        ]
        mock_get.return_value = mock_search

        result = docs_search.fn(query="how to color atoms")
        assert result["status"] == "ok"
        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "color"

    @patch("chimerax_mcp.server.get_doc_search")
    def test_search_with_category(self, mock_get):
        mock_search = MagicMock()
        mock_search.is_indexed.return_value = True
        mock_search.search.return_value = []
        mock_get.return_value = mock_search

        result = docs_search.fn(query="color", category="tutorials")
        mock_search.search.assert_called_once_with(
            query="color", category="tutorials", max_results=5
        )

    @patch("chimerax_mcp.server.get_doc_search")
    def test_search_not_indexed(self, mock_get):
        mock_search = MagicMock()
        mock_search.is_indexed.return_value = False
        mock_search.ensure_index.return_value = None
        mock_search.search.return_value = []
        mock_get.return_value = mock_search

        result = docs_search.fn(query="test")
        mock_search.ensure_index.assert_called_once()


class TestDocsLookupTool:
    @patch("chimerax_mcp.server.get_doc_search")
    def test_lookup_returns_chunks(self, mock_get):
        mock_search = MagicMock()
        mock_search.is_indexed.return_value = True
        mock_search.lookup.return_value = [
            {
                "id": "c1",
                "document": "color simple usage",
                "metadata": {
                    "title": "color",
                    "section": "Simple",
                    "category": "commands",
                    "source_file": "user/commands/color.html",
                    "command_name": "color",
                },
            }
        ]
        mock_get.return_value = mock_search

        result = docs_lookup.fn(command_name="color")
        assert result["status"] == "ok"
        assert len(result["results"]) == 1

    @patch("chimerax_mcp.server.get_doc_search")
    def test_lookup_not_found(self, mock_get):
        mock_search = MagicMock()
        mock_search.is_indexed.return_value = True
        mock_search.lookup.return_value = []
        mock_get.return_value = mock_search

        result = docs_lookup.fn(command_name="nonexistent")
        assert result["status"] == "ok"
        assert result["results"] == []
