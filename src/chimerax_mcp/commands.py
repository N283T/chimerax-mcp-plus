"""Helpers for building ChimeraX command strings safely."""

from __future__ import annotations

from pathlib import Path


def quote_chimerax_path(path: str | Path) -> str:
    """Quote a local path for ChimeraX commands when quoting is needed."""
    path_str = str(path)
    if (
        path_str
        and not any(char.isspace() for char in path_str)
        and '"' not in path_str
        and "\\" not in path_str
    ):
        return path_str
    escaped = path_str.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
