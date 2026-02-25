"""Tests for MCP server tools."""

from pathlib import Path
from unittest.mock import patch

import httpx

from chimerax_mcp.chimerax import ChimeraXClient, detect_chimerax
from chimerax_mcp.server import (
    _RESET_COMMANDS,
    MAX_IMAGE_DIMENSION,
    MIN_IMAGE_DIMENSION,
    VALID_AXES,
    VALID_IMAGE_FORMATS,
    _build_tool_screenshot_script,
    chimerax_reset,
    chimerax_screenshot,
    chimerax_status,
    chimerax_tool_screenshot,
    chimerax_turn,
    chimerax_view,
    get_client,
)


class TestDetectFunction:
    def test_detect_returns_info_or_none(self):
        result = detect_chimerax()
        if result is not None:
            assert result.path.exists()
        # None is also valid if ChimeraX not installed


class TestClientStatus:
    def test_is_running_when_not_running(self):
        client = ChimeraXClient(port=59998)
        assert client.is_running() is False


class TestGetClient:
    def test_get_client_returns_client(self):
        client = get_client()
        assert isinstance(client, ChimeraXClient)

    def test_get_client_returns_same_instance(self):
        client1 = get_client()
        client2 = get_client()
        assert client1 is client2


class TestScreenshotValidation:
    """Test screenshot input validation without needing ChimeraX."""

    def test_screenshot_negative_width(self):
        result = chimerax_screenshot.fn(width=-1, height=768, format="png")
        assert result["status"] == "error"
        assert "positive" in result["message"].lower()

    def test_screenshot_zero_width(self):
        result = chimerax_screenshot.fn(width=0, height=768, format="png")
        assert result["status"] == "error"
        assert "positive" in result["message"].lower()

    def test_screenshot_negative_height(self):
        result = chimerax_screenshot.fn(width=1024, height=-1, format="png")
        assert result["status"] == "error"
        assert "positive" in result["message"].lower()

    def test_screenshot_too_large_width(self):
        result = chimerax_screenshot.fn(width=MAX_IMAGE_DIMENSION + 1, height=768, format="png")
        assert result["status"] == "error"
        assert str(MAX_IMAGE_DIMENSION) in result["message"]

    def test_screenshot_too_large_height(self):
        result = chimerax_screenshot.fn(width=1024, height=MAX_IMAGE_DIMENSION + 1, format="png")
        assert result["status"] == "error"
        assert str(MAX_IMAGE_DIMENSION) in result["message"]

    def test_screenshot_invalid_format(self):
        result = chimerax_screenshot.fn(width=1024, height=768, format="bmp")
        assert result["status"] == "error"
        assert "format" in result["message"].lower()

    def test_screenshot_valid_formats(self):
        for fmt in VALID_IMAGE_FORMATS:
            # Will fail at "not running" stage, not validation
            result = chimerax_screenshot.fn(width=100, height=100, format=fmt)
            assert "format" not in result.get("message", "").lower() or result["status"] != "error"

    def test_screenshot_not_running_returns_no_base64(self):
        """Verify file-based response: no image_base64 field."""
        result = chimerax_screenshot.fn(width=100, height=100, format="png")
        assert result["status"] == "error"
        assert "image_base64" not in result

    def test_screenshot_accepts_output_path(self):
        """output_path parameter is accepted (hits not-running before saving)."""
        result = chimerax_screenshot.fn(
            width=100, height=100, format="png", output_path="/tmp/test.png"
        )
        assert result["status"] == "error"
        assert "not running" in result["message"].lower()

    def test_screenshot_whitespace_output_path(self):
        """Whitespace-only output_path is rejected."""
        result = chimerax_screenshot.fn(width=100, height=100, format="png", output_path="  ")
        assert result["status"] == "error"
        assert "empty" in result["message"].lower()


