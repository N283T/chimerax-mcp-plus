"""Tests for ChimeraX detection and communication."""

import platform
import re
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from chimerax_mcp.chimerax import ChimeraXClient, ChimeraXInfo, detect_chimerax


class TestChimeraXInfo:
    def test_chimerax_info_creation(self):
        info = ChimeraXInfo(path=Path("/test/path"))
        assert info.path == Path("/test/path")
        assert info.version is None

    def test_chimerax_info_with_version(self):
        info = ChimeraXInfo(path=Path("/test/path"), version="1.8")
        assert info.version == "1.8"


class TestChimeraXClient:
    def test_client_creation(self):
        client = ChimeraXClient()
        assert client.host == "127.0.0.1"
        assert client.port == 63269
        assert client.base_url == "http://127.0.0.1:63269"

    def test_client_custom_port(self):
        client = ChimeraXClient(port=12345)
        assert client.port == 12345
        assert client.base_url == "http://127.0.0.1:12345"

    def test_client_custom_host(self):
        client = ChimeraXClient(host="192.168.1.1", port=8080)
        assert client.host == "192.168.1.1"
        assert client.base_url == "http://192.168.1.1:8080"

    def test_is_running_when_not_running(self):
        client = ChimeraXClient(port=59999)
        assert client.is_running() is False

    def test_context_manager(self):
        with ChimeraXClient(port=59999) as client:
            assert client.host == "127.0.0.1"
        # Client should be closed after context

    def test_run_command_not_connected(self):
        client = ChimeraXClient(port=59998)
        with pytest.raises(httpx.ConnectError):
            client.run_command("version")


class TestRunCommand:
    """Test run_command JSON/text parsing and _extract_output."""

    @staticmethod
    def _fake_response(status_code: int = 200, **kwargs) -> httpx.Response:
        """Create a fake httpx.Response with a request attached."""
        request = httpx.Request("GET", "http://127.0.0.1:59998/run?command=test")
        return httpx.Response(status_code, request=request, **kwargs)

    def test_json_mode_parsing(self):
        """JSON response is normalized to internal format."""
        client = ChimeraXClient(port=59998)
        json_body = {
            "python values": ["hello"],
            "json values": [None],
            "log messages": {"info": ["Version 1.9"], "warning": []},
            "error": None,
        }
        fake_response = self._fake_response(json=json_body)

        with patch.object(client._client, "get", return_value=fake_response):
            result = client.run_command("version")

        assert result["python_values"] == ["hello"]
        assert result["json_values"] == [None]
        assert result["log_messages"]["info"] == ["Version 1.9"]
        assert result["error"] is None

    def test_plain_text_fallback(self):
        """Non-JSON response falls back to text normalization."""
        client = ChimeraXClient(port=59998)
        fake_response = self._fake_response(text="UCSF ChimeraX version 1.9")

        with patch.object(client._client, "get", return_value=fake_response):
            result = client.run_command("version")

        assert result["python_values"] == []
        assert result["json_values"] == []
        assert result["log_messages"]["info"] == ["UCSF ChimeraX version 1.9"]
        assert result["error"] is None

    def test_plain_text_empty(self):
        """Empty text response produces empty info list."""
        client = ChimeraXClient(port=59998)
        fake_response = self._fake_response(text="  ")

        with patch.object(client._client, "get", return_value=fake_response):
            result = client.run_command("view")

        assert result["log_messages"]["info"] == []

    def test_json_error_preserved(self):
        """ChimeraX-level error is preserved in result."""
        client = ChimeraXClient(port=59998)
        json_body = {
            "python values": [],
            "json values": [],
            "log messages": {},
            "error": {"type": "UserError", "message": "No such model #5"},
        }
        fake_response = self._fake_response(json=json_body)

        with patch.object(client._client, "get", return_value=fake_response):
            result = client.run_command("close #5")

        assert result["error"]["type"] == "UserError"
        assert result["error"]["message"] == "No such model #5"

    def test_extract_output(self):
        """_extract_output joins info messages."""
        result = {
            "log_messages": {"info": ["line 1", "line 2"]},
        }
        assert ChimeraXClient._extract_output(result) == "line 1\nline 2"

    def test_extract_output_empty(self):
        """_extract_output returns empty string for no messages."""
        assert ChimeraXClient._extract_output({}) == ""
        assert ChimeraXClient._extract_output({"log_messages": {}}) == ""

    def test_get_version_from_json(self):
        """get_version extracts version from info messages."""
        client = ChimeraXClient(port=59998)

        def fake_run(cmd: str):
            return {
                "python_values": [],
                "json_values": [None],
                "log_messages": {"info": ["UCSF ChimeraX version 1.9"]},
                "error": None,
            }

        client.run_command = fake_run  # type: ignore[assignment]
        assert client.get_version() == "UCSF ChimeraX version 1.9"

    def test_get_models_from_json_values(self):
        """get_models prefers json_values when available."""
        client = ChimeraXClient(port=59998)
        model_data = [{"id": "#1", "name": "1a0s"}, {"id": "#2", "name": "1xyz"}]

        def fake_run(cmd: str):
            return {
                "python_values": [],
                "json_values": [model_data],
                "log_messages": {"info": ["some text"]},
                "error": None,
            }

        client.run_command = fake_run  # type: ignore[assignment]
        assert client.get_models() == model_data

    def test_get_models_falls_back_to_log(self):
        """get_models falls back to log parsing when json_values is empty."""
        client = ChimeraXClient(port=59998)

        def fake_run(cmd: str):
            return {
                "python_values": [],
                "json_values": [None],
                "log_messages": {"info": ["#1 1a0s", "#2 1xyz"]},
                "error": None,
            }

        client.run_command = fake_run  # type: ignore[assignment]
        models = client.get_models()
        assert models == [{"info": "#1 1a0s"}, {"info": "#2 1xyz"}]


