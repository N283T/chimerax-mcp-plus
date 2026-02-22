"""Tests for CLI commands."""

import subprocess
import sys


class TestIndexDocsCli:
    def test_help_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "chimerax_mcp", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "index-docs" in result.stdout

    def test_index_docs_with_nonexistent_path(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "chimerax_mcp",
                "index-docs",
                "--docs-path",
                "/nonexistent",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