class TestScreenshotHappyPath:
    """Test screenshot success path with mocked ChimeraX client."""

    def test_screenshot_returns_file_path(self, tmp_path: Path):
        """Successful screenshot returns file_path, not image_base64."""
        fake_file = tmp_path.joinpath("shot.png")

        mock_client = ChimeraXClient(port=59998)

        def fake_screenshot(**kwargs):  # noqa: ARG001
            fake_file.write_bytes(b"PNG_DATA")
            return fake_file

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.screenshot = fake_screenshot  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_screenshot.fn(width=100, height=100, format="png")

        assert result["status"] == "ok"
        assert result["file_path"] == str(fake_file)
        assert "image_base64" not in result
        assert result["width"] == 100
        assert result["height"] == 100

    def test_screenshot_with_explicit_output_path(self, tmp_path: Path):
        """User-provided output_path is passed through and returned."""
        user_path = tmp_path.joinpath("my_screenshot.png")

        mock_client = ChimeraXClient(port=59998)

        def fake_screenshot(**kwargs):
            assert kwargs["output_path"] == user_path
            user_path.write_bytes(b"PNG_DATA")
            return user_path

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.screenshot = fake_screenshot  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_screenshot.fn(
                width=100, height=100, format="png", output_path=str(user_path)
            )

        assert result["status"] == "ok"
        assert result["file_path"] == str(user_path)

    def test_screenshot_os_error_handled(self):
        """OSError from client.screenshot is caught and returned."""
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]

        def raise_os_error(**kwargs):  # noqa: ARG001
            raise OSError("Permission denied")

        mock_client.screenshot = raise_os_error  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_screenshot.fn(width=100, height=100, format="png")

        assert result["status"] == "error"
        assert "Permission denied" in result["message"]


class TestStatusTool:
    def test_status_not_running(self):
        result = chimerax_status.fn()
        assert result["status"] == "ok"
        assert result["running"] is False


class TestViewTool:
    def test_view_not_running(self):
        """view returns error when ChimeraX is not running."""
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: False  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_view.fn()

        assert result["status"] == "error"
        assert "not running" in result["message"].lower()

    def test_view_with_target_not_running(self):
        """view with target returns error when ChimeraX is not running."""
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: False  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_view.fn(target=":MK1")

        assert result["status"] == "error"
        assert "not running" in result["message"].lower()

    def test_view_sends_correct_command(self):
        mock_client = ChimeraXClient(port=59998)
        commands_run: list[str] = []

        def fake_run(cmd: str):
            commands_run.append(cmd)
            return {"status": "ok"}

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            chimerax_view.fn(target="#1")

        assert commands_run == ["view #1"]

    def test_view_all_sends_correct_command(self):
        mock_client = ChimeraXClient(port=59998)
        commands_run: list[str] = []

        def fake_run(cmd: str):
            commands_run.append(cmd)
            return {"status": "ok"}

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            chimerax_view.fn()

        assert commands_run == ["view"]


class TestTurnTool:
    def test_turn_not_running(self):
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: False  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_turn.fn()

        assert result["status"] == "error"
        assert "not running" in result["message"].lower()

    def test_turn_invalid_axis(self):
        result = chimerax_turn.fn(axis="w")
        assert result["status"] == "error"
        assert "invalid axis" in result["message"].lower()

    def test_turn_valid_axes(self):
        for axis in VALID_AXES:
            result = chimerax_turn.fn(axis=axis)
            # Should fail at not-running, not validation
            assert "invalid axis" not in result.get("message", "").lower()

    def test_turn_sends_correct_command(self):
        mock_client = ChimeraXClient(port=59998)
        commands_run: list[str] = []

        def fake_run(cmd: str):
            commands_run.append(cmd)
            return {"status": "ok"}

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            chimerax_turn.fn(axis="x", angle=45)

        assert commands_run == ["turn x 45"]

    def test_turn_with_frames(self):
        mock_client = ChimeraXClient(port=59998)
        commands_run: list[str] = []

        def fake_run(cmd: str):
            commands_run.append(cmd)
            return {"status": "ok"}

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            chimerax_turn.fn(axis="y", angle=360, frames=36)

        assert commands_run == ["turn y 360 36"]

    def test_turn_frames_1_not_appended(self):
        """frames=1 (default) does not append frame count to command."""
        mock_client = ChimeraXClient(port=59998)
        commands_run: list[str] = []

        def fake_run(cmd: str):
            commands_run.append(cmd)
            return {"status": "ok"}

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            chimerax_turn.fn(axis="y", angle=90, frames=1)

        assert commands_run == ["turn y 90"]

    def test_turn_negative_frames_rejected(self):
        """Negative frames value is rejected."""
        result = chimerax_turn.fn(axis="y", angle=90, frames=-1)
        assert result["status"] == "error"
        assert "frames" in result["message"].lower()

    def test_turn_zero_frames_rejected(self):
        """Zero frames value is rejected."""
        result = chimerax_turn.fn(axis="y", angle=90, frames=0)
        assert result["status"] == "error"
        assert "frames" in result["message"].lower()

    def test_turn_case_insensitive(self):
        """Uppercase axis is accepted and lowered."""
        mock_client = ChimeraXClient(port=59998)
        commands_run: list[str] = []

        def fake_run(cmd: str):
            commands_run.append(cmd)
            return {"status": "ok"}

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            chimerax_turn.fn(axis="X", angle=90)

        assert commands_run == ["turn x 90"]


