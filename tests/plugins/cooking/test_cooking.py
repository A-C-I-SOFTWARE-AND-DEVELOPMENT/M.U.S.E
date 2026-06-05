"""cooking plugin — registration, gating, handlers (no network)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

import plugins.cooking as plugin_pkg
import plugins.cooking.tools as tools
from plugins.cooking import config as cooking_config
from tools.http_client import HttpClientError


def _parse(result: str):
    return json.loads(result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(
        cooking_config,
        "load_config",
        lambda: cooking_config.CookingConfig(enabled=True),
    )


@pytest.fixture
def mock_client(monkeypatch):
    m = MagicMock()
    instance = MagicMock()
    m.return_value = instance
    monkeypatch.setattr(tools, "CookingClient", m)
    return instance


def test_register_emits_four_tools():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    assert [c["name"] for c in captured] == [
        "recipe_search",
        "recipe_lookup",
        "cocktail_search",
        "food_product",
    ]
    assert all(c["toolset"] == "cooking" for c in captured)


def test_disabled_blocks(monkeypatch, mock_client):
    monkeypatch.setattr(
        cooking_config,
        "load_config",
        lambda: cooking_config.CookingConfig(enabled=False),
    )
    out = _parse(tools.handle_recipe_search({"query": "pasta"}))
    assert out["error"] == "plugin_disabled"
    mock_client.recipe_search.assert_not_called()


def test_recipe_search_slims(enabled, mock_client):
    mock_client.recipe_search.return_value = {
        "meals": [
            {
                "idMeal": "52771",
                "strMeal": "Arrabiata",
                "strCategory": "Vegetarian",
                "strArea": "Italian",
                "strMealThumb": "https://img",
            }
        ]
    }
    out = _parse(tools.handle_recipe_search({"query": "arrabiata"}))
    assert out["meals"][0]["id"] == "52771"
    assert out["meals"][0]["area"] == "Italian"


def test_recipe_lookup_assembles_ingredients(enabled, mock_client):
    meal = {
        "idMeal": "1",
        "strMeal": "Test",
        "strInstructions": "Cook.",
        "strIngredient1": "Pasta",
        "strMeasure1": "200g",
        "strIngredient2": "Salt",
        "strMeasure2": "1 tsp",
        "strIngredient3": "",
        "strMeasure3": "",
    }
    mock_client.recipe_lookup.return_value = {"meals": [meal]}
    out = _parse(tools.handle_recipe_lookup({"id": "1"}))
    assert out["meal"]["ingredients"] == [
        {"ingredient": "Pasta", "measure": "200g"},
        {"ingredient": "Salt", "measure": "1 tsp"},
    ]


def test_recipe_lookup_not_found(enabled, mock_client):
    mock_client.recipe_lookup.return_value = {"meals": None}
    out = _parse(tools.handle_recipe_lookup({"id": "999"}))
    assert out["error"] == "not_found"


def test_cocktail_search_assembles_ingredients(enabled, mock_client):
    mock_client.cocktail_search.return_value = {
        "drinks": [
            {
                "idDrink": "11007",
                "strDrink": "Margarita",
                "strCategory": "Ordinary Drink",
                "strGlass": "Cocktail glass",
                "strAlcoholic": "Alcoholic",
                "strInstructions": "Rub rim with lime.",
                "strIngredient1": "Tequila",
                "strMeasure1": "1 1/2 oz",
            }
        ]
    }
    out = _parse(tools.handle_cocktail_search({"query": "margarita"}))
    assert out["drinks"][0]["ingredients"][0]["ingredient"] == "Tequila"


def test_food_product_status_zero_is_not_found(enabled, mock_client):
    mock_client.food_product.return_value = {"status": 0}
    out = _parse(tools.handle_food_product({"barcode": "0000"}))
    assert out["error"] == "not_found"


def test_food_product_slims(enabled, mock_client):
    mock_client.food_product.return_value = {
        "status": 1,
        "product": {
            "product_name": "Nutella",
            "brands": "Ferrero",
            "nutriscore_grade": "e",
            "nova_group": 4,
            "nutriments": {"energy-kcal_100g": 539, "sugars_100g": 56.3},
        },
    }
    out = _parse(tools.handle_food_product({"barcode": "3017620422003"}))
    assert out["product"]["nutriscore"] == "e"
    assert out["product"]["nutriments_per_100g"]["energy_kcal"] == 539


def test_food_product_rejects_nondigit_barcode(enabled, mock_client):
    out = _parse(tools.handle_food_product({"barcode": "abc"}))
    assert out["error"] == "bad_args"
    mock_client.food_product.assert_not_called()


def test_http_error_envelope(enabled, mock_client):
    mock_client.recipe_search.side_effect = HttpClientError(
        "timeout", "request timed out"
    )
    out = _parse(tools.handle_recipe_search({"query": "x"}))
    assert out["error"] == "timeout"
