# ChimeraX API Reference Tools Design

Date: 2026-05-19
Branch: `feat/chimerax-api-reference-tools`

## Goal

Add MCP tools that help an LLM discover and verify ChimeraX Python APIs before using `runscript`-based automation. The tools must work for users who only install `chimerax-mcp-plus`; they must not depend on the repository's optional Claude/Codex skills being installed.

## Background

The server currently controls ChimeraX through the REST `/run` endpoint and exposes command-oriented tools such as `chimerax_run`, `chimerax_open`, `chimerax_view`, and screenshot tools. Existing rich-log tools already create a temporary Python file and execute it with the ChimeraX `runscript` command, proving that Python API execution through ChimeraX is viable.

The repository also contains an optional `explore-chimerax` skill with a generated documentation index, but that skill is not part of the installed Python package. New API-reference MCP tools need an installed-package fallback so normal `uv tool install` users get useful behavior without extra skill setup.

## User-Facing Tools

### `chimerax_api_search`

Search static ChimeraX command, tutorial, and Python API module metadata.

Inputs:

- `query: str`: Search terms.
- `kind: str = "all"`: One of `all`, `commands`, `tutorials`, `modules`, or `keywords`.
- `limit: int = 10`: Maximum results.

Output:

- `status`
- `source`: Which index was used.
- `version`: Index version when known.
- `results`: Ranked metadata records with name, kind, path, title, and description.

### `chimerax_api_read`

Read a static documentation entry by path, symbol-ish name, or result name.

Inputs:

- `target: str`: A path such as `devel/modules/atomic/atomic.html`, a module name such as `atomic`, or a command name such as `color`.
- `max_chars: int = 6000`: Output truncation limit.

Output:

- `status`
- `source`
- `version`
- `target`
- `content`: Plain-text documentation excerpt when available, or metadata summary if only the packaged lightweight index is available.

### `chimerax_python_inspect`

Inspect the live Python API inside the running ChimeraX process via `runscript`.

Inputs:

- `symbol: str`: Dotted import path such as `chimerax.atomic.AtomicStructure`.
- `include_dir: bool = true`: Include a bounded `dir()` preview.
- `max_doc_chars: int = 4000`: Truncate docstrings.

Output:

- `status`
- `symbol`
- `module`
- `type`
- `signature` when available
- `doc` when available
- `attributes` when requested

This tool does not accept arbitrary Python code. It resolves a dotted symbol through `importlib.import_module()` and `getattr()` only.

### `chimerax_python_dir`

List attributes of a live Python object inside ChimeraX.

Inputs:

- `symbol: str`: Dotted import path.
- `filter: str | None = None`: Optional substring filter.
- `limit: int = 100`: Maximum attributes.

Output:

- `status`
- `symbol`
- `attributes`
- `truncated`

## Static Documentation Sources

The static lookup layer uses this priority order:

1. `CHIMERAX_DOCS_PATH`, if set. This points at a ChimeraX `share/docs` directory.
2. Detected local ChimeraX application docs, derived from the detected ChimeraX executable path when possible.
3. Repository-local skill docs/index when running from a checkout.
4. A lightweight JSON index packaged under `src/chimerax_mcp/resources/`.

The packaged index is required and is the non-skill fallback. It should be generated from a local ChimeraX installation at release time. Full HTML docs should not be vendored initially; package size and licensing stay simpler if the MCP ships a lightweight metadata index and optionally reads full local docs when present.

## Index Generation

Move or wrap the existing `skills/explore-chimerax/build_doc_index.py` logic into a repository script that can generate package resources.

Example release-time command:

```bash
uv run scripts/build_chimerax_doc_index.py \
  /Applications/ChimeraX-1.10.app/Contents/share/docs \
  1.10 \
  src/chimerax_mcp/resources/chimerax-1.10.index.json
```

The script should also support auto-detecting docs from the installed ChimeraX path when the docs path is omitted.

## Architecture

Add a small documentation module, for example `src/chimerax_mcp/api_docs.py`, responsible for:

- discovering candidate documentation/index locations;
- loading the best available index;
- searching metadata records;
- resolving names to paths;
- converting local HTML docs to bounded plain text excerpts;
- falling back to packaged metadata summaries when full docs are unavailable.

Add a small live-introspection helper, for example `src/chimerax_mcp/python_api.py`, responsible for:

- validating dotted symbol syntax;
- generating bounded, safe introspection scripts;
- executing those scripts through the existing `ChimeraXClient.run_command()` + `runscript` pattern;
- parsing JSON output from ChimeraX log messages.

`src/chimerax_mcp/server.py` should remain the MCP tool wiring layer and delegate most logic to these helpers.

## Safety and Boundaries

- Do not expose a general arbitrary Python eval tool in the first implementation.
- Accept only dotted symbols matching a conservative pattern like `[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+`.
- Reject dunder segments such as `__class__` and `__subclasses__` unless there is a clear future need.
- Bound docstring, attribute, and text output sizes.
- Always clean up temporary scripts.
- Return explicit errors when ChimeraX is not running for live introspection.

## Testing

Unit tests should cover:

- packaged index loading without skills installed;
- search ranking and kind filtering;
- target resolution by command name, module name, and path;
- HTML-to-text truncation behavior using temporary docs fixtures;
- dotted-symbol validation, including rejection of unsafe input;
- live introspection script generation with mocked ChimeraX client;
- MCP tool error handling when ChimeraX is not running.

Manual smoke testing should cover:

1. Start ChimeraX.
2. Run `chimerax_api_search("AtomicStructure residues")`.
3. Run `chimerax_api_read("atomic")`.
4. Run `chimerax_python_inspect("chimerax.atomic.AtomicStructure")`.
5. Use the inspected API from a separate `runscript` workflow.

## Out of Scope

- General-purpose Python code execution.
- Installing a ChimeraX bundle into the user's ChimeraX environment.
- Vendoring the complete ChimeraX HTML documentation tree.
- Replacing command-oriented tools; commands remain useful for high-level operations.
