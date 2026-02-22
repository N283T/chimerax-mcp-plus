"""ChimeraX communication via REST API."""

from __future__ import annotations

import glob
import os
import platform
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx


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
        """Execute a ChimeraX command and return the result."""
        encoded = quote(command, safe="")
        response = self._client.get(f"{self.base_url}/run?command={encoded}")
        response.raise_for_status()
        return {"status": "ok", "output": response.text}

    def get_version(self) -> str:
        """Get ChimeraX version."""
        result = self.run_command("version")
        return result["output"].strip()

    def get_models(self) -> list[dict[str, Any]]:
        """Get list of open models."""
        result = self.run_command("info models")
        lines = result["output"].strip().split("\n")
        models = []
        for line in lines:
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


def detect_chimerax() -> ChimeraXInfo | None:
    """Auto-detect ChimeraX installation."""
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
                matches.sort(reverse=True)
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
                matches.sort(reverse=True)
                return ChimeraXInfo(path=Path(matches[0]))

    env_path = os.environ.get("CHIMERAX_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return ChimeraXInfo(path=path)

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
    cmd.extend(["--cmd", f"remotecontrol rest start port {port}"])

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
