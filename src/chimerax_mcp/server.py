"""MCP server for ChimeraX."""

from __future__ import annotations

import atexit
import contextlib
import datetime
import html as html_lib
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
from fastmcp import FastMCP

from chimerax_mcp.chimerax import ChimeraXClient, detect_chimerax, start_chimerax

mcp = FastMCP("chimerax-mcp")

_client: ChimeraXClient | None = None
_process: subprocess.Popen[bytes] | None = None

# Screenshot constraints
VALID_IMAGE_FORMATS = {"png", "jpg", "jpeg"}
MAX_IMAGE_DIMENSION = 8192
MIN_IMAGE_DIMENSION = 1

# View management constants
VALID_AXES = {"x", "y", "z"}
VALID_LOG_LEVELS = {"error", "info", "warning"}
RICH_LOG_OK_SENTINEL = "__CHIMERAX_MCP_RICH_LOG_OK__"
RICH_LOG_ERROR_SENTINEL = "__CHIMERAX_MCP_RICH_LOG_ERROR__:"
_RESET_COMMANDS = [
    "hide pseudobonds",
    "hide atoms",
    "hide surface",
    "cartoon",
    "color byhetero",
    "lighting soft",
    "view",
]


def _cleanup() -> None:
    """Cleanup ChimeraX process on exit."""
    global _process
    if _process is not None:
        _process.terminate()
        try:
            _process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _process.kill()


atexit.register(_cleanup)


def get_client() -> ChimeraXClient:
    """Get or create the ChimeraX client."""
    global _client
    if _client is None:
        _client = ChimeraXClient()
    return _client


@mcp.tool()
def chimerax_detect() -> dict[str, Any]:
    """Detect ChimeraX installation on this system.

    Returns the path to ChimeraX if found, or an error message if not.
    """
    info = detect_chimerax()
    if info:
        return {"status": "ok", "found": True, "path": str(info.path)}
    return {"status": "ok", "found": False, "message": "ChimeraX not found"}


@mcp.tool()
def chimerax_start(
    port: int = 63269,
    nogui: bool = False,
    wait_seconds: int = 15,
    background: bool = False,
) -> dict[str, Any]:
    """Start ChimeraX with REST API enabled.

    Args:
        port: Port for REST API (default: 63269)
        nogui: Run without GUI (default: False)
        wait_seconds: Seconds to wait for startup (default: 15)
        background: If True, return immediately and let ChimeraX start in background.
            Use chimerax_status to check if ready. (default: False)

    Returns:
        Status of the startup attempt.
    """
    global _process

    client = get_client()

    # Check if already running via REST API
    if client.is_running():
        return {"status": "already_running", "message": "ChimeraX is already running"}

    # Check if we already have a process (might be starting up)
    if _process is not None and _process.poll() is None:
        if background:
            return {
                "status": "starting",
                "message": (
                    "ChimeraX is starting in background. Use chimerax_status to check readiness."
                ),
            }
        # Process exists and is still running - wait for it
        # Initial sleep to allow process to initialize
        time.sleep(3.0)
        remaining_checks = (wait_seconds - 3) * 2
        for _ in range(max(remaining_checks, 1)):
            time.sleep(0.5)
            if client.is_running():
                try:
                    version = client.get_version()
                except httpx.HTTPError:
                    version = "unknown"
                return {
                    "status": "started",
                    "port": port,
                    "version": version,
                    "note": "Connected to existing process",
                }
        return {
            "status": "timeout",
            "message": (
                f"Process exists but REST API not ready in {wait_seconds}s. "
                "ChimeraX may still be starting - try chimerax_status later."
            ),
        }

    try:
        _process = start_chimerax(port=port, nogui=nogui)
    except RuntimeError as e:
        return {"status": "error", "message": str(e)}

    if background:
        return {
            "status": "starting",
            "message": (
                "ChimeraX is starting in background. Use chimerax_status to check readiness."
            ),
        }

    # Initial sleep to allow ChimeraX to launch (especially important on macOS)
    time.sleep(3.0)

    remaining_checks = (wait_seconds - 3) * 2
    for _ in range(max(remaining_checks, 1)):
        time.sleep(0.5)
        if client.is_running():
            try:
                version = client.get_version()
            except httpx.HTTPError:
                version = "unknown"
            return {
                "status": "started",
                "port": port,
                "version": version,
            }

    return {
        "status": "timeout",
        "message": (
            f"ChimeraX did not respond within {wait_seconds}s. "
            "The process is still running - try chimerax_status in a few seconds."
        ),
    }