class TestResetTool:
    def test_reset_not_running(self):
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: False  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_reset.fn()

        assert result["status"] == "error"
        assert "not running" in result["message"].lower()

    def test_reset_executes_all_commands(self):
        mock_client = ChimeraXClient(port=59998)
        commands_run: list[str] = []

        def fake_run(cmd: str):
            commands_run.append(cmd)
            return {"status": "ok"}

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_reset.fn()

        assert result["status"] == "ok"
        assert commands_run == _RESET_COMMANDS

    def test_reset_partial_failure(self):
        mock_client = ChimeraXClient(port=59998)
        call_count = 0

        def fake_run(cmd: str):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return {
                    "python_values": [],
                    "json_values": [],
                    "log_messages": {},
                    "error": {"type": "UserError", "message": "command failed"},
                }
            return {"python_values": [], "json_values": [], "log_messages": {}, "error": None}

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_reset.fn()

        assert result["status"] == "partial"
        assert len(result["errors"]) == 1

    def test_reset_http_error(self):
        """HTTPError during reset is captured and execution continues."""
        mock_client = ChimeraXClient(port=59998)
        call_count = 0

        def fake_run(cmd: str):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise httpx.HTTPError("connection reset")
            return {"status": "ok"}

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_reset.fn()

        assert result["status"] == "partial"
        assert len(result["errors"]) == 1
        assert "connection reset" in result["errors"][0]

    def test_reset_connect_error_aborts_early(self):
        """ConnectError aborts reset immediately without running remaining commands."""
        mock_client = ChimeraXClient(port=59998)
        commands_run: list[str] = []

        def fake_run(cmd: str):
            commands_run.append(cmd)
            if len(commands_run) == 2:
                raise httpx.ConnectError("connection refused")
            return {"status": "ok"}

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_reset.fn()

        assert result["status"] == "error"
        assert "lost connection" in result["message"].lower()
        # Should have stopped after 2 commands (not all 7)
        assert len(commands_run) == 2

    def test_reset_all_commands_fail(self):
        """When every command fails, status is 'error'."""
        mock_client = ChimeraXClient(port=59998)

        def fake_run(cmd: str):
            return {
                "python_values": [],
                "json_values": [],
                "log_messages": {},
                "error": {"type": "UserError", "message": f"{cmd} failed"},
            }

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_reset.fn()

        assert result["status"] == "error"
        assert "all reset commands failed" in result["message"].lower()
        assert len(result["errors"]) == len(_RESET_COMMANDS)


