"""Tests for HTML document indexer."""

from pathlib import Path

from chimerax_mcp.docs.indexer import (
    DocChunk,
    _extract_command_name,
    _split_large_text,
    categorize_file,
    chunk_html,
    parse_html,
)

SAMPLE_COMMAND_HTML = """\
<html>
<head><title>Command: color, rainbow</title></head>
<body>
<h3><a href="../index.html#commands">Command</a>: color, rainbow</h3>
<p>The <b>color</b> command changes the color of atoms, bonds, and surfaces.</p>

<h4><a name="simple">Simple Coloring</a></h4>
<p>Usage: <b>color</b> <i>spec</i> <i>color-spec</i></p>
<p>Colors the specified items with the given color.</p>

<h4><a name="sequential">Sequential Coloring (Rainbow)</a></h4>
<p>Usage: <b>rainbow</b> <i>spec</i></p>
<p>Colors residues sequentially using a rainbow palette.</p>
</body>
</html>
"""

SAMPLE_TOOL_HTML = """\
<html>
<head><title>Tool: Model Panel</title></head>
<body>
<h3>Tool: Model Panel</h3>
<p>The Model Panel lists the currently open models.</p>
<p>It shows model number, name, and display status.</p>
</body>
</html>
"""


class TestCategorizeFile:
    def test_command_file(self):
        p = Path("user/commands/color.html")
        assert categorize_file(p) == "commands"

    def test_tool_file(self):
        p = Path("user/tools/modelpanel.html")
        assert categorize_file(p) == "tools"

    def test_tutorial_file(self):
        p = Path("user/tutorials/intro.html")
        assert categorize_file(p) == "tutorials"

    def test_devel_file(self):
        p = Path("devel/bundles.html")
        assert categorize_file(p) == "devel"

    def test_user_top_level(self):
        p = Path("user/attributes.html")
        assert categorize_file(p) == "concepts"

    def test_unknown_file(self):
        p = Path("other/random.html")
        assert categorize_file(p) == "other"


class TestParseHtml:
    def test_extracts_title(self):
        title, _ = parse_html(SAMPLE_COMMAND_HTML)
        assert title == "Command: color, rainbow"

    def test_extracts_text_content(self):
        _, text = parse_html(SAMPLE_COMMAND_HTML)
        assert "color" in text
        assert "rainbow" in text
        assert "<b>" not in text


class TestChunkHtml:
    def test_returns_chunks(self):
        chunks = chunk_html(SAMPLE_COMMAND_HTML, source_file="user/commands/color.html")
        assert len(chunks) > 0
        assert all(isinstance(c, DocChunk) for c in chunks)

    def test_chunk_has_metadata(self):
        chunks = chunk_html(SAMPLE_COMMAND_HTML, source_file="user/commands/color.html")
        for chunk in chunks:
            assert chunk.source_file == "user/commands/color.html"
            assert chunk.category == "commands"
            assert chunk.title == "Command: color, rainbow"
            assert chunk.command_name == "color"

    def test_command_name_extracted(self):
        chunks = chunk_html(SAMPLE_COMMAND_HTML, source_file="user/commands/color.html")
        assert all(c.command_name == "color" for c in chunks)

    def test_non_command_has_empty_command_name(self):
        chunks = chunk_html(SAMPLE_TOOL_HTML, source_file="user/tools/modelpanel.html")
        assert all(c.command_name == "" for c in chunks)

    def test_chunks_have_section_names(self):
        chunks = chunk_html(SAMPLE_COMMAND_HTML, source_file="user/commands/color.html")
        sections = [c.section for c in chunks]
        assert any("Simple Coloring" in s for s in sections)

    def test_chunk_content_is_text(self):
        chunks = chunk_html(SAMPLE_COMMAND_HTML, source_file="user/commands/color.html")
        for chunk in chunks:
            assert "<" not in chunk.content or "&lt;" in chunk.content
            assert len(chunk.content) > 0

    def test_fallback_for_no_headings(self):
        html = """\
<html><head><title>Simple Page</title></head>
<body>
<p>This page has no heading tags at all but has enough content to be indexed.
It contains a paragraph with sufficient text to pass the minimum chunk size threshold.</p>
</body></html>
"""
        chunks = chunk_html(html, source_file="user/simple.html")
        assert len(chunks) >= 1
        assert chunks[0].section == "Simple Page"


class TestSplitLargeText:
    def test_small_text_unchanged(self):
        text = "short paragraph"
        result = _split_large_text(text, max_size=100)
        assert result == [text]

    def test_splits_at_paragraph_boundary(self):
        para_a = "A" * 60
        para_b = "B" * 60
        para_c = "C" * 60
        text = f"{para_a}\n{para_b}\n{para_c}"
        result = _split_large_text(text, max_size=130)
        assert len(result) == 2
        assert para_a in result[0]
        assert para_b in result[0]
        assert para_c in result[1]

    def test_no_paragraph_duplication(self):
        text = "para_A\npara_B\npara_C\npara_D\npara_E\npara_F"
        result = _split_large_text(text, max_size=20)
        for chunk in result:
            lines = chunk.split("\n")
            # No line should appear more than once in a chunk
            assert len(lines) == len(set(lines)), f"Duplicate found in chunk: {chunk!r}"

    def test_all_paragraphs_present(self):
        paragraphs = ["para_A", "para_B", "para_C", "para_D"]
        text = "\n".join(paragraphs)
        result = _split_large_text(text, max_size=20)
        all_content = "\n".join(result)
        for p in paragraphs:
            assert p in all_content

    def test_single_huge_paragraph(self):
        text = "A" * 200
        result = _split_large_text(text, max_size=100)
        # Cannot split at paragraph boundary, returns as single chunk
        assert len(result) == 1
        assert result[0] == text


class TestExtractCommandName:
    def test_standard_command_title(self):
        assert _extract_command_name("Command: color, rainbow", "commands") == "color"

    def test_non_command_category(self):
        assert _extract_command_name("Command: color", "tools") == ""

    def test_no_match_in_title(self):
        assert _extract_command_name("Some Other Title", "commands") == ""

    def test_single_command(self):
        assert _extract_command_name("Command: open", "commands") == "open"