@mcp.tool()
def chimerax_stop() -> dict[str, Any]:
    """Stop the ChimeraX process started by this server.

    Returns:
        Status of the stop attempt.
    """
    global _process

    if _process is None:
        return {"status": "error", "message": "No ChimeraX process to stop"}

    proc = _process  # Capture for type narrowing
    proc.terminate()
    try:
        proc.wait(timeout=5)
        _process = None
        return {"status": "ok", "message": "ChimeraX stopped"}
    except subprocess.TimeoutExpired:
        proc.kill()
        _process = None
        return {"status": "ok", "message": "ChimeraX killed (did not respond to terminate)"}


@mcp.tool()
def chimerax_status() -> dict[str, Any]:
    """Check if ChimeraX REST server is running.

    Returns:
        Connection status and version if running.
    """
    client = get_client()
    if client.is_running():
        try:
            version = client.get_version()
        except httpx.HTTPError:
            version = "unknown"
        return {"status": "ok", "running": True, "version": version}
    return {"status": "ok", "running": False}


def _format_response(result: dict[str, Any]) -> dict[str, Any]:
    """Format a successful ChimeraX response for MCP tool output."""
    response: dict[str, Any] = {"status": "ok"}

    # Main output from log messages (both 'info' and 'note' levels)
    msgs = result.get("log_messages", {})
    output_lines: list[str] = []
    for level in ("info", "note"):
        output_lines.extend(msgs.get(level, []))
    if output_lines:
        response["output"] = "\n".join(output_lines)

    # Include warnings
    warnings = msgs.get("warning", [])
    if warnings:
        response["warnings"] = warnings

    # Include structured data if available
    json_vals = [v for v in result.get("json_values", []) if v is not None]
    if json_vals:
        response["json_values"] = json_vals

    return response


def _run_command(command: str) -> dict[str, Any]:
    """Internal function to execute a ChimeraX command."""
    client = get_client()
    if not client.is_running():
        return {"status": "error", "message": "ChimeraX is not running"}

    try:
        result = client.run_command(command)
    except httpx.ConnectError:
        return {"status": "error", "message": "Lost connection to ChimeraX"}
    except httpx.HTTPStatusError as e:
        return {"status": "error", "message": f"HTTP error: {e.response.status_code}"}
    except httpx.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}

    # Check for ChimeraX-level error
    if result.get("error") is not None:
        err = result["error"]
        return {
            "status": "error",
            "error_type": err.get("type", "Unknown"),
            "message": err.get("message", "Unknown error"),
        }

    return _format_response(result)


def _validate_log_level(level: str) -> str | None:
    """Normalize and validate a ChimeraX logger level."""
    normalized = level.strip().lower()
    if normalized not in VALID_LOG_LEVELS:
        return None
    return normalized


def _quote_chimerax_path(path: Path) -> str:
    """Quote a path for a ChimeraX command when quoting is needed."""
    path_str = str(path)
    if (
        not any(char.isspace() for char in path_str)
        and '"' not in path_str
        and "\\" not in path_str
    ):
        return path_str
    escaped = path_str.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _build_rich_log_html(html: str, title: str | None = None) -> str:
    """Wrap trusted caller-provided HTML with an optional escaped title."""
    if title is None or not title.strip():
        return html
    escaped_title = html_lib.escape(title.strip())
    return "\n".join(
        [
            '<div class="chimerax-mcp-rich-log" '
            'style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; '
            'line-height: 1.35; margin: 0.4em 0;">',
            f'<h2 style="margin: 0 0 0.35em 0; font-size: 1.25em;">{escaped_title}</h2>',
            html,
            "</div>",
        ]
    )


def _escape_html_value(value: Any) -> str:
    """Escape a value for insertion into generated rich report HTML."""
    if value is None:
        return ""
    return html_lib.escape(str(value))


