"""Tests for MCP server tools."""

from chimerax_mcp.chimerax import ChimeraXClient, detect_chimerax
from chimerax_mcp.server import (
    MAX_IMAGE_DIMENSION,
    MIN_IMAGE_DIMENSION,
    VALID_IMAGE_FORMATS,
    chimerax_screenshot,
    chimerax_status,
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


class TestStatusTool:
    def test_status_not_running(self):
        result = chimerax_status.fn()
        assert result["status"] == "ok"
        assert result["running"] is False


class TestConstants:
    def test_valid_formats(self):
        assert "png" in VALID_IMAGE_FORMATS
        assert "jpg" in VALID_IMAGE_FORMATS
        assert "jpeg" in VALID_IMAGE_FORMATS

    def test_dimension_limits(self):
        assert MIN_IMAGE_DIMENSION == 1
        assert MAX_IMAGE_DIMENSION == 8192
