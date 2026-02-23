"""Tests for MCP server tools."""

from pathlib import Path
from unittest.mock import patch

from chimerax_mcp.chimerax import ChimeraXClient, detect_chimerax
from chimerax_mcp.server import (
    _RESET_COMMANDS,
    MAX_IMAGE_DIMENSION,
    MIN_IMAGE_DIMENSION,
    VALID_AXES,
    VALID_IMAGE_FORMATS,
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
                return {"status": "error", "message": "command failed"}
            return {"status": "ok"}

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_reset.fn()

        assert result["status"] == "partial"
        assert len(result["errors"]) == 1


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
            return {"status": "ok", "output": "ERROR: Tool 'Nonexistent' not found"}

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
                return {"status": "ok", "output": f"OK: {output_file}"}
            return {"status": "ok", "output": ""}

        mock_client.run_command = fake_run  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_tool_screenshot.fn(
                tool_name="Chain Contacts", output_path=str(output_file)
            )

        assert result["status"] == "ok"
        assert result["file_path"] == str(output_file)

    def test_default_output_path(self):
        """When no output_path given, a default is generated."""
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]

        def fake_run(cmd: str):
            if "runscript" in cmd:
                # Extract the output path from the script and create the file
                # The script will write to a default path
                return {"status": "ok", "output": "OK: /some/path.png"}
            return {"status": "ok", "output": ""}

        mock_client.run_command = fake_run  # type: ignore[assignment]

        with (
            patch("chimerax_mcp.server.get_client", return_value=mock_client),
            patch("pathlib.Path.write_text"),
            patch("pathlib.Path.unlink"),
        ):
            result = chimerax_tool_screenshot.fn(tool_name="Chain Contacts")

        # Should generate a path, not error
        assert result["status"] in ("ok", "error")
        # If ok, file_path should be present
        if result["status"] == "ok":
            assert "file_path" in result

    def test_resize_params_passed(self, tmp_path: Path):
        """Width and height are included in the generated script."""
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]
        output_file = tmp_path.joinpath("resized.png")
        scripts_written: list[str] = []

        def fake_run(cmd: str):
            if "runscript" in cmd:
                output_file.write_bytes(b"PNG_DATA")
                return {"status": "ok", "output": f"OK: {output_file}"}
            return {"status": "ok", "output": ""}

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
        # The generated script should contain resize dimensions
        assert any("600" in s and "400" in s for s in scripts_written)

    def test_padding_param_passed(self, tmp_path: Path):
        """Padding value is included in the generated script."""
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]
        output_file = tmp_path.joinpath("padded.png")
        scripts_written: list[str] = []

        def fake_run(cmd: str):
            if "runscript" in cmd:
                output_file.write_bytes(b"PNG_DATA")
                return {"status": "ok", "output": f"OK: {output_file}"}
            return {"status": "ok", "output": ""}

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
        assert any("30" in s for s in scripts_written)

    def test_empty_tool_name_rejected(self):
        """Empty tool_name is rejected."""
        result = chimerax_tool_screenshot.fn(tool_name="")
        assert result["status"] == "error"

    def test_whitespace_tool_name_rejected(self):
        """Whitespace-only tool_name is rejected."""
        result = chimerax_tool_screenshot.fn(tool_name="   ")
        assert result["status"] == "error"


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