def _build_rich_log_script(html: str, level: str) -> str:
    """Build a ChimeraX Python script that writes HTML to the Log."""
    direct_logger_hint = (
        f"    # logger_method = session.logger.{level}"
        if level in VALID_LOG_LEVELS
        else "    # logger_method selected by validated level"
    )
    lines = [
        f"html_content = {html!r}",
        f"level = {level!r}",
        "",
        "def write_log():",
        direct_logger_hint,
        "    logger_method = getattr(session.logger, level)",
        "    logger_method(html_content, is_html=True)",
        "",
        "try:",
        "    ui = getattr(session, 'ui', None)",
        "    if ui is not None and getattr(ui, 'is_gui', False) and hasattr(ui, 'thread_safe'):",
        "        session.ui.thread_safe(write_log)",
        "    else:",
        "        write_log()",
        f"    session.logger.info({RICH_LOG_OK_SENTINEL!r})",
        "except Exception as exc:",
        f"    session.logger.info({RICH_LOG_ERROR_SENTINEL!r} + ' ' + str(exc))",
    ]
    return "\n".join(lines)


def _iter_structured_log_messages(result: dict[str, Any]) -> list[str]:
    """Return structured ChimeraX log messages without parsing joined output."""
    messages: list[str] = []
    log_messages = result.get("log_messages", {})
    if not isinstance(log_messages, dict):
        return messages
    for entries in log_messages.values():
        if isinstance(entries, list):
            messages.extend(str(entry) for entry in entries)
        elif entries is not None:
            messages.append(str(entries))
    return messages


def _write_rich_log(html: str, level: str) -> dict[str, Any]:
    """Execute rich HTML logging inside ChimeraX."""
    client = get_client()
    if not client.is_running():
        return {"status": "error", "message": "ChimeraX is not running"}

    script = _build_rich_log_script(html=html, level=level)
    fd, script_path_str = tempfile.mkstemp(suffix=".py", prefix="chimerax_rich_log_")
    os.close(fd)
    script_path = Path(script_path_str)
    try:
        script_path.write_text(script)
        result = client.run_command(f"runscript {_quote_chimerax_path(script_path)}")

        if result.get("error") is not None:
            err = result["error"]
            if isinstance(err, dict):
                return {
                    "status": "error",
                    "error_type": err.get("type", "Unknown"),
                    "message": err.get("message", "Unknown error"),
                }
            return {"status": "error", "error_type": "Unknown", "message": str(err)}

        for message in _iter_structured_log_messages(result):
            if message.startswith(RICH_LOG_ERROR_SENTINEL):
                return {
                    "status": "error",
                    "message": message.removeprefix(RICH_LOG_ERROR_SENTINEL).strip(),
                }

        if RICH_LOG_OK_SENTINEL in _iter_structured_log_messages(result):
            return {"status": "ok", "level": level, "message": "Rich log written"}

        output = client._extract_output(result)
        return {"status": "error", "message": f"Unexpected output: {output}"}
    except httpx.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    finally:
        with contextlib.suppress(OSError):
            script_path.unlink()


def _render_rich_report_table(table: dict[str, Any]) -> str:
    """Render a structured table for generated rich report HTML."""
    title = _escape_html_value(table.get("title", ""))
    columns_value = table.get("columns") or []
    rows_value = table.get("rows") or []
    columns = columns_value if isinstance(columns_value, (list, tuple)) else []
    rows = rows_value if isinstance(rows_value, (list, tuple)) else []

    header_cells = "".join(
        f"<th>{_escape_html_value(column)}</th>" for column in columns
    )
    body_rows: list[str] = []
    for row in rows:
        cells = row if isinstance(row, (list, tuple)) else [row]
        body_cells = "".join(f"<td>{_escape_html_value(cell)}</td>" for cell in cells)
        body_rows.append(f"<tr>{body_cells}</tr>")

    html_parts = [
        '<div class="chimerax-mcp-rich-report-table" style="margin: 0.75em 0;">'
    ]
    if title:
        html_parts.append(f'<h4 style="margin: 0 0 0.35em 0;">{title}</h4>')
    html_parts.extend(
        [
            '<table style="border-collapse: collapse; width: 100%;">',
            "<thead>",
            f"<tr>{header_cells}</tr>",
            "</thead>",
            "<tbody>",
            *body_rows,
            "</tbody>",
            "</table>",
            "</div>",
        ]
    )
    return "\n".join(html_parts)


