"""Bundled ChimeraX script recipe lookup helpers."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

SCRIPT_RECIPES_NAME = "script_recipes.json"
VALID_OUTPUT_KINDS = {
    "all",
    "command_sequence",
    "html_log",
    "json_payload",
    "log_text",
    "rich_report_payload",
    "script",
}


def load_script_recipes() -> dict[str, Any]:
    """Load bundled ChimeraX script recipes."""
    recipes_path = resources.files("chimerax_mcp.resources").joinpath(SCRIPT_RECIPES_NAME)
    return json.loads(recipes_path.read_text(encoding="utf-8"))


def _recipes() -> list[dict[str, Any]]:
    data = load_script_recipes()
    recipes = data.get("recipes", [])
    return [recipe for recipe in recipes if isinstance(recipe, dict)]


def _valid_categories(recipes: list[dict[str, Any]]) -> set[str]:
    return {"all", *(str(recipe.get("category", "")) for recipe in recipes)}


def _error(message: str) -> dict[str, Any]:
    return {"status": "error", "message": message}


def _text_fields(recipe: dict[str, Any]) -> str:
    pieces: list[str] = []
    for key in ("id", "title", "category", "output_kind", "description"):
        pieces.append(str(recipe.get(key, "")))
    for key in ("uses_api", "related_api_queries", "suggested_next_tools", "notes"):
        value = recipe.get(key, [])
        if isinstance(value, list):
            pieces.extend(str(item) for item in value)
    refs = recipe.get("official_references", [])
    if isinstance(refs, list):
        for ref in refs:
            if isinstance(ref, dict):
                pieces.append(str(ref.get("title", "")))
                pieces.append(str(ref.get("url", "")))
    return " ".join(pieces).lower()


def _score_recipe(recipe: dict[str, Any], query_terms: list[str]) -> int:
    if not query_terms:
        return 1
    recipe_id = str(recipe.get("id", "")).lower()
    title = str(recipe.get("title", "")).lower()
    haystack = _text_fields(recipe)
    score = 0
    for term in query_terms:
        if term == recipe_id:
            score += 100
        if term in recipe_id:
            score += 40
        if term in title:
            score += 25
        if term in haystack:
            score += 5
    return score


def _summary(recipe: dict[str, Any], score: int | None = None) -> dict[str, Any]:
    result = {
        "id": recipe.get("id"),
        "title": recipe.get("title"),
        "category": recipe.get("category"),
        "output_kind": recipe.get("output_kind"),
        "description": recipe.get("description"),
        "uses_api": recipe.get("uses_api", []),
        "suggested_next_tools": recipe.get("suggested_next_tools", []),
    }
    if score is not None:
        result["score"] = score
    return result


def search_script_recipes(
    query: str,
    *,
    category: str = "all",
    output_kind: str = "all",
    limit: int = 10,
) -> dict[str, Any]:
    """Search bundled ChimeraX script recipes."""
    recipes = _recipes()
    normalized_category = category.strip().lower()
    categories = _valid_categories(recipes)
    if normalized_category not in categories:
        return _error(f"category must be one of: {', '.join(sorted(categories))}")

    normalized_output_kind = output_kind.strip().lower()
    if normalized_output_kind not in VALID_OUTPUT_KINDS:
        return _error(f"output_kind must be one of: {', '.join(sorted(VALID_OUTPUT_KINDS))}")

    query_terms = [term.lower() for term in query.split() if term.strip()]
    bounded_limit = max(1, min(limit, 50))
    matches: list[tuple[int, dict[str, Any]]] = []
    for recipe in recipes:
        recipe_category = str(recipe.get("category", "")).lower()
        if normalized_category != "all" and recipe_category != normalized_category:
            continue
        if (
            normalized_output_kind != "all"
            and str(recipe.get("output_kind", "")).lower() != normalized_output_kind
        ):
            continue
        score = _score_recipe(recipe, query_terms)
        if score > 0:
            matches.append((score, recipe))

    matches.sort(key=lambda item: (-item[0], str(item[1].get("id", ""))))
    return {
        "status": "ok",
        "version": load_script_recipes().get("version"),
        "query": query,
        "category": normalized_category,
        "output_kind": normalized_output_kind,
        "limit": bounded_limit,
        "results": [_summary(recipe, score=score) for score, recipe in matches[:bounded_limit]],
    }


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    bounded_max = max(1, max_chars)
    if len(text) <= bounded_max:
        return text, False
    return text[:bounded_max].rstrip(), True


def read_script_recipe(
    recipe_id: str,
    *,
    include_script: bool = True,
    max_chars: int = 10000,
) -> dict[str, Any]:
    """Read one bundled ChimeraX script recipe by ID."""
    normalized_id = recipe_id.strip()
    for recipe in _recipes():
        if str(recipe.get("id")) != normalized_id:
            continue
        result = dict(recipe)
        result["status"] = "ok"
        result["truncated"] = False
        if include_script:
            script, truncated = _truncate(str(result.get("script", "")), max_chars)
            result["script"] = script
            result["truncated"] = truncated
        else:
            result.pop("script", None)
        return result
    return _error(f"No script recipe found: {recipe_id}")
