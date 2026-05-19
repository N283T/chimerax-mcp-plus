"""Tests for MCP server tools."""

import json
import os
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
    VALID_LOG_LEVELS,
    _build_rich_log_html,
    _build_rich_log_script,
    _build_rich_report_html,
    _build_tool_screenshot_script,
    chimerax_api_read,
    chimerax_api_search,
    chimerax_python_dir,
    chimerax_python_inspect,
    chimerax_reset,
    chimerax_rich_log,
    chimerax_rich_report,
    chimerax_screenshot,
    chimerax_start,
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

    def test_status_running_omits_version_by_default(self):
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]

        def fail_get_version():
            raise AssertionError("status should not fetch version by default")

        mock_client.get_version = fail_get_version  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_status.fn()

        assert result == {"status": "ok", "running": True}

    def test_status_running_fetches_version_when_requested(self):
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.get_version = lambda: "UCSF ChimeraX version 1.11.1"  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_status.fn(include_version=True)

        assert result == {
            "status": "ok",
            "running": True,
            "version": "UCSF ChimeraX version 1.11.1",
        }


class TestStartTool:
    def test_start_already_running_omits_version_by_default(self):
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]

        def fail_get_version():
            raise AssertionError("start should not fetch version by default")

        mock_client.get_version = fail_get_version  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_start.fn()

        assert result == {"status": "already_running", "message": "ChimeraX is already running"}

    def test_start_already_running_fetches_version_when_requested(self):
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.get_version = lambda: "UCSF ChimeraX version 1.11.1"  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_start.fn(include_version=True)

        assert result == {
            "status": "already_running",
            "message": "ChimeraX is already running",
            "version": "UCSF ChimeraX version 1.11.1",
        }


class TestApiReferenceTools:
    def test_chimerax_api_search_returns_atomic_module_results(self):
        result = chimerax_api_search.fn(query="AtomicStructure residues", kind="modules", limit=5)

        assert result["status"] == "ok"
        assert any("atomic" in item["name"].lower() for item in result["results"])

    def test_chimerax_api_read_returns_atomic_content(self):
        result = chimerax_api_read.fn(target="atomic", max_chars=500)

        assert result["status"] == "ok"
        assert result["target"] == "atomic"
        assert "Atomic structures" in result["content"]

    def test_chimerax_python_inspect_not_running(self):
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: False  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_python_inspect.fn(symbol="chimerax.atomic.AtomicStructure")

        assert result == {"status": "error", "message": "ChimeraX is not running"}

    def test_chimerax_python_inspect_rejects_unsafe_symbol_before_client_check(self):
        def fail_get_client():
            raise AssertionError("unsafe symbols should be rejected before client lookup")

        with patch("chimerax_mcp.server.get_client", side_effect=fail_get_client):
            result = chimerax_python_inspect.fn(symbol="os")

        assert result["status"] == "error"
        assert "dotted import path" in result["message"]

    def test_chimerax_python_dir_delegates_to_runscript(self):
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: True  # type: ignore[assignment]

        expected = {
            "status": "ok",
            "symbol": "chimerax.atomic",
            "attributes": ["AtomicStructure"],
            "truncated": False,
        }

        def fake_run_command(command: str):
            assert command.startswith("runscript")
            return {
                "log_messages": {
                    "info": [
                        "CHIMERAX_MCP_PYTHON_API_JSON="
                        + json.dumps(expected, sort_keys=True)
                    ],
                },
            }

        mock_client.run_command = fake_run_command  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_python_dir.fn(symbol="chimerax.atomic")

        assert result == expected


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