def _validate_rich_report_tables(tables: list[dict[str, Any]] | None) -> str | None:
    """Validate rich report table shapes accepted from MCP clients."""
    if tables is None:
        return None

    for index, table in enumerate(tables):
        if not isinstance(table, dict):
            return f"tables[{index}] must be a dict"

        columns = table.get("columns")
        if columns is not None and not isinstance(columns, (list, tuple)):
            return f"tables[{index}].columns must be a list"

        rows = table.get("rows")
        if rows is not None and not isinstance(rows, (list, tuple)):
            return f"tables[{index}].rows must be a list"

    return None


def _build_rich_report_html(
    title: str,
    summary: str | None = None,
    sections: list[dict[str, Any]] | None = None,
    tables: list[dict[str, Any]] | None = None,
    key_values: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> str:
    """Build escaped HTML for a generic structured rich report."""
    html_parts = [
        '<div class="chimerax-mcp-rich-report" '
        'style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; '
        'line-height: 1.35; margin: 0.4em 0;">',
        f'<h2 style="margin: 0 0 0.35em 0; font-size: 1.25em;">{_escape_html_value(title)}</h2>',
    ]

    if summary:
        html_parts.append(
            f'<p class="chimerax-mcp-rich-report-summary">{_escape_html_value(summary)}</p>'
        )

    if key_values:
        html_parts.append('<dl class="chimerax-mcp-rich-report-key-values">')
        for key, value in key_values.items():
            html_parts.append(f"<dt>{_escape_html_value(key)}</dt>")
            html_parts.append(f"<dd>{_escape_html_value(value)}</dd>")
        html_parts.append("</dl>")

    if warnings:
        html_parts.extend(
            [
                '<div class="chimerax-mcp-rich-report-warnings" '
                'style="border-left: 0.25em solid #d99000; padding-left: 0.75em;">',
                '<h3 style="margin: 0 0 0.35em 0;">Warnings</h3>',
                "<ul>",
            ]
        )
        for warning in warnings:
            html_parts.append(f"<li>{_escape_html_value(warning)}</li>")
        html_parts.extend(["</ul>", "</div>"])

    for section in sections or []:
        heading = _escape_html_value(section.get("heading", ""))
        body = _escape_html_value(section.get("body", ""))
        html_parts.append('<section class="chimerax-mcp-rich-report-section">')
        if heading:
            html_parts.append(f'<h3 style="margin: 0.75em 0 0.35em 0;">{heading}</h3>')
        if body:
            html_parts.append(f"<p>{body}</p>")
        html_parts.append("</section>")

    for table in tables or []:
        html_parts.append(_render_rich_report_table(table))

    html_parts.append("</div>")
    return "\n".join(html_parts)


@mcp.tool()
def chimerax_run(command: str) -> dict[str, Any]:
    """Execute a ChimeraX command.

    SECURITY NOTE: This tool can execute arbitrary ChimeraX commands, including
    Python code execution via 'runscript' and shell commands via 'shell'.
    Only use with trusted input.

    Args:
        command: The ChimeraX command to execute (e.g., "open 1a0s", "color red")

    Returns:
        Command output or error message.
    """
    return _run_command(command)


@mcp.tool()
def chimerax_rich_log(
    html: str,
    level: str = "info",
    title: str | None = None,
) -> dict[str, Any]:
    """Write trusted HTML to the ChimeraX Log.

    SECURITY NOTE: This tool passes caller-provided HTML through to ChimeraX
    with ``is_html=True``. Only use with trusted input.

    Args:
        html: HTML content to write to the ChimeraX Log.
        level: Log level - ``info``, ``warning``, or ``error`` (default: info).
        title: Optional escaped heading displayed above the HTML.

    Returns:
        Status of the rich log write operation.
    """
    if not html or not html.strip():
        return {"status": "error", "message": "html must not be empty"}

    normalized_level = _validate_log_level(level)
    if normalized_level is None:
        return {
            "status": "error",
            "message": f"level must be one of: {', '.join(sorted(VALID_LOG_LEVELS))}",
        }

    rich_html = _build_rich_log_html(html=html, title=title)
    return _write_rich_log(html=rich_html, level=normalized_level)


@mcp.tool()
def chimerax_rich_report(
    title: str,
    summary: str | None = None,
    sections: list[dict[str, Any]] | None = None,
    tables: list[dict[str, Any]] | None = None,
    key_values: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    level: str = "info",
) -> dict[str, Any]:
    """Write an escaped structured rich report to the ChimeraX Log.

    Args:
        title: Report title.
        summary: Optional summary paragraph.
        sections: Optional sections with ``heading`` and ``body`` values.
        tables: Optional tables with ``title``, ``columns``, and ``rows`` values.
        key_values: Optional key/value facts rendered as a definition list.
        warnings: Optional warning messages rendered as a callout list.
        level: Log level - ``info``, ``warning``, or ``error`` (default: info).

    Returns:
        Status of the rich report write operation.
    """
    if not title or not title.strip():
        return {"status": "error", "message": "title must not be empty"}

    normalized_level = _validate_log_level(level)
    if normalized_level is None:
        return {
            "status": "error",
            "message": f"level must be one of: {', '.join(sorted(VALID_LOG_LEVELS))}",
        }

    validation_error = _validate_rich_report_tables(tables)
    if validation_error is not None:
        return {"status": "error", "message": validation_error}

    report_html = _build_rich_report_html(
        title=title,
        summary=summary,
        sections=sections,
        tables=tables,
        key_values=key_values,
        warnings=warnings,
    )
    return _write_rich_log(html=report_html, level=normalized_level)


@mcp.tool()
def chimerax_models() -> dict[str, Any]:
    """Get list of currently open models in ChimeraX.

    Returns:
        List of open models with their information.
    """
    client = get_client()
    if not client.is_running():
        return {"status": "error", "message": "ChimeraX is not running"}

    try:
        models = client.get_models()
        return {"status": "ok", "models": models}
    except httpx.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}


