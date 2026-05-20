"""Tests for bundled ChimeraX script recipes."""

from chimerax_mcp.script_recipes import (
    load_script_recipes,
    read_script_recipe,
    search_script_recipes,
)


def test_load_script_recipes_has_expected_recipes() -> None:
    data = load_script_recipes()
    recipe_ids = {recipe["id"] for recipe in data["recipes"]}

    assert data["version"] == 1
    assert "iterate_atomic_models" in recipe_ids
    assert "structure_summary_rich_report_payload" in recipe_ids
    assert len(recipe_ids) >= 10


def test_search_script_recipes_finds_rich_report_payload() -> None:
    result = search_script_recipes(
        "structure summary cards table",
        category="rich_report",
        output_kind="rich_report_payload",
        limit=5,
    )

    assert result["status"] == "ok"
    assert result["results"][0]["id"] == "structure_summary_rich_report_payload"
    assert "chimerax_rich_report" in result["results"][0]["suggested_next_tools"]


def test_search_script_recipes_rejects_invalid_category() -> None:
    result = search_script_recipes("summary", category="bad")

    assert result["status"] == "error"
    assert "category must be one of" in result["message"]


def test_search_script_recipes_rejects_invalid_output_kind() -> None:
    result = search_script_recipes("summary", output_kind="bad")

    assert result["status"] == "error"
    assert "output_kind must be one of" in result["message"]


def test_read_script_recipe_includes_script_by_default() -> None:
    result = read_script_recipe("emit_mcp_json_marker")

    assert result["status"] == "ok"
    assert result["id"] == "emit_mcp_json_marker"
    assert "CHIMERAX_MCP_RESULT_JSON=" in result["script"]
    assert result["truncated"] is False


def test_read_script_recipe_can_omit_script() -> None:
    result = read_script_recipe("iterate_atomic_models", include_script=False)

    assert result["status"] == "ok"
    assert "script" not in result


def test_read_script_recipe_truncates_script() -> None:
    result = read_script_recipe("structure_summary_rich_report_payload", max_chars=40)

    assert result["status"] == "ok"
    assert result["truncated"] is True
    assert len(result["script"]) <= 40


def test_read_script_recipe_missing() -> None:
    result = read_script_recipe("missing")

    assert result == {"status": "error", "message": "No script recipe found: missing"}