class TestRichLog:
    """Tests for chimerax_rich_log and helper script generation."""

    def test_valid_log_levels(self):
        assert {"error", "info", "warning"} == VALID_LOG_LEVELS

    def test_rich_log_rejects_empty_html(self):
        result = chimerax_rich_log.fn(html="   ")
        assert result["status"] == "error"
        assert "html" in result["message"].lower()
        assert "empty" in result["message"].lower()

    def test_rich_log_rejects_invalid_level(self):
        result = chimerax_rich_log.fn(html="<b>Hello</b>", level="debug")
        assert result["status"] == "error"
        assert "level" in result["message"].lower()
        assert "error, info, warning" in result["message"]

    def test_rich_log_not_running(self):
        mock_client = ChimeraXClient(port=59998)
        mock_client.is_running = lambda: False  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_rich_log.fn(html="<b>Hello</b>")

        assert result["status"] == "error"
        assert "not running" in result["message"].lower()

    def test_build_rich_log_html_adds_optional_title(self):
        html = _build_rich_log_html("<p>Body</p>", title="Analysis <One>")
        assert "chimerax-mcp-rich-log" in html
        assert "Analysis &lt;One&gt;" in html
        assert "<p>Body</p>" in html

    def test_build_rich_log_html_without_title_keeps_html(self):
        assert _build_rich_log_html("<em>Body</em>") == "<em>Body</em>"

    def test_build_rich_log_script_uses_html_logger_and_thread_safe(self):
        script = _build_rich_log_script("<p>Hello</p>", "warning", marker_id="test-marker")
        assert "html_content = '<p>Hello</p>'" in script
        assert "logger_method = session.logger.warning" in script
        assert "is_html=True" in script
        assert "session.ui.thread_safe(write_log)" in script
        assert "write_log()" in script
        assert "__CHIMERAX_MCP_RICH_LOG_OK__" not in script
        assert "__CHIMERAX_MCP_RICH_LOG_ERROR__" not in script

    def test_build_rich_log_script_does_not_log_private_success_marker(self):
        script = _build_rich_log_script("<p>Hello</p>", "info", marker_id="test-marker")

        assert "session.logger.info('__CHIMERAX_MCP_RICH_LOG_OK__:" not in script
        assert "print('__CHIMERAX_MCP_RICH_LOG_OK__:" not in script

    def test_rich_log_returns_ok_without_private_marker_when_runscript_succeeds(self):
        mock_client = ChimeraXClient(port=59998)

        def fake_run_command(cmd: str):  # noqa: ARG001
            return {
                "python_values": [],
                "json_values": [],
                "log_messages": {},
                "error": None,
            }

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run_command  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_rich_log.fn(html="<p>Hi</p>")

        assert result == {"status": "ok", "level": "info", "message": "Rich log written"}

    def test_rich_log_saves_generated_html(self, tmp_path: Path):
        mock_client = ChimeraXClient(port=59998)
        html_path = tmp_path.joinpath("reports", "summary.html")

        def fake_run_command(cmd: str):  # noqa: ARG001
            return {
                "python_values": [],
                "json_values": [],
                "log_messages": {},
                "error": None,
            }

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run_command  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_rich_log.fn(
                html="<p>Saved body</p>",
                title="Saved <Report>",
                save_html_path=str(html_path),
            )

        assert result["status"] == "ok"
        assert result["html_path"] == str(html_path)
        saved_html = html_path.read_text()
        assert "Saved &lt;Report&gt;" in saved_html
        assert "<p>Saved body</p>" in saved_html

    def test_rich_log_rejects_existing_html_save_path_without_overwrite(self, tmp_path: Path):
        mock_client = ChimeraXClient(port=59998)
        commands_run: list[str] = []
        html_path = tmp_path.joinpath("existing.html")
        html_path.write_text("old")

        def fake_run_command(cmd: str):  # noqa: ARG001
            commands_run.append(cmd)
            return {
                "python_values": [],
                "json_values": [],
                "log_messages": {},
                "error": None,
            }

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run_command  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_rich_log.fn(
                html="<p>New body</p>",
                save_html_path=str(html_path),
            )

        assert result["status"] == "error"
        assert "already exists" in result["message"]
        assert html_path.read_text() == "old"
        assert commands_run == []

    def test_rich_log_sends_runscript_when_running(self):
        mock_client = ChimeraXClient(port=59998)
        commands_run: list[str] = []

        def fake_run_command(cmd: str):
            commands_run.append(cmd)
            Path(cmd.removeprefix("runscript ").strip('"')).read_text()
            return {
                "python_values": [],
                "json_values": [],
                "log_messages": {},
                "error": None,
            }

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run_command  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_rich_log.fn(
                html="<strong>Result</strong>", level="info", title="Summary"
            )

        assert result == {"status": "ok", "level": "info", "message": "Rich log written"}
        assert len(commands_run) == 1
        assert commands_run[0].startswith("runscript ")

    def test_rich_log_returns_script_error(self):
        mock_client = ChimeraXClient(port=59998)

        def fake_run_command(cmd: str):  # noqa: ARG001
            return {
                "python_values": [],
                "json_values": [],
                "log_messages": {},
                "error": {"type": "RuntimeError", "message": "boom"},
            }

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run_command  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_rich_log.fn(html="<p>Hi</p>")

        assert result == {"status": "error", "error_type": "RuntimeError", "message": "boom"}

    def test_rich_log_ignores_error_text_without_sentinel(self):
        mock_client = ChimeraXClient(port=59998)

        def fake_run_command(cmd: str):  # noqa: ARG001
            return {
                "python_values": [],
                "json_values": [],
                "log_messages": {
                    "info": ["<p>Caller HTML mentions ERROR: but is not a marker</p>"],
                },
                "error": None,
            }

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run_command  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_rich_log.fn(html="<p>ERROR: caller text</p>")

        assert result == {"status": "ok", "level": "info", "message": "Rich log written"}

    def test_rich_log_ignores_combined_log_output_when_runscript_succeeds(self):
        mock_client = ChimeraXClient(port=59998)

        def fake_run_command(cmd: str):  # noqa: ARG001
            return {
                "python_values": [],
                "json_values": [],
                "log_messages": {"info": ["<p>Rendered HTML and command echo</p>"]},
                "error": None,
            }

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run_command  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_rich_log.fn(html="<p>combined log output</p>")

        assert result == {"status": "ok", "level": "info", "message": "Rich log written"}

    def test_rich_log_ignores_static_sentinel_text_when_runscript_succeeds(self):
        mock_client = ChimeraXClient(port=59998)

        def fake_run_command(cmd: str):  # noqa: ARG001
            return {
                "python_values": [],
                "json_values": [],
                "log_messages": {
                    "info": [
                        "__CHIMERAX_MCP_RICH_LOG_ERROR__:not-the-nonce: caller text",
                        "__CHIMERAX_MCP_RICH_LOG_OK__:not-the-nonce",
                    ]
                },
                "error": None,
            }

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run_command  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_rich_log.fn(
                html="<p>__CHIMERAX_MCP_RICH_LOG_ERROR__:not-the-nonce: caller text</p>"
            )

        assert result == {"status": "ok", "level": "info", "message": "Rich log written"}

    def test_rich_log_quotes_temp_script_path_with_spaces(self, tmp_path: Path):
        mock_client = ChimeraXClient(port=59998)
        commands_run: list[str] = []
        script_path = tmp_path.joinpath("rich log script.py")
        fd = os.open(script_path, os.O_CREAT | os.O_RDWR)

        def fake_run_command(cmd: str):
            commands_run.append(cmd)
            Path(cmd.removeprefix("runscript ").strip('"')).read_text()
            return {
                "python_values": [],
                "json_values": [],
                "log_messages": {},
                "error": None,
            }

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run_command  # type: ignore[assignment]

        with (
            patch("chimerax_mcp.server.get_client", return_value=mock_client),
            patch("chimerax_mcp.server.tempfile.mkstemp", return_value=(fd, str(script_path))),
        ):
            result = chimerax_rich_log.fn(html="<p>Hi</p>")

        assert result["status"] == "ok"
        assert commands_run == [f'runscript "{script_path}"']

    def test_rich_log_returns_chimerax_level_error_before_marker_parsing(self):
        mock_client = ChimeraXClient(port=59998)

        def fake_run_command(cmd: str):  # noqa: ARG001
            return {
                "python_values": [],
                "json_values": [],
                "log_messages": {"info": ["__CHIMERAX_MCP_RICH_LOG_OK__:not-the-nonce"]},
                "error": {"type": "UserError", "message": "runscript failed"},
            }

        mock_client.is_running = lambda: True  # type: ignore[assignment]
        mock_client.run_command = fake_run_command  # type: ignore[assignment]

        with patch("chimerax_mcp.server.get_client", return_value=mock_client):
            result = chimerax_rich_log.fn(html="<p>Hi</p>")

        assert result == {
            "status": "error",
            "error_type": "UserError",
            "message": "runscript failed",
        }