class TestScreenshot:
    """Test ChimeraXClient.screenshot() with mocked run_command."""

    def _ok_result(self) -> dict:
        """Return a normalized successful command result."""
        return {
            "python_values": [],
            "json_values": [None],
            "log_messages": {},
            "error": None,
        }

    def test_default_path_generation(self, tmp_path: Path):
        """Auto-generated path uses correct dir and timestamp pattern."""
        client = ChimeraXClient(port=59998)
        commands_called: list[str] = []

        def fake_run_command(cmd: str):
            commands_called.append(cmd)
            # Simulate ChimeraX writing the file
            parts = cmd.split()
            file_path = Path(parts[1])
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"PNG_DATA")
            return self._ok_result()

        client.run_command = fake_run_command  # type: ignore[assignment]

        with patch("chimerax_mcp.chimerax.Path.home", return_value=tmp_path):
            result = client.screenshot(width=200, height=150, format="png")

        assert result.parent == tmp_path.joinpath(".local", "share", "chimerax-mcp", "screenshots")
        assert re.match(r"screenshot_\d{8}_\d{6}_\d{6}\.png", result.name)
        assert len(commands_called) == 1
        assert "save" in commands_called[0]
        assert "width 200" in commands_called[0]
        assert "height 150" in commands_called[0]

    def test_explicit_output_path(self, tmp_path: Path):
        """User-provided output_path is used directly."""
        client = ChimeraXClient(port=59998)
        user_path = tmp_path.joinpath("subdir", "my_shot.png")

        def fake_run_command(cmd: str):  # noqa: ARG001
            user_path.parent.mkdir(parents=True, exist_ok=True)
            user_path.write_bytes(b"PNG_DATA")
            return self._ok_result()

        client.run_command = fake_run_command  # type: ignore[assignment]

        result = client.screenshot(output_path=user_path)
        assert result == user_path
        assert result.exists()

    def test_raises_if_file_not_created(self, tmp_path: Path):
        """OSError raised when save command succeeds but file is missing."""
        client = ChimeraXClient(port=59998)

        def fake_run_command(cmd: str):  # noqa: ARG001
            return self._ok_result()

        client.run_command = fake_run_command  # type: ignore[assignment]

        with pytest.raises(OSError, match="file not found"):
            client.screenshot(output_path=tmp_path.joinpath("missing.png"))


class TestDetectChimeraX:
    def test_detect_returns_info_or_none(self):
        result = detect_chimerax()
        if result is not None:
            assert isinstance(result, ChimeraXInfo)
            assert result.path.exists()
        # If None, ChimeraX is not installed - that's ok for testing

    @pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
    def test_detect_macos(self):
        # Just verify no errors on macOS
        result = detect_chimerax()
        if result:
            assert "ChimeraX" in str(result.path)
