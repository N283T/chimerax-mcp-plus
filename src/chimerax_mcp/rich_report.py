"""HTML rendering helpers for ChimeraX rich report output."""

from __future__ import annotations

import html as html_lib
from typing import Any
from urllib.parse import quote

VALID_RICH_REPORT_THEMES = {"auto", "dark", "light"}
VALID_RICH_REPORT_BLOCK_TYPES = {
    "badges",
    "callout",
    "cards",
    "columns",
    "heading",
    "html",
    "legend",
    "paragraph",
    "progress",
    "table",
}


def _escape_html_value(value: Any) -> str:
    """Escape a value for insertion into generated rich report HTML."""
    if value is None:
        return ""
    return html_lib.escape(str(value))


def _rich_report_theme(theme: str, accent_color: str | None = None) -> dict[str, str]:
    """Return inline color tokens for rich report rendering."""
    normalized = theme.strip().lower()
    if normalized == "auto":
        light_accent = accent_color or "#0673c8"
        dark_accent = accent_color or "#58a6ff"
        return {
            "style_block": (
                "<style>"
                ".chimerax-mcp-rich-report.cxmcp-auto-theme{"
                f"--cxmcp-accent:{dark_accent};"
                "--cxmcp-bg:#0d1117;"
                "--cxmcp-text:#e6edf3;"
                "--cxmcp-muted:#8b949e;"
                "--cxmcp-panel:#161b22;"
                "--cxmcp-border:#30363d;"
                "--cxmcp-card:#161b22;"
                "--cxmcp-table-header:#1f6feb;"
                "--cxmcp-badge:#1f6feb;"
                "--cxmcp-badge-text:#ffffff;"
                "--cxmcp-callout-note-bg:#10233f;"
                "--cxmcp-callout-note-border:#58a6ff;"
                "--cxmcp-callout-success-bg:#0f2a1a;"
                "--cxmcp-callout-success-border:#238636;"
                "--cxmcp-callout-warning-bg:#2d2302;"
                "--cxmcp-callout-warning-border:#d29922;"
                "--cxmcp-callout-danger-bg:#3d1117;"
                "--cxmcp-callout-danger-border:#da3633;"
                "}"
                "@media (prefers-color-scheme: light){"
                ".chimerax-mcp-rich-report.cxmcp-auto-theme{"
                f"--cxmcp-accent:{light_accent};"
                "--cxmcp-bg:#ffffff;"
                "--cxmcp-text:#111827;"
                "--cxmcp-muted:#4b5563;"
                "--cxmcp-panel:#f8fafc;"
                "--cxmcp-border:#cbd5e1;"
                "--cxmcp-card:#f8fafc;"
                f"--cxmcp-table-header:{light_accent};"
                "--cxmcp-badge:#2563eb;"
                "--cxmcp-badge-text:#ffffff;"
                "--cxmcp-callout-note-bg:#eff6ff;"
                "--cxmcp-callout-note-border:#2563eb;"
                "--cxmcp-callout-success-bg:#ecfdf5;"
                "--cxmcp-callout-success-border:#16a34a;"
                "--cxmcp-callout-warning-bg:#fffbeb;"
                "--cxmcp-callout-warning-border:#d97706;"
                "--cxmcp-callout-danger-bg:#fef2f2;"
                "--cxmcp-callout-danger-border:#dc2626;"
                "}"
                "}"
                "</style>"
            ),
            "class_suffix": " cxmcp-auto-theme",
            "color_scheme": "color-scheme:light dark; ",
            "accent": "var(--cxmcp-accent)",
            "bg": "var(--cxmcp-bg)",
            "text": "var(--cxmcp-text)",
            "muted": "var(--cxmcp-muted)",
            "panel": "var(--cxmcp-panel)",
            "border": "var(--cxmcp-border)",
            "card": "var(--cxmcp-card)",
            "table_header": "var(--cxmcp-table-header)",
            "badge": "var(--cxmcp-badge)",
            "badge_text": "var(--cxmcp-badge-text)",
            "callout_note_bg": "var(--cxmcp-callout-note-bg)",
            "callout_note_border": "var(--cxmcp-callout-note-border)",
            "callout_success_bg": "var(--cxmcp-callout-success-bg)",
            "callout_success_border": "var(--cxmcp-callout-success-border)",
            "callout_warning_bg": "var(--cxmcp-callout-warning-bg)",
            "callout_warning_border": "var(--cxmcp-callout-warning-border)",
            "callout_danger_bg": "var(--cxmcp-callout-danger-bg)",
            "callout_danger_border": "var(--cxmcp-callout-danger-border)",
        }
    if normalized == "light":
        default_accent = accent_color or "#0673c8"
        return {
            "style_block": "",
            "class_suffix": "",
            "color_scheme": "",
            "accent": default_accent,
            "bg": "#ffffff",
            "text": "#111827",
            "muted": "#4b5563",
            "panel": "#f8fafc",
            "border": "#cbd5e1",
            "card": "#f8fafc",
            "table_header": default_accent,
            "badge": "#2563eb",
            "badge_text": "#ffffff",
            "callout_note_bg": "#eff6ff",
            "callout_note_border": "#2563eb",
            "callout_success_bg": "#ecfdf5",
            "callout_success_border": "#16a34a",
            "callout_warning_bg": "#fffbeb",
            "callout_warning_border": "#d97706",
            "callout_danger_bg": "#fef2f2",
            "callout_danger_border": "#dc2626",
        }

    default_accent = accent_color or "#58a6ff"
    return {
        "style_block": "",
        "class_suffix": "",
        "color_scheme": "",
        "accent": default_accent,
        "bg": "#0d1117",
        "text": "#e6edf3",
        "muted": "#8b949e",
        "panel": "#161b22",
        "border": "#30363d",
        "card": "#161b22",
        "table_header": "#1f6feb",
        "badge": "#1f6feb",
        "badge_text": "#ffffff",
        "callout_note_bg": "#10233f",
        "callout_note_border": "#58a6ff",
        "callout_success_bg": "#0f2a1a",
        "callout_success_border": "#238636",
        "callout_warning_bg": "#2d2302",
        "callout_warning_border": "#d29922",
        "callout_danger_bg": "#3d1117",
        "callout_danger_border": "#da3633",
    }


