# Rich Log Design

## Overview

Add a flexible “rich log” feature to `chimerax-mcp-plus` so MCP clients can write attractive HTML output to the ChimeraX Log. The feature will be implemented in the MCP server and delivered to ChimeraX via the existing REST `runscript` pattern. ChimeraX will only display HTML; report construction remains in the MCP server.

## Goals

- Provide a low-level tool for writing caller-provided HTML directly to the ChimeraX Log.
- Provide a higher-level generic report tool that formats structured analysis output into readable HTML.
- Keep the first implementation small and compatible with the repository’s current FastMCP architecture.
- Make the report formatter generic now, while leaving room for later structure-analysis-specific templates.

## Non-goals

- Do not build or install a ChimeraX bundle in this change.
- Do not add structure-analysis-specific report templates yet.
- Do not sanitize arbitrary HTML passed to the low-level tool; this feature is intended for trusted MCP usage.
- Do not replace `chimerax_run`; rich logging is an additive convenience layer.

## User-facing tools

### `chimerax_rich_log`

Purpose: write arbitrary HTML to the ChimeraX Log.

Proposed parameters:

- `html: str` — HTML content to log. Required and must not be empty.
- `level: str = "info"` — one of `info`, `warning`, or `error`.
- `title: str | None = None` — optional heading wrapper shown above the HTML.

Behavior:

1. Validate `html` is non-empty and `level` is valid.
2. Confirm ChimeraX REST API is running.
3. Write a temporary Python script.
4. Execute it with `runscript <path>`.
5. The script calls `session.logger.info`, `session.logger.warning`, or `session.logger.error` with `is_html=True`.
6. Return a small status dict on success or an error dict on failure.

### `chimerax_rich_report`

Purpose: format structured generic report data into a styled HTML block and log it.

Proposed parameters:

- `title: str` — report title. Required and must not be empty.
- `summary: str | None = None` — short intro text.
- `sections: list[dict[str, Any]] | None = None` — each section supports `heading` and `body`.
- `tables: list[dict[str, Any]] | None = None` — each table supports `title`, `columns`, and `rows`.
- `key_values: dict[str, Any] | None = None` — summary facts rendered as label/value rows.
- `warnings: list[str] | None = None` — warning callouts rendered in the report.
- `level: str = "info"` — one of `info`, `warning`, or `error`.

Behavior:

1. Validate the required title and log level.
2. Build HTML from the structured fields.
3. Escape all data-derived text with `html.escape()` before inserting it into generated HTML.
4. Reuse the same rich log execution path as `chimerax_rich_log`.

## HTML rendering and security model

The low-level `chimerax_rich_log` tool is flexible by design: it passes caller-provided HTML through to ChimeraX with `is_html=True`. This matches the intended trusted-assistant workflow for this MCP server, which already exposes arbitrary ChimeraX command execution through `chimerax_run`.

The higher-level `chimerax_rich_report` tool is safer by default because it escapes all structured values before composing the HTML. Styling is server-generated, so user data cannot accidentally break the report layout unless the caller intentionally uses `chimerax_rich_log`.

Documentation will explicitly note that arbitrary HTML logging is trusted-input functionality.

## ChimeraX integration

Use the existing temporary-script + `runscript` integration style already used by `chimerax_tool_screenshot`.

The generated script should define a small `write_log()` function that calls the selected logger method with `is_html=True`. If a GUI session is active and `session.ui.thread_safe` is available, call the logger through `session.ui.thread_safe(write_log)` so the implementation follows ChimeraX GUI API guidance. Otherwise, call `write_log()` directly. This keeps the feature usable in both GUI and non-GUI contexts where the logger supports HTML or can gracefully degrade.

Relevant ChimeraX API references:

- `session.logger.info`, `warning`, and `error` accept `is_html=True` for HTML messages.
- `session.ui.thread_safe()` is the supported way to execute GUI-sensitive work in the UI thread.

## Internal design

Add focused helpers in `src/chimerax_mcp/server.py`:

- `VALID_LOG_LEVELS = {"info", "warning", "error"}`
- `_validate_log_level(level: str) -> str | None`
- `_build_rich_log_html(html: str, title: str | None = None) -> str`
- `_build_rich_report_html(...) -> str`
- `_build_rich_log_script(html: str, level: str) -> str`
- `_write_rich_log(html: str, level: str) -> dict[str, Any]`

`_write_rich_log` will own the repeated ChimeraX-running check, temp script lifecycle, `runscript` execution, output parsing, and HTTP error handling.

## Error handling

Return consistent MCP dicts:

- ChimeraX not running: `{"status": "error", "message": "ChimeraX is not running"}`
- Empty `html`: `{"status": "error", "message": "html must not be empty"}`
- Empty `title` for report: `{"status": "error", "message": "title must not be empty"}`
- Invalid `level`: `{"status": "error", "message": "level must be one of: error, info, warning"}`
- HTTP error: `{"status": "error", "message": "HTTP error: ..."}`
- Script-reported error: parse `ERROR:` marker from ChimeraX log output and return it.

## Testing plan

Add or extend tests in `tests/test_server.py`:

- Validate `chimerax_rich_log` rejects empty HTML.
- Validate `chimerax_rich_log` rejects invalid log levels.
- Validate not-running behavior returns the standard error.
- Mock a running client and verify `chimerax_rich_log` sends a `runscript` command.
- Verify `_build_rich_log_script` contains `is_html=True` and `session.ui.thread_safe` fallback logic.
- Verify `chimerax_rich_report` escapes data-derived HTML such as `<script>` in summary/table values.
- Verify `chimerax_rich_report` renders sections, key-values, warnings, and tables.

Run focused checks before implementation completion:

```bash
uv run pytest tests/test_server.py
uv run ruff check src tests
uv run ty check src tests
```

## Documentation updates

Update:

- `README.md` with a “Rich Log” tool section and examples.
- `CHANGELOG.md` under `[Unreleased]` with the new tools.

## Future extensions

- Add structure-analysis-specific report helpers once common output shapes are known.
- Add optional presets for compact, detailed, and publication-style reports.
- Add optional image thumbnails or links to screenshots in generated reports.
- Consider a stricter `sanitize=True` option only if untrusted HTML becomes a real use case.
