# Rich Report Composer Design

## Overview

Replace the current conservative `chimerax_rich_report` formatter with a flexible rich document composer for ChimeraX Log. The goal is to produce output closer to an analysis dashboard: large headings, cards, colored tables, badges, callouts, legends, and raw HTML escape hatches. This is intended for local/trusted MCP use, so expressiveness is more important than strict sanitization.

`chimerax_rich_log` remains the low-level raw HTML writer. `chimerax_rich_report` becomes the higher-level composer that builds attractive HTML from blocks.

## Goals

- Make rich reports visually comparable to hand-authored ChimeraX Log HTML.
- Support light, dark, and auto-ish themes with explicit inline colors for ChimeraX Log reliability.
- Keep the API flexible enough that domain-specific reports are not forced into a rigid template.
- Allow trusted raw HTML blocks inside the composer.
- Preserve the reliable rich-log execution path: temporary script, quoted `runscript` path, per-call markers, and structured result parsing.

## Non-goals

- Do not attempt full CSS framework support.
- Do not sanitize raw HTML blocks; this is local/trusted functionality like `chimerax_run`.
- Do not add a UniProt-specific or PDB-specific report tool in this change.
- Do not require backward compatibility with the current plain `summary/key_values/sections/tables` layout.

## User-facing API

`chimerax_rich_report` should accept a document-style payload:

- `title: str` — required title.
- `subtitle: str | None = None` — optional subtitle below the title.
- `theme: str = "auto"` — `auto`, `light`, or `dark`.
- `accent_color: str | None = None` — optional title underline / primary accent.
- `blocks: list[dict[str, Any]] | None = None` — ordered rich content blocks.
- `level: str = "info"` — `info`, `warning`, or `error`.

The existing `summary`, `sections`, `tables`, `key_values`, and `warnings` parameters can be removed or replaced. If retaining some temporarily is simpler for FastMCP compatibility, they should be converted internally to blocks and documented as transitional only.

## Block model

Each block is a dict with a `type` key. Unknown block types return a structured error instead of being silently ignored.

### `heading`

Renders a section heading.

Fields:

- `text: str`
- `level: int = 2` — supported values 2 or 3.

### `paragraph`

Renders normal escaped text or trusted HTML.

Fields:

- `text: str | None`
- `html: str | None`

If `html` is provided, it is inserted raw. Otherwise `text` is escaped.

### `cards`

Renders a responsive grid of metric cards.

Fields:

- `items: list[dict[str, Any]]`

Each item supports:

- `label: str`
- `value: Any`
- `note: str | None`
- `color: str | None`

### `table`

Renders a styled table.

Fields:

- `title: str | None`
- `columns: list[Any]`
- `rows: list[list[Any] | Any]`
- `header_color: str | None`
- `column_styles: dict[str, str] | None`
- `cell_styles: list[list[str | None]] | None`

Cell values are escaped by default. If a cell is a dict, support:

- `text: Any` — escaped text.
- `html: str` — raw trusted HTML.
- `style: str` — inline style for the cell.

### `callout`

Renders a highlighted callout.

Fields:

- `tone: str = "note"` — `note`, `success`, `warning`, or `danger`.
- `title: str | None`
- `text: str | None`
- `html: str | None`

### `badges`

Renders inline badges.

Fields:

- `items: list[dict[str, Any] | str]`

Dict items support:

- `label: str`
- `tone: str | None`
- `color: str | None`

### `legend`

Renders a compact color legend.

Fields:

- `items: list[dict[str, Any]]`

Each item supports:

- `label: str`
- `color: str`
- `description: str | None`

### `html`

Raw trusted HTML escape hatch.

Fields:

- `html: str`

## Theme behavior

Use inline styles so output is stable in ChimeraX Log.

Themes:

- `dark` — dark panel background, light text, dark borders, bright accents.
- `light` — white/light panel background, dark text, gray borders, saturated accents.
- `auto` — use a dark-leaning neutral palette by default because the user’s Log may be in dark mode; allow explicit `theme="light"` for screenshots or light sessions.

Theme controls:

- report container background / text / border
- title color / accent line
- card background / border
- table border / row background
- callout palettes
- default badge colors

## Validation and error handling

Return MCP-style dict errors:

- Empty title: `{"status": "error", "message": "title must not be empty"}`
- Invalid level: same format as `chimerax_rich_log`.
- Invalid theme: `theme must be one of: auto, dark, light`.
- Invalid blocks: include the block index and field, e.g. `blocks[2].type must be one of: ...`.
- Invalid table columns/rows/cards/items should return structured errors, not raise exceptions.

## HTML safety model

This is a local trusted MCP. The composer escapes plain text fields, but raw HTML fields are intentionally inserted as-is. This is documented behavior and mirrors the power already exposed by `chimerax_run` and `chimerax_rich_log`.

## Documentation and testing

Tests should cover:

- Rich dark themed output includes expected container styles and title.
- Light theme output uses light palette.
- Raw HTML block is preserved.
- Text fields are escaped.
- Cards, badges, callouts, legends, and styled tables render.
- Unknown block type and malformed block data return structured errors.
- `chimerax_rich_report` passes generated HTML to `_write_rich_log`.

Docs should update README examples to show the new block composer style rather than the old plain generic report.

## Migration

Because backward compatibility is not required, the old plain report fields can be removed from `chimerax_rich_report`. Existing tests and README examples should be updated to the new block API.
