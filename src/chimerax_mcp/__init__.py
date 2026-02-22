"""ChimeraX MCP Server - Control UCSF ChimeraX through Model Context Protocol."""

from __future__ import annotations

from chimerax_mcp.server import mcp


def main() -> None:
    """Entry point for the MCP server."""
    mcp.run()


__all__ = ["main", "mcp"]