class TestScreenshotAutoFit:
    def test_auto_fit_true_runs_view(self, tmp_path: Path):
        mock_client = ChimeraXClient(port=59998)
        commands_run: list[str] = []
        fake_file = tmp_path.joinpath("shot.png")

        def fake_run(cmd: str):
            commands_run.append(cmd)
            return {"status": "ok"}

        def fake_screenshot(**kwargs):  # noqa: ARG001
            fake_file.write_bytes(b"PNG_DATA")
            return fake_file

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run  # type: ignore[assignment]
        mock_client.screenshot = fake_screenshot  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_screenshot.fn(width=100, height=100, format="png", auto_fit=True)

        assert result["status"] == "ok"
        assert "view" in commands_run

    def test_auto_fit_false_skips_view(self, tmp_path: Path):
        mock_client = ChimeraXClient(port=59998)
        commands_run: list[str] = []
        fake_file = tmp_path.joinpath("shot.png")

        def fake_run(cmd: str):
            commands_run.append(cmd)
            return {"status": "ok"}

        def fake_screenshot(**kwargs):  # noqa: ARG001
            fake_file.write_bytes(b"PNG_DATA")
            return fake_file

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run  # type: ignore[assignment]
        mock_client.screenshot = fake_screenshot  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_screenshot.fn(width=100, height=100, format="png", auto_fit=False)

        assert result["status"] == "ok"
        assert "view" not in commands_run

    def test_auto_fit_view_failure_still_captures(self, tmp_path: Path):
        """When auto_fit view command raises HTTPError, screenshot still proceeds."""
        mock_client = ChimeraXClient(port=59998)
        fake_file = tmp_path.joinpath("shot.png")

        def fake_run(cmd: str):
            if cmd == "view":
                raise httpx.HTTPError("view failed")
            return {"status": "ok"}

        def fake_screenshot(**kwargs):  # noqa: ARG001
            fake_file.write_bytes(b"PNG_DATA")
            return fake_file

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run  # type: ignore[assignment]
        mock_client.screenshot = fake_screenshot  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_screenshot.fn(width=100, height=100, format="png", auto_fit=True)

        assert result["status"] == "ok"
        assert result["file_path"] == str(fake_file)


