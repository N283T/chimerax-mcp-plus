"""MCP server for ChimeraX."""

from __future__ import annotations

import atexit
import contextlib
import datetime
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
    wait_seconds: int = 10,
) -> dict[str, Any]:
    """Start ChimeraX with REST API enabled.

    Args:
        port: Port for REST API (default: 63269)
        nogui: Run without GUI (default: False)
        wait_seconds: Seconds to wait for startup (default: 10)

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
        # Process exists and is still running - wait for it
        for _ in range(wait_seconds * 2):
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
            "message": f"Process exists but REST API not ready in {wait_seconds}s",
        }

    try:
        _process = start_chimerax(port=port, nogui=nogui)
    except RuntimeError as e:
        return {"status": "error", "message": str(e)}

    for _ in range(wait_seconds * 2):
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

    return {"status": "timeout", "message": f"ChimeraX did not respond within {wait_seconds}s"}


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

    # Main output from info-level log messages
    info = result.get("log_messages", {}).get("info", [])
    if info:
        response["output"] = "\n".join(info)

    # Include warnings
    warnings = result.get("log_messages", {}).get("warning", [])
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