def _validate_rich_report_blocks(blocks: list[dict[str, Any]] | None) -> str | None:
    """Validate rich report blocks and return an error message, if invalid."""
    if blocks is None:
        return None
    if not isinstance(blocks, list):
        return "blocks must be a list"

    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            return f"blocks[{index}] must be an object"
        block_type = str(block.get("type", "")).strip().lower()
        if block_type not in VALID_RICH_REPORT_BLOCK_TYPES:
            return (
                f"blocks[{index}].type must be one of: "
                f"{', '.join(sorted(VALID_RICH_REPORT_BLOCK_TYPES))}"
            )
        if block_type == "table":
            columns = block.get("columns", [])
            rows = block.get("rows", [])
            if not isinstance(columns, (list, tuple)):
                return f"blocks[{index}].columns must be a list"
            if not isinstance(rows, (list, tuple)):
                return f"blocks[{index}].rows must be a list"
        if block_type in {"cards", "badges", "legend", "columns"}:
            items = block.get("items", [])
            if not isinstance(items, (list, tuple)):
                return f"blocks[{index}].items must be a list"
    return None


VALID_RICH_REPORT_LINK_ACTIONS = {"hide", "metadata", "select", "show", "view"}


def _rich_report_command_from_item(item: dict[str, Any]) -> str | None:
    """Return an explicit or spec-derived ChimeraX command link target."""
    command = item.get("command")
    if command is not None and str(command).strip():
        return str(command).strip()

    spec = item.get("spec")
    if spec is None or not str(spec).strip():
        return None

    normalized_action = str(item.get("action") or "select").strip().lower()
    if normalized_action not in VALID_RICH_REPORT_LINK_ACTIONS:
        normalized_action = "select"
    spec_text = str(spec).strip()
    if normalized_action == "metadata":
        return f"log metadata {spec_text}"
    return f"{normalized_action} {spec_text}"


def _rich_report_link_html(label: Any, command: str) -> str:
    """Render an escaped ChimeraX Log command link."""
    escaped_label = _escape_html_value(label)
    escaped_href = html_lib.escape(f"cxcmd:{quote(command, safe='')}", quote=True)
    return f'<a href="{escaped_href}">{escaped_label}</a>'


def _rich_report_value_html(value: Any, field: str = "text") -> str:
    """Render a plain, linked, or trusted-HTML rich report value."""
    if isinstance(value, dict):
        if value.get("html") is not None:
            return str(value["html"])
        label = value.get(field)
        if label is None and field != "text":
            label = value.get("text")
        if label is None and field != "value":
            label = value.get("value")
        if label is None:
            label = ""
        command = _rich_report_command_from_item(value)
        if command is not None:
            return _rich_report_link_html(label, command)
        return _escape_html_value(label)
    return _escape_html_value(value)


