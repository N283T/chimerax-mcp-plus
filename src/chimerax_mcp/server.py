"""MCP server for ChimeraX."""

from __future__ import annotations

import atexit
import contextlib
import shutil
import subprocess
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
    wait_seconds: int = 5,
) -> dict[str, Any]:
    """Start ChimeraX with REST API enabled.

    Args:
        port: Port for REST API (default: 63269)
        nogui: Run without GUI (default: False)
        wait_seconds: Seconds to wait for startup (default: 5)

    Returns:
        Status of the startup attempt.
    """
    global _process

    client = get_client()
    if client.is_running():
        return {"status": "already_running", "message": "ChimeraX is already running"}

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


def _run_command(command: str) -> dict[str, Any]:
    """Internal function to execute a ChimeraX command."""
    client = get_client()
    if not client.is_running():
        return {"status": "error", "message": "ChimeraX is not running"}

    try:
        result = client.run_command(command)
        return result
    except httpx.ConnectError:
        return {"status": "error", "message": "Lost connection to ChimeraX"}
    except httpx.HTTPStatusError as e:
        return {"status": "error", "message": f"HTTP error: {e.response.status_code}"}
    except httpx.HTTPError as e:
        return {"status": "error", "message": f"HTTP error: {e}"}


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
        frames: Number of animation frames (default: 1, instant)

    Returns:
        Result of the turn command.
    """
    if axis.lower() not in VALID_AXES:
        return {
            "status": "error",
            "message": f"Invalid axis '{axis}'. Must be one of: {', '.join(sorted(VALID_AXES))}",
        }
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
            if result.get("status") == "error":
                errors.append(f"{cmd}: {result.get('message', 'unknown error')}")
        except httpx.HTTPError as e:
            errors.append(f"{cmd}: {e}")

    if errors:
        return {"status": "partial", "message": "Some commands failed", "errors": errors}
    return {"status": "ok", "message": f"Reset complete ({len(_RESET_COMMANDS)} commands executed)"}


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
        auto_fit: If True, run ``view`` to fit all models before capture (default: False)

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


@mcp.tool()
def bundle_install(
    bundle_path: str = ".",
    user: bool = True,
) -> dict[str, Any]:
    """Build and install a ChimeraX bundle using echidna.

    Args:
        bundle_path: Path to the bundle project (default: current directory)
        user: Install as user bundle (default: True)

    Returns:
        Result of echidna build and install.
    """
    echidna = shutil.which("echidna")
    if not echidna:
        return {"status": "error", "message": "echidna not found in PATH"}

    path = Path(bundle_path).resolve()
    if not path.exists():
        return {"status": "error", "message": f"Path not found: {path}"}

    cmd = [echidna, "install"]
    if user:
        cmd.append("--user")
    cmd.append(str(path))

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        return {"status": "ok", "output": result.stdout}
    return {"status": "error", "output": result.stdout, "error": result.stderr}


@mcp.tool()
def bundle_run(
    bundle_path: str = ".",
    script: str | None = None,
) -> dict[str, Any]:
    """Build, install, and launch ChimeraX with a bundle using echidna.

    Args:
        bundle_path: Path to the bundle project (default: current directory)
        script: Optional ChimeraX script to run after launch

    Returns:
        Result of echidna run.
    """
    echidna = shutil.which("echidna")
    if not echidna:
        return {"status": "error", "message": "echidna not found in PATH"}

    path = Path(bundle_path).resolve()
    if not path.exists():
        return {"status": "error", "message": f"Path not found: {path}"}

    cmd = [echidna, "run"]
    if script:
        cmd.extend(["--script", script])
    cmd.append(str(path))

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    return {
        "status": "ok" if result.returncode == 0 else "error",
        "output": result.stdout,
        "error": result.stderr if result.returncode != 0 else None,
    }


@mcp.tool()
def bundle_test(
    bundle_path: str = ".",
    smoke: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """Run tests for a ChimeraX bundle using echidna.

    Args:
        bundle_path: Path to the bundle project (default: current directory)
        smoke: Run smoke test instead of pytest (default: False)
        verbose: Verbose output (default: False)

    Returns:
        Test results.
    """
    echidna = shutil.which("echidna")
    if not echidna:
        return {"status": "error", "message": "echidna not found in PATH"}

    path = Path(bundle_path).resolve()
    if not path.exists():
        return {"status": "error", "message": f"Path not found: {path}"}

    cmd = [echidna, "test"]
    if smoke:
        cmd.append("--smoke")
    if verbose:
        cmd.append("--verbose")
    cmd.append(str(path))

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    return {
        "status": "ok" if result.returncode == 0 else "error",
        "output": result.stdout,
        "error": result.stderr if result.returncode != 0 else None,
    }