@mcp.tool()
def chimerax_view(target: str | None = None) -> dict[str, Any]:
    """Adjust the view to fit models or a specific target in the window.

    Args:
        target: Optional atom specification to focus on (e.g., "#1", ":MK1").
            If not provided, fits all models in the view.

    Returns:
        Result of the view command.
    """
    command = f"view {target}" if target else "view"
    return _run_command(command)


@mcp.tool()
def chimerax_turn(axis: str = "y", angle: float = 90, frames: int = 1) -> dict[str, Any]:
    """Rotate the view around an axis.

    Args:
        axis: Axis to rotate around - "x", "y", or "z" (default: "y")
        angle: Rotation angle in degrees (default: 90)
        frames: Number of animation frames, must be >= 1 (default: 1, instant)

    Returns:
        Result of the turn command.
    """
    if axis.lower() not in VALID_AXES:
        return {
            "status": "error",
            "message": f"Invalid axis '{axis}'. Must be one of: {', '.join(sorted(VALID_AXES))}",
        }
    if frames < 1:
        return {"status": "error", "message": "frames must be >= 1"}
    command = f"turn {axis.lower()} {angle}"
    if frames > 1:
        command = f"{command} {frames}"
    return _run_command(command)


@mcp.tool()
def chimerax_reset() -> dict[str, Any]:
    """Reset the display to a clean default state.

    Hides pseudobonds, atoms, and surfaces, then shows cartoon representation
    with heteroatom coloring, soft lighting, and fits the view.

    Returns:
        Summary of reset commands executed.
    """
    client = get_client()
    if not client.is_running():
        return {"status": "error", "message": "ChimeraX is not running"}

    errors: list[str] = []
    for cmd in _RESET_COMMANDS:
        try:
            result = client.run_command(cmd)
            if result.get("error") is not None:
                err = result["error"]
                msg = err.get("message", "unknown error") if isinstance(err, dict) else str(err)
                errors.append(f"{cmd}: {msg}")
        except httpx.ConnectError as e:
            errors.append(f"{cmd}: {e}")
            return {
                "status": "error",
                "message": "Lost connection to ChimeraX during reset",
                "errors": errors,
            }
        except httpx.HTTPError as e:
            errors.append(f"{cmd}: {e}")

    if len(errors) == len(_RESET_COMMANDS):
        return {"status": "error", "message": "All reset commands failed", "errors": errors}
    if errors:
        return {"status": "partial", "message": "Some commands failed", "errors": errors}
    return {"status": "ok", "message": f"Reset complete ({len(_RESET_COMMANDS)} commands executed)"}