def _rich_report_text_or_html(block: dict[str, Any], field: str = "text") -> str:
    """Render a block text field, preserving trusted raw HTML when present."""
    return _rich_report_value_html(block, field=field)


def _rich_report_cell_html(cell: Any) -> tuple[str, str]:
    """Return rendered cell HTML and optional inline style."""
    if isinstance(cell, dict):
        style = str(cell.get("style", ""))
        return _rich_report_value_html(cell), style
    return _escape_html_value(cell), ""


def _tone_color(tone: str, tokens: dict[str, str]) -> tuple[str, str]:
    """Return background and border colors for a callout tone."""
    normalized = tone.strip().lower()
    if normalized not in {"note", "success", "warning", "danger"}:
        normalized = "note"
    return (
        tokens[f"callout_{normalized}_bg"],
        tokens[f"callout_{normalized}_border"],
    )


def _badge_color(item: dict[str, Any], tokens: dict[str, str]) -> str:
    """Return a badge color from explicit color or tone."""
    if item.get("color"):
        return str(item["color"])
    tone = str(item.get("tone", "")).strip().lower()
    if tone == "success":
        return tokens["callout_success_border"]
    if tone == "warning":
        return tokens["callout_warning_border"]
    if tone == "danger":
        return tokens["callout_danger_border"]
    return tokens["badge"]


def _render_rich_report_heading(block: dict[str, Any], tokens: dict[str, str]) -> str:
    """Render a rich report heading block."""
    level = block.get("level", 2)
    tag = "h3" if level == 3 else "h2"
    size = "18px" if tag == "h3" else "20px"
    return (
        f'<{tag} style="font-size:{size}; margin:16px 0 8px 0; '
        f'color:{tokens["text"]};">{_rich_report_value_html(block)}</{tag}>'
    )


def _render_rich_report_paragraph(block: dict[str, Any], tokens: dict[str, str]) -> str:
    """Render a paragraph block."""
    return (
        f'<p style="margin:0 0 12px 0; color:{tokens["text"]};">'
        f"{_rich_report_text_or_html(block)}</p>"
    )


def _render_rich_report_cards(block: dict[str, Any], tokens: dict[str, str]) -> str:
    """Render metric cards."""
    cards: list[str] = []
    for item in block.get("items", []):
        if not isinstance(item, dict):
            item = {"label": "", "value": item}
        value_color = str(item.get("color") or tokens["text"])
        note = item.get("note")
        note_html = ""
        if note is not None:
            note_html = (
                f'<div style="color:{tokens["muted"]}; font-size:12px; margin-top:3px;">'
                f"{_rich_report_value_html(note)}</div>"
            )
        cards.append(
            f'<div style="background:{tokens["card"]}; border:1px solid {tokens["border"]}; '
            'border-radius:10px; padding:10px;">'
            f'<div style="color:{tokens["muted"]}; font-size:12px; font-weight:700;">'
            f"{_rich_report_value_html(item.get('label', ''))}</div>"
            f'<div style="font-size:20px; font-weight:800; color:{value_color};">'
            f"{_rich_report_value_html(item.get('value', ''))}</div>"
            f"{note_html}</div>"
        )
    return (
        '<div style="display:grid; grid-template-columns:repeat(4,minmax(120px,1fr)); '
        f'gap:10px; margin:12px 0 18px 0;">{"".join(cards)}</div>'
    )


def _coerce_percentage(value: Any, maximum: Any) -> tuple[float, str]:
    """Return a clamped percentage and display text for progress blocks."""
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        numeric_value = 0.0
    try:
        numeric_maximum = float(maximum)
    except (TypeError, ValueError):
        numeric_maximum = 100.0
    if numeric_maximum <= 0:
        numeric_maximum = 100.0

    percentage = max(0.0, min(100.0, (numeric_value / numeric_maximum) * 100.0))
    display = f"{int(percentage)}%" if percentage.is_integer() else f"{percentage:.1f}%"
    return percentage, display