class TestRichReport:
    """Tests for rich report block composer generation and logging."""

    def test_build_rich_report_html_renders_dark_block_composer(self):
        html = _build_rich_report_html(
            title="Carbonic Anhydrase II",
            subtitle="PDB 1CA2 · active-site snapshot",
            theme="dark",
            accent_color="#58a6ff",
            blocks=[
                {
                    "type": "cards",
                    "items": [
                        {"label": "Model", "value": "#1 · 1CA2"},
                        {"label": "Cofactor", "value": "Zn²⁺", "color": "#ffd33d"},
                    ],
                },
                {"type": "heading", "text": "Functional feature map"},
                {
                    "type": "table",
                    "columns": ["Feature", "Residues", "View"],
                    "rows": [
                        [
                            "Active site",
                            "His64",
                            {
                                "text": "red",
                                "style": "background:#da3633;color:white;font-weight:800;",
                            },
                        ],
                    ],
                    "header_color": "#1f6feb",
                },
                {"type": "callout", "tone": "warning", "title": "Note", "text": "Draft report"},
            ],
        )

        assert "chimerax-mcp-rich-report" in html
        assert "background:#0d1117" in html
        assert "Carbonic Anhydrase II" in html
        assert "PDB 1CA2 · active-site snapshot" in html
        assert "#1 · 1CA2" in html
        assert "Zn²⁺" in html
        assert "Functional feature map" in html
        assert "background:#da3633;color:white;font-weight:800;" in html
        assert "Draft report" in html

    def test_build_rich_report_html_renders_light_theme(self):
        html = _build_rich_report_html(
            title="Light report",
            theme="light",
            blocks=[{"type": "paragraph", "text": "Readable on white backgrounds"}],
        )

        assert "background:#ffffff" in html
        assert "color:#111827" in html
        assert "Readable on white backgrounds" in html

    def test_build_rich_report_html_auto_uses_css_color_scheme(self):
        html = _build_rich_report_html(
            title="Auto report",
            theme="auto",
            blocks=[{"type": "paragraph", "text": "Follows ChimeraX appearance"}],
        )

        assert "color-scheme:light dark" in html
        assert "@media (prefers-color-scheme: light)" in html
        assert "--cxmcp-bg:#0d1117" in html
        assert "--cxmcp-bg:#ffffff" in html
        assert "--cxmcp-text:#111827" in html
        assert "Follows ChimeraX appearance" in html

    def test_build_rich_report_html_escapes_text_but_preserves_raw_html(self):
        html = _build_rich_report_html(
            title="Unsafe <title>",
            theme="dark",
            blocks=[
                {"type": "paragraph", "text": "Text <script>alert(1)</script>"},
                {"type": "html", "html": "<p><b>Trusted raw HTML</b></p>"},
            ],
        )

        assert "Unsafe &lt;title&gt;" in html
        assert "Text &lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "<p><b>Trusted raw HTML</b></p>" in html
        assert "Text <script>" not in html

    def test_build_rich_report_html_renders_badges_and_legend(self):
        html = _build_rich_report_html(
            title="Legend report",
            blocks=[
                {
                    "type": "badges",
                    "items": ["interactive", {"label": "view colored", "tone": "success"}],
                },
                {
                    "type": "legend",
                    "items": [
                        {"label": "Active site", "color": "#da3633", "description": "His64"},
                        {
                            "label": "Zn²⁺ ligands",
                            "color": "#fb8500",
                            "description": "His94/96/119",
                        },
                    ],
                },
            ],
        )

        assert "interactive" in html
        assert "view colored" in html
        assert "Active site" in html
        assert "#da3633" in html
        assert "His94/96/119" in html

    def test_build_rich_report_html_renders_progress_and_columns(self):
        html = _build_rich_report_html(
            title="Layout report",
            blocks=[
                {
                    "type": "progress",
                    "label": "Model confidence",
                    "value": 82,
                    "max": 100,
                    "color": "#238636",
                },
                {
                    "type": "columns",
                    "items": [
                        {"type": "paragraph", "text": "Left column"},
                        {
                            "type": "table",
                            "columns": ["Metric", "Value"],
                            "rows": [["Atoms", "327"]],
                        },
                    ],
                },
            ],
        )

        assert "Model confidence" in html
        assert "82%" in html
        assert "width:82.0%" in html
        assert "#238636" in html
        assert "Left column" in html
        assert "Atoms" in html

    def test_rich_report_rejects_empty_title(self):
        result = chimerax_rich_report.fn(title="  ")
        assert result["status"] == "error"
        assert "title" in result["message"].lower()
        assert "empty" in result["message"].lower()

    def test_rich_report_rejects_invalid_level(self):
        result = chimerax_rich_report.fn(title="Report", level="debug")
        assert result["status"] == "error"
        assert "level" in result["message"].lower()

    def test_rich_report_rejects_invalid_theme(self):
        result = chimerax_rich_report.fn(title="Report", theme="sepia")
        assert result["status"] == "error"
        assert "theme" in result["message"].lower()

    def test_rich_report_rejects_unknown_block_type(self):
        result = chimerax_rich_report.fn(title="Report", blocks=[{"type": "timeline"}])
        assert result["status"] == "error"
        assert "blocks[0].type" in result["message"]

    def test_rich_report_rejects_malformed_table_columns_and_rows(self):
        result = chimerax_rich_report.fn(title="Report", blocks=[{"type": "table", "columns": 3}])
        assert result["status"] == "error"
        assert "blocks[0].columns" in result["message"]

        result = chimerax_rich_report.fn(title="Report", blocks=[{"type": "table", "rows": 3}])
        assert result["status"] == "error"
        assert "blocks[0].rows" in result["message"]

        result = chimerax_rich_report.fn(
            title="Report", blocks=[{"type": "columns", "items": "not-a-list"}]
        )
        assert result["status"] == "error"
        assert "blocks[0].items" in result["message"]

    def test_rich_report_builds_html_and_writes_it(self):
        captured: dict[str, str] = {}

        def fake_write_rich_log(
            html: str,
            level: str,
            save_html_path: str | None = None,
            overwrite: bool = False,
        ):
            captured["html"] = html
            captured["level"] = level
            captured["save_html_path"] = save_html_path or ""
            captured["overwrite"] = str(overwrite)
            return {"status": "ok", "level": level, "message": "Rich log written"}

        with patch("chimerax_mcp.server._write_rich_log", side_effect=fake_write_rich_log):
            result = chimerax_rich_report.fn(
                title="Analysis Summary",
                subtitle="Composer output",
                theme="dark",
                save_html_path="/tmp/report.html",
                overwrite=True,
                blocks=[
                    {"type": "cards", "items": [{"label": "Models", "value": 1}]},
                    {"type": "paragraph", "text": "Complete"},
                ],
            )

        assert result == {"status": "ok", "level": "info", "message": "Rich log written"}
        assert captured["level"] == "info"
        assert "Analysis Summary" in captured["html"]
        assert "Composer output" in captured["html"]
        assert "Models" in captured["html"]
        assert "Complete" in captured["html"]
        assert captured["save_html_path"] == "/tmp/report.html"
        assert captured["overwrite"] == "True"
