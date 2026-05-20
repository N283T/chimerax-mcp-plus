# Rich Report Command Links Design

Date: 2026-05-20
Branch: `feat/rich-report-links`

## Goal

Make model, chain, residue, and action values in `chimerax_rich_report` clickable in the ChimeraX Log without requiring callers to hand-write raw HTML.

## Design

Extend rich report value rendering with structured link objects. Existing plain text and trusted raw HTML behavior remains unchanged.

Supported object fields:

- `text`: link label or visible value.
- `command`: explicit ChimeraX command to execute through `cxcmd:`.
- `spec`: ChimeraX atom/model specification used to build a command.
- `action`: one of `select`, `view`, `show`, `hide`, or `metadata`; defaults to `select` when `spec` is present.
- `style`: existing inline style support for table cells.
- `html`: existing trusted raw HTML escape hatch. If `html` is present, it wins over structured link rendering.

Command mapping:

- `select` -> `select <spec>`
- `view` -> `view <spec>`
- `show` -> `show <spec>`
- `hide` -> `hide <spec>`
- `metadata` -> `log metadata <spec>`

Structured links should be HTML-escaped and URL-escaped for the `href` attribute. They should work in table cells, card values/notes, badges, legend items, progress labels/notes, headings, paragraph text fields, and callout text/title where object values are already supported or easy to support. The first implementation will explicitly cover table cells, cards, badges, legends, progress labels/notes, heading text, paragraph text, and callout title/text.

## Safety

This is still a ChimeraX command link. Only render commands from trusted local report payloads. Do not auto-link arbitrary strings in this change; callers must opt in by providing `command` or `spec`.