def _render_rich_report_progress(block: dict[str, Any], tokens: dict[str, str]) -> str:
    """Render a horizontal progress bar."""
    percentage, display = _coerce_percentage(block.get("value", 0), block.get("max", 100))
    label = _rich_report_value_html(block.get("label", "Progress"))
    color = str(block.get("color") or tokens["accent"])
    note = block.get("note")
    note_html = ""
    if note is not None:
        note_html = (
            f'<div style="color:{tokens["muted"]}; font-size:12px; margin-top:4px;">'
            f"{_rich_report_value_html(note)}</div>"
        )
    return (
        f'<div class="chimerax-mcp-rich-report-progress" style="margin:12px 0 16px 0;">'
        '<div style="display:flex; justify-content:space-between; gap:12px; '
        f'color:{tokens["text"]}; font-weight:800; margin-bottom:6px;">'
        f"<span>{label}</span><span>{display}</span></div>"
        f'<div style="height:14px; background:{tokens["panel"]}; border:1px solid '
        f'{tokens["border"]}; border-radius:999px; overflow:hidden;">'
        f'<div style="height:100%; width:{percentage:.1f}%; background:{color};"></div>'
        "</div>"
        f"{note_html}</div>"
    )


def _render_rich_report_columns(block: dict[str, Any], tokens: dict[str, str]) -> str:
    """Render nested report blocks in flexible columns."""
    items = block.get("items", [])
    min_width = _escape_html_value(block.get("min_width", "240px"))
    gap = _escape_html_value(block.get("gap", "12px"))
    column_html = []
    for item in items:
        if not isinstance(item, dict):
            item = {"type": "paragraph", "text": item}
        column_html.append(
            f'<div style="min-width:{min_width}; flex:1 1 {min_width};">'
            f"{_render_rich_report_block(item, tokens)}</div>"
        )
    return (
        f'<div class="chimerax-mcp-rich-report-columns" style="display:flex; '
        f'flex-wrap:wrap; gap:{gap}; margin:12px 0 16px 0;">{"".join(column_html)}</div>'
    )


def _render_rich_report_table(block: dict[str, Any], tokens: dict[str, str]) -> str:
    """Render a styled table block."""
    title = _rich_report_value_html(block.get("title", ""))
    columns = block.get("columns") or []
    rows = block.get("rows") or []
    header_color = str(block.get("header_color") or tokens["table_header"])
    column_styles = block.get("column_styles") or {}
    cell_styles = block.get("cell_styles") or []

    header_cells = "".join(
        f'<th style="background:{header_color}; color:white; text-align:left; padding:8px 10px; '
        f'border:1px solid {tokens["border"]};{column_styles.get(str(index), "")}">'
        f"{_escape_html_value(column)}</th>"
        for index, column in enumerate(columns)
    )

    body_rows: list[str] = []
    for row_index, row in enumerate(rows):
        cells = row if isinstance(row, (list, tuple)) else [row]
        body_cells: list[str] = []
        row_cell_styles = cell_styles[row_index] if row_index < len(cell_styles) else []
        for cell_index, cell in enumerate(cells):
            cell_html, cell_style = _rich_report_cell_html(cell)
            extra_style = ""
            if isinstance(row_cell_styles, (list, tuple)) and cell_index < len(row_cell_styles):
                extra_style = str(row_cell_styles[cell_index] or "")
            body_cells.append(
                f'<td style="padding:8px 10px; border:1px solid {tokens["border"]}; '
                f'{extra_style}{cell_style}">{cell_html}</td>'
            )
        body_rows.append(f"<tr>{''.join(body_cells)}</tr>")

    table_html = ['<div class="chimerax-mcp-rich-report-table" style="margin:14px 0 18px 0;">']
    if title:
        table_html.append(
            f'<h2 style="font-size:20px; margin:0 0 8px 0; color:{tokens["text"]};">{title}</h2>'
        )
    table_html.extend(
        [
            '<table style="border-collapse:collapse; width:100%; font-size:15px;">',
            f"<thead><tr>{header_cells}</tr></thead>",
            f"<tbody>{''.join(body_rows)}</tbody>",
            "</table>",
            "</div>",
        ]
    )
    return "".join(table_html)


def _render_rich_report_callout(block: dict[str, Any], tokens: dict[str, str]) -> str:
    """Render a callout block."""
    bg, border = _tone_color(str(block.get("tone", "note")), tokens)
    title = _rich_report_value_html(block.get("title", ""))
    title_html = f"<b>{title}</b> " if title else ""
    return (
        f'<div style="border-left:4px solid {border}; background:{bg}; padding:8px 10px; '
        f'color:{tokens["text"]}; border-radius:6px; margin:12px 0;">'
        f"{title_html}{_rich_report_text_or_html(block)}</div>"
    )