def _build_tool_screenshot_script(
    tool_name: str,
    output_path: str,
    width: int | None = None,
    height: int | None = None,
    padding: int = 0,
) -> str:
    """Build a Python script for ChimeraX to capture a tool window screenshot.

    Generates a script that, when executed inside ChimeraX via ``runscript``,
    finds a tool by name, optionally resizes its Qt widget, captures it via
    ``QWidget.grab()``, optionally adds white padding, and saves the result.

    The script communicates results back via session.logger.info() which
    appears in JSON response log_messages: ``OK: <path>`` on success,
    ``ERROR: <message>`` on failure.

    Args:
        tool_name: Name of the ChimeraX tool to capture.
        output_path: File path where the screenshot will be saved.
        width: Optional width to resize the widget before capture.
        height: Optional height to resize the widget before capture.
        padding: Pixels of white padding to add around the captured image.

    Returns:
        A string containing the Python script to execute inside ChimeraX.
    """
    lines = [
        "from Qt.QtGui import QPixmap, QPainter, QColor",
        "from Qt.QtWidgets import QApplication",
        "",
        f"tool_name = {tool_name!r}",
        f"output_path = {output_path!r}",
        f"resize_w = {width!r}",
        f"resize_h = {height!r}",
        f"padding = {padding!r}",
        "",
        "target = None",
        "for t in session.tools.list():",
        "    if t.tool_name == tool_name:",
        "        target = t",
        "        break",
        "",
        "if target is None:",
        "    session.logger.info('ERROR: Tool ' + repr(tool_name) + ' not found')",
        "else:",
        "    try:",
        "        ua = target.tool_window.ui_area",
        "        original_size = ua.size()",
        "",
        "        if resize_w is not None and resize_h is not None:",
        "            ua.resize(resize_w, resize_h)",
        "            QApplication.processEvents()",
        "        elif resize_w is not None:",
        "            ua.resize(resize_w, original_size.height())",
        "            QApplication.processEvents()",
        "        elif resize_h is not None:",
        "            ua.resize(original_size.width(), resize_h)",
        "            QApplication.processEvents()",
        "",
        "        pixmap = ua.grab()",
        "",
        "        if resize_w is not None or resize_h is not None:",
        "            ua.resize(original_size)",
        "            QApplication.processEvents()",
        "",
        "        if padding > 0:",
        "            padded = QPixmap(pixmap.width() + 2 * padding, pixmap.height() + 2 * padding)",
        "            padded.fill(QColor(255, 255, 255))",
        "            painter = QPainter(padded)",
        "            painter.drawPixmap(padding, padding, pixmap)",
        "            painter.end()",
        "            pixmap = padded",
        "",
        "        if not pixmap.save(output_path):",
        "            session.logger.info(f'ERROR: Failed to save screenshot to {output_path!r}')",
        "        else:",
        "            session.logger.info(f'OK: {output_path}')",
        "    except Exception as exc:",
        "        session.logger.info('ERROR: ' + str(exc))",
    ]
    return "\n".join(lines)


