# ChimeraX Script Recipes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bundled ChimeraX script recipes and MCP tools to search/read them, including recipes that emit `chimerax_rich_report` payloads.

**Architecture:** Store recipes in a packaged JSON resource, load/search/read them through a focused `script_recipes.py` helper, and expose only read-only MCP tools from `server.py`. README and CHANGELOG describe usage and safety boundaries.

**Tech Stack:** Python 3.12, FastMCP, `importlib.resources`, JSON resources, pytest, ruff, ty.

---

## Tasks

1. Create `src/chimerax_mcp/resources/script_recipes.json` with 10 bundled recipes covering command usage, model iteration, selection summary, JSON marker output, rich report payload output, measurement, neighborhood search, coloring, and error handling.
2. Create `src/chimerax_mcp/script_recipes.py` with `load_script_recipes`, `search_script_recipes`, and `read_script_recipe`.
3. Add tests in `tests/test_script_recipes.py` for loading, category/output filtering, search ranking, read truncation, no-script mode, missing recipe, and rich report metadata.
4. Add `chimerax_script_recipe_search` and `chimerax_script_recipe_read` tools to `src/chimerax_mcp/server.py` with server tests.
5. Update README and CHANGELOG.
6. Verify with `uv run pytest tests/test_script_recipes.py tests/test_server.py`, `uv run pytest`, `uv run ruff check .`, `uv run ty check .`, and wheel resource inclusion.
