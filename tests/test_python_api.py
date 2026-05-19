"""Tests for live ChimeraX Python API introspection helpers."""

import json
import shlex
from pathlib import Path
from typing import Any

import httpx

from chimerax_mcp.python_api import (
    MARKER,
    build_python_dir_script,
    build_python_inspect_script,
    parse_introspection_result,
    run_python_api_script,
    validate_symbol,
)


def _run_generated_script(script: str) -> dict[str, Any]:
    class FakeLogger:
        messages: list[str]

        def __init__(self) -> None:
            self.messages = []

        def info(self, message: str) -> None:
            self.messages.append(message)

    class FakeSession:
        logger: FakeLogger

        def __init__(self) -> None:
            self.logger = FakeLogger()

    session = FakeSession()
    exec(script, {"session": session})
    assert session.logger.messages
    return parse_introspection_result({"log_messages": {"info": session.logger.messages}})


def test_validate_symbol_accepts_dotted_import_path() -> None:
    assert validate_symbol("chimerax.atomic.AtomicStructure") is None


def test_validate_symbol_rejects_non_dotted_import_path() -> None:
    assert (
        validate_symbol("__import__('os').system('id')")
        == "symbol must be a dotted import path such as chimerax.atomic.AtomicStructure"
    )


def test_validate_symbol_rejects_dunder_segments() -> None:
    assert (
        validate_symbol("chimerax.atomic.__class__")
        == "symbol must not contain dunder segments"
    )


def test_build_python_inspect_script_contains_safe_bounded_values() -> None:
    script = build_python_inspect_script(
        "chimerax.atomic.AtomicStructure",
        include_dir=True,
        max_doc_chars=123,
    )

    assert "CHIMERAX_MCP_PYTHON_API_JSON=" in script
    assert "chimerax.atomic.AtomicStructure" in script
    assert "max_doc_chars = 123" in script
    assert "eval(" not in script
    assert "exec(" not in script


def test_build_python_dir_script_contains_filter_limit_and_marker() -> None:
    script = build_python_dir_script("chimerax.atomic", filter_text="res", limit=25)

    assert "filter_text = 'res'" in script
    assert "limit = 25" in script
    assert MARKER in script


def test_inspect_script_emits_attributes_when_include_dir_is_true() -> None:
    script = build_python_inspect_script(
        "json.decoder.JSONDecoder",
        include_dir=True,
        max_doc_chars=500,
    )

    payload = _run_generated_script(script)

    assert payload["status"] == "ok"
    assert payload["symbol"] == "json.decoder.JSONDecoder"
    assert "decode" in payload["attributes"]
    assert "attrs" not in payload


def test_dir_script_emits_attributes_and_truncated() -> None:
    script = build_python_dir_script("json.decoder.JSONDecoder", filter_text=None, limit=1)

    payload = _run_generated_script(script)

    assert payload["status"] == "ok"
    assert payload["symbol"] == "json.decoder.JSONDecoder"
    assert len(payload["attributes"]) == 1
    assert payload["truncated"] is True
    assert "attrs" not in payload


def test_parse_introspection_result_reads_marker_payload_from_note_log() -> None:
    result = {
        "log_messages": {
            "note": [f'{MARKER}{{"status":"ok","symbol":"chimerax.atomic"}}'],
        },
    }

    assert parse_introspection_result(result) == {"status": "ok", "symbol": "chimerax.atomic"}


def test_parse_introspection_result_returns_error_when_payload_missing() -> None:
    assert parse_introspection_result({"log_messages": {"note": ["plain log"]}}) == {
        "status": "error",
        "message": "No introspection JSON payload found in ChimeraX output",
    }


def test_run_python_api_script_runs_temp_file_and_returns_payload() -> None:
    payload = {"status": "ok", "value": 42}

    class FakeClient:
        command: str
        path: Path
        path_existed_during_run: bool

        def run_command(self, command: str) -> dict[str, Any]:
            self.command = command
            self.path = Path(shlex.split(command.removeprefix("runscript "))[0])
            self.path_existed_during_run = self.path.exists()
            return {"log_messages": {"info": [MARKER + json.dumps(payload)]}}

    client = FakeClient()

    result = run_python_api_script(client, "print('hello')")

    assert client.command.startswith("runscript ")
    assert result == payload
    assert client.path_existed_during_run is True
    assert not client.path.exists()


def test_run_python_api_script_returns_http_error_status() -> None:
    class FakeClient:
        def run_command(self, command: str) -> dict[str, Any]:
            raise httpx.ConnectError("boom")

    result = run_python_api_script(FakeClient(), "print('hello')")

    assert result["status"] == "error"
    assert "HTTP error" in result["message"]


def test_run_python_api_script_returns_chimerax_error_details() -> None:
    class FakeClient:
        def run_command(self, command: str) -> dict[str, Any]:
            return {"error": {"type": "UserError", "message": "bad script"}}

    result = run_python_api_script(FakeClient(), "print('hello')")

    assert result["status"] == "error"
    assert result["error_type"] == "UserError"
    assert result["message"] == "bad script"
