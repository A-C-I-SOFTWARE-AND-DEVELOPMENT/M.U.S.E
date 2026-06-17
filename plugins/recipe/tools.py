"""One agent-facing recipe tool (pure, offline — no network, no API key).

``recipe_card`` takes a title plus structured ingredients and steps (the model
supplies the content, exactly like the contract's recipe widget), then validates
units, assigns stable ids, and scales every ingredient amount proportionally to a
target serving count. Deterministic; returns the uniform ``{"success": bool, …}``
envelope. The only gate is ``recipe.enabled``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from plugins.recipe import config as recipe_config

# Units the contract's recipe widget accepts; ``None`` (countable items) is allowed.
_UNITS = frozenset(
    {"g", "kg", "ml", "l", "tsp", "tbsp", "cup", "fl_oz", "oz", "lb", "pinch"}
)


def _json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _err(error: str, message: str = "", **extra: Any) -> str:
    body: Dict[str, Any] = {"success": False, "error": error}
    if message:
        body["message"] = message
    body.update(extra)
    return _json(body)


def _ok(**payload: Any) -> str:
    return _json({"success": True, **payload})


def check_recipe_requirements() -> bool:
    """Offer the tool only when ``recipe.enabled`` is True."""
    return recipe_config.load_config().enabled


def _enabled_or_error() -> Optional[str]:
    if not recipe_config.load_config().enabled:
        return _err("plugin_disabled", "recipe.enabled is false")
    return None


_INGREDIENT = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Ingredient name (fold counting nouns in, e.g. 'garlic cloves')."},
        "amount": {"type": "number", "description": "Quantity at base_servings."},
        "unit": {
            "type": "string",
            "enum": sorted(_UNITS),
            "description": "Measurement unit; omit for countable items.",
        },
        "id": {"type": "string", "description": "Optional stable id; auto-assigned if omitted."},
    },
    "required": ["name", "amount"],
    "additionalProperties": False,
}

_STEP = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Short step summary, e.g. 'Boil pasta'."},
        "content": {"type": "string", "description": "Full instruction text."},
        "timer_seconds": {"type": "integer", "minimum": 0, "description": "Timer for wait/cook steps."},
        "id": {"type": "string", "description": "Optional stable id; auto-assigned if omitted."},
    },
    "required": ["content"],
    "additionalProperties": False,
}

RECIPE_SCHEMA: Dict[str, Any] = {
    "name": "recipe_card",
    "description": (
        "Render a structured, scalable recipe card. You supply the title, "
        "ingredients (name, amount, optional unit), and steps; the tool validates "
        "units, assigns stable ingredient/step ids, and — when `servings` differs "
        "from `base_servings` — scales every ingredient amount proportionally. "
        "Pure and offline (no network)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Recipe name."},
            "description": {"type": "string"},
            "ingredients": {"type": "array", "items": _INGREDIENT, "minItems": 1},
            "steps": {"type": "array", "items": _STEP, "minItems": 1},
            "base_servings": {"type": "integer", "minimum": 1, "description": "Servings the amounts are written for (default 4)."},
            "servings": {"type": "integer", "minimum": 1, "description": "Target servings to scale to; defaults to base_servings."},
            "notes": {"type": "string"},
        },
        "required": ["title", "ingredients", "steps"],
        "additionalProperties": False,
    },
}


def handle_recipe_card(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled

    title = args.get("title")
    if not isinstance(title, str) or not title.strip():
        return _err("bad_args", "title is required")

    raw_ingredients = args.get("ingredients")
    if not isinstance(raw_ingredients, list) or not raw_ingredients:
        return _err("bad_args", "ingredients must be a non-empty array")
    raw_steps = args.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        return _err("bad_args", "steps must be a non-empty array")

    base = args.get("base_servings")
    base_servings = int(base) if isinstance(base, (int, float)) and int(base) > 0 else 4
    target = args.get("servings")
    target_servings = (
        int(target) if isinstance(target, (int, float)) and int(target) > 0 else base_servings
    )
    scale = target_servings / base_servings

    ingredients: List[Dict[str, Any]] = []
    for i, ing in enumerate(raw_ingredients, start=1):
        if not isinstance(ing, dict):
            return _err("bad_args", f"ingredient #{i} is not an object")
        name = ing.get("name")
        if not isinstance(name, str) or not name.strip():
            return _err("bad_args", f"ingredient #{i} is missing a name")
        amount = ing.get("amount")
        if not isinstance(amount, (int, float)):
            return _err("bad_args", f"ingredient #{i} ('{name}') is missing a numeric amount")
        unit = ing.get("unit")
        if unit is not None and unit not in _UNITS:
            return _err("bad_args", f"ingredient #{i} has invalid unit {unit!r}")
        ingredients.append({
            "id": str(ing.get("id") or f"{i:04d}"),
            "name": name,
            "amount": round(float(amount) * scale, 4),
            "unit": unit,
        })

    steps: List[Dict[str, Any]] = []
    for j, st in enumerate(raw_steps, start=1):
        if not isinstance(st, dict):
            return _err("bad_args", f"step #{j} is not an object")
        content = st.get("content")
        if not isinstance(content, str) or not content.strip():
            return _err("bad_args", f"step #{j} is missing content")
        timer = st.get("timer_seconds")
        steps.append({
            "id": str(st.get("id") or f"step-{j}"),
            "title": st.get("title"),
            "content": content,
            "timer_seconds": int(timer) if isinstance(timer, (int, float)) else None,
        })

    return _ok(
        recipe={
            "title": title.strip(),
            "description": args.get("description"),
            "base_servings": base_servings,
            "servings": target_servings,
            "scale": round(scale, 4),
            "ingredients": ingredients,
            "steps": steps,
            "notes": args.get("notes"),
        }
    )


TOOL_REGISTRATIONS = (
    ("recipe_card", RECIPE_SCHEMA, handle_recipe_card, "🍳"),
)