class TestToolScreenshot:
    """Tests for chimerax_tool_screenshot."""

    def test_not_running(self):
        """Returns error when ChimeraX is not running."""
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: False  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_tool_screenshot.fn(tool_name="Chain Contacts")

        assert result["status"] == "error"
        assert "not running" in result["message"].lower()

    def test_tool_not_found(self):
        """Returns error when the specified tool is not open."""
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]

        # runscript returns output indicating tool not found
        def fake_run(cmd: str):
            return {
                "python_values": [],
                "json_values": [None],
                "log_messages": {"info": ["ERROR: Tool 'Nonexistent' not found"]},
                "error": None,
            }

        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_tool_screenshot.fn(tool_name="Nonexistent")

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    def test_basic_capture(self, tmp_path: Path):
        """Successful capture returns file_path."""
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]
        output_file = tmp_path.joinpath("tool_shot.png")

        def fake_run(cmd: str):
            # The script writes a file; simulate that
            if "runscript" in cmd:
                output_file.write_bytes(b"PNG_DATA")
                return {
                    "python_values": [],
                    "json_values": [None],
                    "log_messages": {"info": [f"OK: {output_file}"]},
                    "error": None,
                }
            return {"python_values": [], "json_values": [], "log_messages": {}, "error": None}

        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_tool_screenshot.fn(
                tool_name="Chain Contacts", output_path=str(output_file)
            )

        assert result["status"] == "ok"
        assert result["file_path"] == str(output_file)

    def test_default_output_path(self):
        """When no output_path given, a default path under screenshots dir is generated."""
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]
        scripts_written: list[str] = []

        def fake_run(cmd: str):
            if "runscript" in cmd:
                return {
                    "python_values": [],
                    "json_values": [None],
                    "log_messages": {"info": ["OK: /some/path.png"]},
                    "error": None,
                }
            return {"python_values": [], "json_values": [], "log_messages": {}, "error": None}

        mock_client.run_command = fake_run  # type: ignore[assignment]

        original_write_text = Path.write_text

        def capture_write(self_path, content, *args, **kwargs):
            scripts_written.append(content)
            return original_write_text(self_path, content, *args, **kwargs)

        with (
            patch("chimerax_mcp.server.get_client", return_value=mock_client),
            patch("pathlib.Path.write_text", capture_write),
            patch("pathlib.Path.unlink"),
        ):
            result = chimerax_tool_screenshot.fn(tool_name="Chain Contacts")

        assert result["status"] == "ok"
        assert "file_path" in result
        # Default path should be under chimerax-mcp/screenshots
        assert "chimerax-mcp" in result["file_path"]
        assert "screenshots" in result["file_path"]
        # Script should include the generated output path
        assert len(scripts_written) == 1
        assert "tool_" in scripts_written[0]

    def test_resize_params_passed(self, tmp_path: Path):
        """Width and height are included in the generated script."""
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]
        output_file = tmp_path.joinpath("resized.png")
        scripts_written: list[str] = []

        def fake_run(cmd: str):
            if "runscript" in cmd:
                output_file.write_bytes(b"PNG_DATA")
                return {
                    "python_values": [],
                    "json_values": [None],
                    "log_messages": {"info": [f"OK: {output_file}"]},
                    "error": None,
                }
            return {"python_values": [], "json_values": [], "log_messages": {}, "error": None}

        mock_client.run_command = fake_run  # type: ignore[assignment]

        original_write_text = Path.write_text

        def capture_write(self_path, content, *args, **kwargs):
            scripts_written.append(content)
            return original_write_text(self_path, content, *args, **kwargs)

        with (
            patch("chimerax_mcp.server.get_client", return_value=mock_client),
            patch("pathlib.Path.write_text", capture_write),
            patch("pathlib.Path.unlink"),
        ):
            result = chimerax_tool_screenshot.fn(
                tool_name="Chain Contacts",
                width=600,
                height=400,
                output_path=str(output_file),
            )

        assert result["status"] == "ok"
        # The generated script should contain resize dimensions as variable assignments
        assert any("resize_w = 600" in s and "resize_h = 400" in s for s in scripts_written)

    def test_padding_param_passed(self, tmp_path: Path):
        """Padding value is included in the generated script."""
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]
        output_file = tmp_path.joinpath("padded.png")
        scripts_written: list[str] = []

        def fake_run(cmd: str):
            if "runscript" in cmd:
                output_file.write_bytes(b"PNG_DATA")
                return {
                    "python_values": [],
                    "json_values": [None],
                    "log_messages": {"info": [f"OK: {output_file}"]},
                    "error": None,
                }
            return {"python_values": [], "json_values": [], "log_messages": {}, "error": None}

        mock_client.run_command = fake_run  # type: ignore[assignment]

        original_write_text = Path.write_text

        def capture_write(self_path, content, *args, **kwargs):
            scripts_written.append(content)
            return original_write_text(self_path, content, *args, **kwargs)

        with (
            patch("chimerax_mcp.server.get_client", return_value=mock_client),
            patch("pathlib.Path.write_text", capture_write),
            patch("pathlib.Path.unlink"),
        ):
            result = chimerax_tool_screenshot.fn(
                tool_name="Chain Contacts",
                padding=30,
                output_path=str(output_file),
            )

        assert result["status"] == "ok"
        assert any("padding = 30" in s for s in scripts_written)

    def test_empty_tool_name_rejected(self):
        """Empty tool_name is rejected."""
        result = chimerax_tool_screenshot.fn(tool_name="")
        assert result["status"] == "error"
        assert "empty" in result["message"].lower()

    def test_whitespace_tool_name_rejected(self):
        """Whitespace-only tool_name is rejected."""
        result = chimerax_tool_screenshot.fn(tool_name="   ")
        assert result["status"] == "error"
        assert "empty" in result["message"].lower()

    def test_http_error_during_runscript(self):
        """HTTPError during runscript is caught and reported."""
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]

        def fake_run(cmd: str):
            if "runscript" in cmd:
                raise httpx.HTTPError("server error")
            return {"status": "ok", "output": ""}

        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_tool_screenshot.fn(tool_name="Chain Contacts")

        assert result["status"] == "error"
        assert "http error" in result["message"].lower()

    def test_unexpected_output(self):
        """Unexpected output (no OK: or ERROR: marker) returns error."""
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]

        def fake_run(cmd: str):
            return {
                "python_values": [],
                "json_values": [None],
                "log_messages": {"info": ["some random output"]},
                "error": None,
            }

        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_tool_screenshot.fn(tool_name="Chain Contacts")

        assert result["status"] == "error"
        assert "unexpected" in result["message"].lower()

    def test_whitespace_output_path_rejected(self):
        """Whitespace-only output_path is rejected."""
        result = chimerax_tool_screenshot.fn(tool_name="Chain Contacts", output_path="  ")
        assert result["status"] == "error"
        assert "empty" in result["message"].lower()

    def test_negative_width_rejected(self):
        """Negative width is rejected."""
        result = chimerax_tool_screenshot.fn(tool_name="Chain Contacts", width=-1)
        assert result["status"] == "error"
        assert "width" in result["message"].lower()

    def test_zero_width_rejected(self):
        """Zero width is rejected."""
        result = chimerax_tool_screenshot.fn(tool_name="Chain Contacts", width=0)
        assert result["status"] == "error"
        assert "width" in result["message"].lower()

    def test_too_large_width_rejected(self):
        """Width exceeding MAX_IMAGE_DIMENSION is rejected."""
        result = chimerax_tool_screenshot.fn(
            tool_name="Chain Contacts", width=MAX_IMAGE_DIMENSION + 1
        )
        assert result["status"] == "error"
        assert "width" in result["message"].lower()

    def test_negative_height_rejected(self):
        """Negative height is rejected."""
        result = chimerax_tool_screenshot.fn(tool_name="Chain Contacts", height=-1)
        assert result["status"] == "error"
        assert "height" in result["message"].lower()

    def test_negative_padding_rejected(self):
        """Negative padding is rejected."""
        result = chimerax_tool_screenshot.fn(tool_name="Chain Contacts", padding=-5)
        assert result["status"] == "error"
        assert "padding" in result["message"].lower()


