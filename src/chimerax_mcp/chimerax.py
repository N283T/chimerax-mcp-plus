"""ChimeraX communication via REST API."""

from __future__ import annotations

import glob
import logging
import os
import platform
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ChimeraXInfo:
    """Information about a ChimeraX installation."""

    path: Path
    version: str | None = None


class ChimeraXClient:
    """Client for communicating with ChimeraX via REST API."""

    def __init__(self, host: str = "127.0.0.1", port: int = 63269) -> None:
        self.host = host
        self.port = port
        self._client = httpx.Client(timeout=30.0)

    def __enter__(self) -> ChimeraXClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def is_running(self) -> bool:
        """Check if ChimeraX REST server is running."""
        try:
            response = self._client.get(f"{self.base_url}/run?command=version")
            return response.status_code == 200
        except httpx.ConnectError:
            return False

    def run_command(self, command: str) -> dict[str, Any]:
        """Execute a ChimeraX command and return the result.

        Returns a normalized dict with keys: python_values, json_values,
        log_messages, error.  Works in both ``json true`` and plain-text modes.
        """
        encoded = quote(command, safe="")
        response = self._client.get(f"{self.base_url}/run?command={encoded}")
        response.raise_for_status()

        # Try JSON mode first, fall back to plain text
        try:
            data = response.json()
            return {
                "python_values": data.get("python values", []),
                "json_values": data.get("json values", []),
                "log_messages": data.get("log messages", {}),
                "error": data.get("error"),
            }
        except (ValueError, KeyError):
            # Plain text mode (json false) — normalize to same shape
            text = response.text.strip()
            return {
                "python_values": [],
                "json_values": [],
                "log_messages": {"info": [text] if text else []},
                "error": None,
            }

    @staticmethod
    def _extract_output(result: dict[str, Any]) -> str:
        """Extract human-readable output from a command result."""
        msgs = result.get("log_messages", {})
        # Include both 'info' and 'note' levels (session.logger.info() -> 'note')
        lines: list[str] = []
        for level in ("info", "note"):
            lines.extend(msgs.get(level, []))
        return "\n".join(lines)

    def get_version(self) -> str:
        """Get ChimeraX version."""
        result = self.run_command("version")
        return self._extract_output(result).strip()

    def get_models(self) -> list[dict[str, Any]]:
        """Get list of open models."""
        result = self.run_command("info models")
        # Prefer json_values if available
        json_vals = result.get("json_values", [])
        if json_vals and json_vals[0] is not None:
            first = json_vals[0]
            return first if isinstance(first, list) else [first]
        # Fall back to parsing info log messages
        output = self._extract_output(result)
        models = []
        for line in output.strip().split("\n"):
            if line.strip():
                models.append({"info": line.strip()})
        return models

    def screenshot(
        self,
        width: int = 1024,
        height: int = 768,
        format: str = "png",  # noqa: A002
        output_path: Path | None = None,
    ) -> Path:
        """Capture screenshot and save to file.

        Args:
            width: Image width in pixels.
            height: Image height in pixels.
            format: Image format (png, jpg).
            output_path: Where to save. If None, auto-generates under
                ``~/.local/share/chimerax-mcp/screenshots/``.

        Returns:
            Path to the saved image file.

        Raises:
            OSError: If the parent directory cannot be created or the file
                was not written after the save command.
        """
        if output_path is None:
            screenshot_dir = Path.home().joinpath(".local", "share", "chimerax-mcp", "screenshots")
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
            output_path = screenshot_dir.joinpath(f"screenshot_{timestamp}.{format}")
        else:
            output_path.parent.mkdir(parents=True, exist_ok=True)

        self.run_command(f"save {output_path} width {width} height {height}")

        if not output_path.exists():
            msg = f"ChimeraX save command completed but file not found: {output_path}"
            raise OSError(msg)
        return output_path

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()


def _version_sort_key(path: str) -> tuple[int, ...]:
    """Extract version numbers from a ChimeraX path for natural sorting.

    Matches the version segment after "ChimeraX" (e.g., "1.10" from
    "ChimeraX-1.10.app") and returns a tuple of integers for correct
    numeric comparison. Digits elsewhere in the path are ignored.
    """
    match = re.search(r"ChimeraX[- ]?(\d[\d.]*)", path, re.IGNORECASE)
    if match:
        return tuple(int(n) for n in match.group(1).split(".") if n)
    return ()


def detect_chimerax() -> ChimeraXInfo | None:
    """Auto-detect ChimeraX installation.

    The CHIMERAX_PATH environment variable takes priority over auto-detection,
    allowing users to specify a particular ChimeraX version or installation.
    """
    env_path = os.environ.get("CHIMERAX_PATH")
    if env_path:
        path = Path(env_path)
        if path.is_file():
            return ChimeraXInfo(path=path)
        logger.warning(
            "CHIMERAX_PATH=%s does not exist or is not a file, falling back to auto-detection",
            env_path,
        )

    system = platform.system()

    if system == "Darwin":
        patterns = [
            "/Applications/ChimeraX*.app/Contents/MacOS/ChimeraX",
            "/Applications/UCSF-ChimeraX*.app/Contents/MacOS/ChimeraX",
            os.path.expanduser("~/Applications/ChimeraX*.app/Contents/MacOS/ChimeraX"),
        ]
        for pattern in patterns:
            matches = glob.glob(pattern)
            if matches:
                matches.sort(key=_version_sort_key, reverse=True)
                return ChimeraXInfo(path=Path(matches[0]))

    elif system == "Linux":
        paths = [
            "/usr/bin/chimerax",
            "/usr/local/bin/chimerax",
            os.path.expanduser("~/.local/bin/chimerax"),
            "/opt/UCSF/ChimeraX/bin/ChimeraX",
        ]
        for p in paths:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return ChimeraXInfo(path=Path(p))

    elif system == "Windows":
        patterns = [
            r"C:\Program Files\ChimeraX*\bin\ChimeraX-console.exe",
            r"C:\Program Files\UCSF\ChimeraX*\bin\ChimeraX-console.exe",
        ]
        for pattern in patterns:
            matches = glob.glob(pattern)
            if matches:
                matches.sort(key=_version_sort_key, reverse=True)
                return ChimeraXInfo(path=Path(matches[0]))

    return None


def start_chimerax(
    chimerax_path: Path | None = None,
    port: int = 63269,
    nogui: bool = False,
) -> subprocess.Popen[bytes]:
    """Start ChimeraX with REST API enabled."""
    if chimerax_path is None:
        info = detect_chimerax()
        if info is None:
            raise RuntimeError("ChimeraX not found. Set CHIMERAX_PATH or install ChimeraX.")
        chimerax_path = info.path

    cmd = [str(chimerax_path)]
    if nogui:
        cmd.append("--nogui")
    cmd.extend(["--cmd", f"remotecontrol rest start port {port} json true log true"])

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
