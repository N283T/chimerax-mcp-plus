"""Tests for ChimeraX detection and communication."""

import platform
from pathlib import Path

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