class TestBuildToolScreenshotScript:
    """Direct tests for _build_tool_screenshot_script."""

    def test_basic_script(self):
        """Generated script contains tool name and output path."""
        script = _build_tool_screenshot_script(
            tool_name="Chain Contacts", output_path="/tmp/out.png"
        )
        assert "tool_name = 'Chain Contacts'" in script
        assert "output_path = '/tmp/out.png'" in script
        assert "resize_w = None" in script
        assert "resize_h = None" in script
        assert "padding = 0" in script

    def test_with_resize(self):
        """Width and height are embedded correctly."""
        script = _build_tool_screenshot_script(
            tool_name="Log", output_path="/tmp/out.png", width=500, height=300
        )
        assert "resize_w = 500" in script
        assert "resize_h = 300" in script

    def test_with_padding(self):
        """Padding value is embedded correctly."""
        script = _build_tool_screenshot_script(
            tool_name="Log", output_path="/tmp/out.png", padding=20
        )
        assert "padding = 20" in script

    def test_error_handling_present(self):
        """Generated script includes try/except for Qt errors."""
        script = _build_tool_screenshot_script(tool_name="Log", output_path="/tmp/out.png")
        assert "except Exception as exc:" in script
        assert "session.logger.info('ERROR: ' + str(exc))" in script

    def test_no_sys_exit(self):
        """Generated script does not call sys.exit."""
        script = _build_tool_screenshot_script(tool_name="Log", output_path="/tmp/out.png")
        assert "sys.exit" not in script

    def test_checks_pixmap_save_return(self):
        """Generated script checks the return value of pixmap.save()."""
        script = _build_tool_screenshot_script(tool_name="Log", output_path="/tmp/out.png")
        assert "if not pixmap.save(output_path):" in script

    def test_tool_not_found_marker(self):
        """Generated script logs ERROR marker when tool not found."""
        script = _build_tool_screenshot_script(tool_name="Missing", output_path="/tmp/out.png")
        assert "session.logger.info('ERROR: Tool '" in script

    def test_success_marker(self):
        """Generated script logs OK marker on success."""
        script = _build_tool_screenshot_script(tool_name="Log", output_path="/tmp/out.png")
        assert "session.logger.info(f'OK: {output_path}')" in script


class TestConstants:
    def test_valid_formats(self):
        assert "png" in VALID_IMAGE_FORMATS
        assert "jpg" in VALID_IMAGE_FORMATS
        assert "jpeg" in VALID_IMAGE_FORMATS

    def test_dimension_limits(self):
        assert MIN_IMAGE_DIMENSION == 1
        assert MAX_IMAGE_DIMENSION == 8192

    def test_valid_axes(self):
        assert {"x", "y", "z"} == VALID_AXES
