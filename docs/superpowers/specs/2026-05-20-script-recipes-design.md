# ChimeraX Script Recipes Design

Date: 2026-05-20
Branch: `feat/script-recipes`

## Goal

Add a small, skill-independent script recipe library to help LLMs write ChimeraX `runscript` Python snippets using the API reference tools added in `v0.3.0`. The library should include patterns for plain logging, JSON marker output, and `chimerax_rich_report` payload generation.

## Scope

This change adds search/read tools for bundled recipes only. It does not execute recipes and does not add a general Python execution tool. Official RBVI ChimeraX Recipes are referenced as links where helpful, but their code is not vendored.

## Tools

- `chimerax_script_recipe_search(query, category="all", output_kind="all", limit=10)`: search bundled recipes by title, description, category, API symbols, notes, and keywords.
- `chimerax_script_recipe_read(recipe_id, include_script=True, max_chars=10000)`: return one recipe with metadata and an optional bounded script body.

## Data Model

Recipes are stored in `src/chimerax_mcp/resources/script_recipes.json`:

- `id`
- `title`
- `category`
- `output_kind`
- `description`
- `uses_api`
- `related_api_queries`
- `suggested_next_tools`
- `official_references`
- `notes`
- `script`

Output kinds include `script`, `log_text`, `json_payload`, `rich_report_payload`, `html_log`, and `command_sequence`.

## Initial Recipes

The initial bundled set focuses on reusable MCP/LLM patterns:

1. Run ChimeraX commands from Python.
2. Iterate open atomic models.
3. Summarize current selection.
4. Emit MCP JSON marker output.
5. Build a structure summary JSON payload.
6. Build a structure summary rich report payload.
7. Measure CA distance between residues.
8. Find residues near selected atoms.
9. Color by chain using commands from Python.
10. Error handling template.

## Rich Report Integration

Recipes that produce rich report payloads use `output_kind="rich_report_payload"` and list `chimerax_rich_report` in `suggested_next_tools`. Scripts emit `CHIMERAX_MCP_RESULT_JSON=<json>` to the ChimeraX Log. A future `chimerax_python_run` tool can parse that marker automatically, but this change only documents and exposes the pattern.

## Safety

Recipes are examples, not automatically executed. Tool documentation should remind callers that running any Python script inside ChimeraX is equivalent to trusted arbitrary code execution. Search/read tools only return bundled static content.