@mcp.tool()
def chimerax_tool_screenshot(
    tool_name: str,
    width: int | None = None,
    height: int | None = None,
    padding: int = 0,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Capture a screenshot of a ChimeraX tool window (e.g., Chain Contacts, Log).

    This captures separate tool panels, not the main 3D view.
    Use ``chimerax_screenshot`` for the main 3D view.

    Args:
        tool_name: Name of the tool window to capture (e.g., "Chain Contacts", "Log")
        width: Optional width to resize the widget before capture (1-8192)
        height: Optional height to resize the widget before capture (1-8192)
        padding: Pixels of white padding around the image (default: 0, must be >= 0)
        output_path: Where to save the image. If not provided, saves to
            ``~/.local/share/chimerax-mcp/screenshots/`` with a timestamp filename.

    Returns:
        Dict with ``status``, ``tool_name``, and ``file_path`` on success,
        or ``status`` and ``message`` on error.
    """
    # Validate inputs
    if not tool_name or not tool_name.strip():
        return {"status": "error", "message": "tool_name must not be empty"}
    if width is not None and (width < MIN_IMAGE_DIMENSION or width > MAX_IMAGE_DIMENSION):
        return {
            "status": "error",
            "message": f"width must be between {MIN_IMAGE_DIMENSION} and {MAX_IMAGE_DIMENSION}",
        }
    if height is not None and (height < MIN_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION):
        return {
            "status": "error",
            "message": f"height must be between {MIN_IMAGE_DIMENSION} and {MAX_IMAGE_DIMENSION}",
        }
    if padding < 0:
        return {"status": "error", "message": "padding must be >= 0"}
    if output_path is not None:
        stripped = output_path.strip()
        if not stripped:
            return {"status": "error", "message": "output_path must not be empty or whitespace"}

    client = get_client()
    if not client.is_running():
        return {"status": "error", "message": "ChimeraX is not running"}

    # Determine output path
    if output_path is not None:
        resolved = Path(output_path.strip())
    else:
        screenshots_dir = Path.home().joinpath(".local", "share", "chimerax-mcp", "screenshots")
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        resolved = screenshots_dir.joinpath(f"tool_{timestamp}.png")

    # Build and write temp script
    script = _build_tool_screenshot_script(
        tool_name=tool_name.strip(),
        output_path=str(resolved),
        width=width,
        height=height,
        padding=padding,
    )
    fd, script_path_str = tempfile.mkstemp(suffix=".py", prefix="chimerax_tool_grab_")
    os.close(fd)
    script_path = Path(script_path_str)
    try:
        script_path.write_text(script)

        result = client.run_command(f"runscript {script_path}")
        output = client._extract_output(result)

        if "ERROR:" in output:
            msg = output.split("ERROR:", 1)[1].strip()
            return {"status": "error", "message": msg}

        if "OK:" in output:
            return {
                "status": "ok",
                "tool_name": tool_name.strip(),
                "file_path": str(resolved),
            }

        return {"status": "error", "message": f"Unexpected output: {output}"}
    except httpx.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    finally:
        with contextlib.suppress(OSError):
            script_path.unlink()


@mcp.tool()
def chimerax_screenshot(
    width: int = 1024,
    height: int = 768,
    format: str = "png",  # noqa: A002
    output_path: str | None = None,
    auto_fit: bool = False,
) -> dict[str, Any]:
    """Capture a screenshot of the current ChimeraX view.

    Saves the image to a file and returns the file path.
    Use the Read tool on the returned path to view the image.

    Args:
        width: Image width in pixels (default: 1024, max: 8192)
        height: Image height in pixels (default: 768, max: 8192)
        format: Image format - png or jpg (default: png)
        output_path: Where to save the image. If not provided, saves to
            ``~/.local/share/chimerax-mcp/screenshots/`` with a timestamp filename.
        auto_fit: If True, run ``view`` to fit all models before capture (default: False).
            If the view command fails, the screenshot is still taken.

    Returns:
        File path to the saved screenshot image.
    """
    # Input validation
    if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
        return {"status": "error", "message": "Dimensions must be positive"}
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        return {
            "status": "error",
            "message": f"Dimensions must be <= {MAX_IMAGE_DIMENSION}",
        }
    if format.lower() not in VALID_IMAGE_FORMATS:
        return {
            "status": "error",
            "message": f"Format must be one of: {', '.join(VALID_IMAGE_FORMATS)}",
        }
    if output_path is not None:
        stripped = output_path.strip()
        if not stripped:
            return {"status": "error", "message": "output_path must not be empty or whitespace"}
        resolved_path: Path | None = Path(stripped)
    else:
        resolved_path = None

    client = get_client()
    if not client.is_running():
        return {"status": "error", "message": "ChimeraX is not running"}

    if auto_fit:
        with contextlib.suppress(httpx.HTTPError):
            client.run_command("view")

    try:
        file_path = client.screenshot(
            width=width, height=height, format=format.lower(), output_path=resolved_path
        )
        return {
            "status": "ok",
            "format": format.lower(),
            "width": width,
            "height": height,
            "file_path": str(file_path),
        }
    except httpx.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}
    except OSError as e:
        return {"status": "error", "message": f"File error: {e}"}


@mcp.tool()
def chimerax_open(path_or_id: str) -> dict[str, Any]:
    """Open a structure file or fetch from PDB.

    Args:
        path_or_id: Local file path, PDB ID (e.g., "1a0s"), or URL

    Returns:
        Result of the open command.
    """
    return _run_command(f"open {path_or_id}")


@mcp.tool()
def chimerax_close(model_spec: str = "all") -> dict[str, Any]:
    """Close models in ChimeraX.

    Args:
        model_spec: Model specification (default: "all")

    Returns:
        Result of the close command.
    """
    return _run_command(f"close {model_spec}")


@mcp.tool()
def chimerax_session_save(path: str) -> dict[str, Any]:
    """Save the current ChimeraX session.

    Args:
        path: Path to save the session file (.cxs)

    Returns:
        Result of the save command.
    """
    return _run_command(f"save {path}")


@mcp.tool()
def chimerax_session_open(path: str) -> dict[str, Any]:
    """Open a saved ChimeraX session.

    Args:
        path: Path to the session file (.cxs)

    Returns:
        Result of the open command.
    """
    return _run_command(f"open {path}")


def _get_screenshots_dir() -> Path:
    """Get the screenshots directory path."""
    return Path.home().joinpath(".local", "share", "chimerax-mcp", "screenshots")


@mcp.tool()
def chimerax_list_screenshots() -> dict[str, Any]:
    """List all screenshots saved by chimerax-mcp.

    Returns:
        List of screenshot files with their details (path, size, modification time).
    """
    screenshots_dir = _get_screenshots_dir()
    if not screenshots_dir.exists():
        return {"status": "ok", "screenshots": [], "message": "No screenshots directory found"}

    screenshots: list[dict[str, Any]] = []
    for f in screenshots_dir.iterdir():
        if f.is_file():
            stat = f.stat()
            screenshots.append(
                {
                    "path": str(f),
                    "name": f.name,
                    "size_bytes": stat.st_size,
                    "modified": datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.UTC)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
            )

    # Sort by modification time, newest first
    screenshots.sort(key=lambda x: x["modified"], reverse=True)

    return {
        "status": "ok",
        "count": len(screenshots),
        "directory": str(screenshots_dir),
        "screenshots": screenshots,
    }


@mcp.tool()
def chimerax_cleanup_screenshots(older_than_days: int = 7) -> dict[str, Any]:
    """Delete old screenshots to free up disk space.

    Args:
        older_than_days: Delete screenshots older than this many days (default: 7).
            Set to 0 to delete all screenshots.

    Returns:
        Number of deleted files and freed space.
    """
    screenshots_dir = _get_screenshots_dir()
    if not screenshots_dir.exists():
        return {"status": "ok", "deleted": 0, "message": "No screenshots directory found"}

    cutoff_time = time.time() - (older_than_days * 24 * 60 * 60)

    deleted_count = 0
    freed_bytes = 0
    errors: list[str] = []

    for f in screenshots_dir.iterdir():
        if f.is_file():
            stat = f.stat()
            if older_than_days == 0 or stat.st_mtime < cutoff_time:
                try:
                    freed_bytes += stat.st_size
                    f.unlink()
                    deleted_count += 1
                except OSError as e:
                    errors.append(f"{f.name}: {e}")

    result: dict[str, Any] = {
        "status": "ok" if not errors else "partial",
        "deleted": deleted_count,
        "freed_bytes": freed_bytes,
        "freed_human": _format_bytes(freed_bytes),
    }
    if errors:
        result["errors"] = errors

    return result


def _format_bytes(size: int) -> str:
    """Format bytes as human-readable string."""
    float_size = float(size)
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(float_size) < 1024:
            return f"{float_size:.1f} {unit}"
        float_size /= 1024
    return f"{float_size:.1f} TB"
