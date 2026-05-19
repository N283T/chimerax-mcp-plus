"""Static ChimeraX documentation index lookup helpers."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

PACKAGED_INDEX_NAME = "chimerax-1.9.index.json"


def load_packaged_index() -> dict[str, Any]:
    """Load the bundled fallback ChimeraX documentation index."""
    index_path = resources.files("chimerax_mcp.resources").joinpath(PACKAGED_INDEX_NAME)
    return json.loads(index_path.read_text(encoding="utf-8"))