def _render_rich_report_badges(block: dict[str, Any], tokens: dict[str, str]) -> str:
    """Render inline badges."""
    badges: list[str] = []
    for item in block.get("items", []):
        item_dict = item if isinstance(item, dict) else {"label": item}
        color = _badge_color(item_dict, tokens)
        badges.append(
            f'<span style="display:inline-block; background:{color}; color:{tokens["badge_text"]}; '
            "border-radius:999px; padding:4px 10px; font-weight:700; font-size:12px; "
            f'margin:0 6px 6px 0;">{_rich_report_value_html(item_dict, field="label")}</span>'
        )
    return f'<div style="margin:8px 0 12px 0;">{"".join(badges)}</div>'


def _render_rich_report_legend(block: dict[str, Any], tokens: dict[str, str]) -> str:
    """Render a compact color legend."""
    items: list[str] = []
    for item in block.get("items", []):
        if not isinstance(item, dict):
            item = {"label": item, "color": tokens["accent"]}
        color = str(item.get("color") or tokens["accent"])
        description = item.get("description")
        description_html = ""
        if description is not None:
            description_html = (
                f' <span style="color:{tokens["muted"]};">'
                f'{_rich_report_value_html(description)}</span>'
            )
        items.append(
            '<div style="display:flex; align-items:center; gap:8px; margin:4px 12px 4px 0;">'
            f'<span style="display:inline-block; width:14px; height:14px; border-radius:3px; '
            f'background:{color}; border:1px solid {tokens["border"]};"></span>'
            f"<span><b>{_rich_report_value_html(item, field='label')}</b>{description_html}</span>"
            "</div>"
        )
    return (
        f'<div style="display:flex; flex-wrap:wrap; color:{tokens["text"]}; '
        f'margin:10px 0 14px 0;">{"".join(items)}</div>'
    )


def _render_rich_report_block(block: dict[str, Any], tokens: dict[str, str]) -> str:
    """Render one rich report block."""
    block_type = str(block.get("type", "")).strip().lower()
    if block_type == "heading":
        return _render_rich_report_heading(block, tokens)
    if block_type == "paragraph":
        return _render_rich_report_paragraph(block, tokens)
    if block_type == "cards":
        return _render_rich_report_cards(block, tokens)
    if block_type == "progress":
        return _render_rich_report_progress(block, tokens)
    if block_type == "columns":
        return _render_rich_report_columns(block, tokens)
    if block_type == "table":
        return _render_rich_report_table(block, tokens)
    if block_type == "callout":
        return _render_rich_report_callout(block, tokens)
    if block_type == "badges":
        return _render_rich_report_badges(block, tokens)
    if block_type == "legend":
        return _render_rich_report_legend(block, tokens)
    if block_type == "html":
        return str(block.get("html", ""))
    return ""


def _build_rich_report_html(
    title: str,
    subtitle: str | None = None,
    theme: str = "auto",
    accent_color: str | None = None,
    blocks: list[dict[str, Any]] | None = None,
) -> str:
    """Build themed rich report HTML for the ChimeraX Log."""
    tokens = _rich_report_theme(theme, accent_color)
    html_parts = [
        tokens["style_block"],
        f'<div class="chimerax-mcp-rich-report{tokens["class_suffix"]}" '
        f'style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif; '
        f"{tokens['color_scheme']}color:{tokens['text']}; background:{tokens['bg']}; "
        f"border:1px solid {tokens['border']}; border-radius:12px; padding:16px 18px; "
        'max-width:1040px; line-height:1.38; box-shadow:0 2px 10px rgba(0,0,0,.20);">',
        '<div style="display:flex; align-items:flex-start; justify-content:space-between; '
        f"gap:16px; border-bottom:3px solid {tokens['accent']}; padding-bottom:10px; "
        'margin-bottom:14px;">',
        "<div>",
        f'<div style="font-size:12px; letter-spacing:.08em; text-transform:uppercase; '
        f'color:{tokens["muted"]}; font-weight:700;">ChimeraX analysis note</div>',
        f'<h1 style="font-size:28px; color:{tokens["accent"]}; margin:2px 0 2px 0;">'
        f"{_escape_html_value(title.strip())}</h1>",
    ]
    if subtitle:
        html_parts.append(
            f'<div style="font-size:14px; color:{tokens["text"]};">'
            f"{_escape_html_value(subtitle)}</div>"
        )
    html_parts.extend(["</div>", "</div>"])
    for block in blocks or []:
        html_parts.append(_render_rich_report_block(block, tokens))
    html_parts.append("</div>")
    return "".join(html_parts)
