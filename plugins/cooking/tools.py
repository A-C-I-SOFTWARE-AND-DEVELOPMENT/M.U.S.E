"""Four agent-facing cooking / food tools (TheMealDB, TheCocktailDB, OFF).

Uniform envelope ``{"success": bool, ...}``. The only gate is
``cooking.enabled`` — every call is a read-only GET, no API key.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from plugins.cooking import config as cooking_config
from plugins.cooking.client import CookingClient
from tools.http_client import HttpClientError


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


def check_cooking_requirements() -> bool:
    return cooking_config.load_config().enabled


def _enabled_or_error() -> str | None:
    if not cooking_config.load_config().enabled:
        return _err("plugin_disabled", "cooking.enabled is false")
    return None


def _str_arg(args: Dict[str, Any], key: str) -> str | None:
    val = args.get(key)
    if not isinstance(val, str) or not val.strip():
        return None
    return val.strip()


def _ingredients(meal: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i in range(1, 21):
        name = (meal.get(f"strIngredient{i}") or "").strip()
        measure = (meal.get(f"strMeasure{i}") or "").strip()
        if name:
            out.append({"ingredient": name, "measure": measure})
    return out


# ── schemas ──────────────────────────────────────────────────────────────────

RECIPE_SEARCH_SCHEMA: Dict[str, Any] = {
    "name": "recipe_search",
    "description": (
        "Search recipes by name on TheMealDB (free, no key). Returns matching "
        "meals with id, name, category, cuisine, and thumbnail. Use "
        "recipe_lookup with the id for full ingredients and instructions. "
        "Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Dish name, e.g. 'arrabiata'."}
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

RECIPE_LOOKUP_SCHEMA: Dict[str, Any] = {
    "name": "recipe_lookup",
    "description": (
        "Fetch a full recipe by TheMealDB meal id (free, no key): ingredients "
        "with measures, instructions, category, cuisine, and source. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {"id": {"type": "string", "description": "TheMealDB meal id."}},
        "required": ["id"],
        "additionalProperties": False,
    },
}

COCKTAIL_SEARCH_SCHEMA: Dict[str, Any] = {
    "name": "cocktail_search",
    "description": (
        "Search cocktails by name on TheCocktailDB (free, no key). Returns "
        "drinks with name, category, glass, instructions, and ingredients. "
        "Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Drink name, e.g. 'margarita'."}
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

FOOD_PRODUCT_SCHEMA: Dict[str, Any] = {
    "name": "food_product",
    "description": (
        "Look up a packaged food product by barcode on Open Food Facts (free, "
        "no key). Returns product name, brands, Nutri-Score, NOVA group, and "
        "key nutriments per 100g. Read-only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "barcode": {"type": "string", "description": "Product barcode (EAN/UPC)."}
        },
        "required": ["barcode"],
        "additionalProperties": False,
    },
}


# ── handlers ─────────────────────────────────────────────────────────────────


def handle_recipe_search(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    query = _str_arg(args, "query")
    if query is None:
        return _err("bad_args", "query is required")
    try:
        payload = CookingClient().recipe_search(query)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    meals = (payload or {}).get("meals") or []
    results = [
        {
            "id": m.get("idMeal"),
            "name": m.get("strMeal"),
            "category": m.get("strCategory"),
            "area": m.get("strArea"),
            "thumbnail": m.get("strMealThumb"),
        }
        for m in meals
        if isinstance(m, dict)
    ]
    return _ok(meals=results)


def handle_recipe_lookup(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    meal_id = _str_arg(args, "id")
    if meal_id is None:
        return _err("bad_args", "id is required")
    try:
        payload = CookingClient().recipe_lookup(meal_id)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    meals = (payload or {}).get("meals") or []
    if not meals or not isinstance(meals[0], dict):
        return _err("not_found", f"no meal with id {meal_id!r}")
    m = meals[0]
    return _ok(
        meal={
            "id": m.get("idMeal"),
            "name": m.get("strMeal"),
            "category": m.get("strCategory"),
            "area": m.get("strArea"),
            "instructions": m.get("strInstructions"),
            "ingredients": _ingredients(m),
            "thumbnail": m.get("strMealThumb"),
            "source": m.get("strSource") or m.get("strYoutube"),
        }
    )


def handle_cocktail_search(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    query = _str_arg(args, "query")
    if query is None:
        return _err("bad_args", "query is required")
    try:
        payload = CookingClient().cocktail_search(query)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    drinks = (payload or {}).get("drinks") or []
    results = []
    for d in drinks:
        if not isinstance(d, dict):
            continue
        ingredients = []
        for i in range(1, 16):
            name = (d.get(f"strIngredient{i}") or "").strip()
            measure = (d.get(f"strMeasure{i}") or "").strip()
            if name:
                ingredients.append({"ingredient": name, "measure": measure})
        results.append({
            "id": d.get("idDrink"),
            "name": d.get("strDrink"),
            "category": d.get("strCategory"),
            "glass": d.get("strGlass"),
            "alcoholic": d.get("strAlcoholic"),
            "instructions": d.get("strInstructions"),
            "ingredients": ingredients,
        })
    return _ok(drinks=results)


def handle_food_product(args: Dict[str, Any], **_kw) -> str:
    if (disabled := _enabled_or_error()) is not None:
        return disabled
    barcode = _str_arg(args, "barcode")
    if barcode is None or not barcode.isdigit():
        return _err("bad_args", "barcode is required and must be digits")
    try:
        payload = CookingClient().food_product(barcode)
    except HttpClientError as exc:
        return _err(exc.error, exc.message, status=exc.status)
    payload = payload or {}
    if payload.get("status") != 1:
        return _err("not_found", f"no product for barcode {barcode!r}")
    p = payload.get("product") or {}
    nutr = p.get("nutriments") or {}
    return _ok(
        product={
            "name": p.get("product_name"),
            "brands": p.get("brands"),
            "quantity": p.get("quantity"),
            "nutriscore": p.get("nutriscore_grade"),
            "nova_group": p.get("nova_group"),
            "ingredients_text": p.get("ingredients_text"),
            "nutriments_per_100g": {
                "energy_kcal": nutr.get("energy-kcal_100g"),
                "fat": nutr.get("fat_100g"),
                "sugars": nutr.get("sugars_100g"),
                "salt": nutr.get("salt_100g"),
                "proteins": nutr.get("proteins_100g"),
            },
        }
    )


TOOL_REGISTRATIONS = (
    ("recipe_search", RECIPE_SEARCH_SCHEMA, handle_recipe_search, "🍝"),
    ("recipe_lookup", RECIPE_LOOKUP_SCHEMA, handle_recipe_lookup, "🍲"),
    ("cocktail_search", COCKTAIL_SEARCH_SCHEMA, handle_cocktail_search, "🍹"),
    ("food_product", FOOD_PRODUCT_SCHEMA, handle_food_product, "🥫"),
)
