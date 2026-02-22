"""ChimeraX MCP Server - Control UCSF ChimeraX through Model Context Protocol."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from chimerax_mcp.server import mcp


def _run_server() -> None:
    """Run the MCP server."""
    mcp.run()


def _index_docs(args: argparse.Namespace) -> None:
    """Build the documentation search index."""
    from chimerax_mcp.docs.search import DocSearch

    docs_path = Path(args.docs_path) if args.docs_path else None
    data_dir = Path(args.data_dir) if args.data_dir else None

    if docs_path and not docs_path.exists():
        print(f"Error: docs path does not exist: {docs_path}", file=sys.stderr)
        sys.exit(1)

    search = DocSearch(docs_path=docs_path, data_dir=data_dir)
    print("Building documentation index...")
    stats = search.build_index()
    print(
        f"Done: {stats['files_processed']} files, "
        f"{stats['chunks_created']} chunks indexed."
    )


def main() -> None:
    """Entry point for the MCP server and CLI commands."""
    parser = argparse.ArgumentParser(
        prog="chimerax-mcp",
        description="MCP server for UCSF ChimeraX",
    )
    subparsers = parser.add_subparsers(dest="command")

    index_parser = subparsers.add_parser(
        "index-docs",
        help="Build the documentation search index",
    )
    index_parser.add_argument(
        "--docs-path",
        help="Path to ChimeraX HTML documentation directory",
    )
    index_parser.add_argument(
        "--data-dir",
        help="Path to store the ChromaDB database",
    )

    args = parser.parse_args()

    if args.command == "index-docs":
        _index_docs(args)
    else:
        _run_server()


__all__ = ["main", "mcp"]
