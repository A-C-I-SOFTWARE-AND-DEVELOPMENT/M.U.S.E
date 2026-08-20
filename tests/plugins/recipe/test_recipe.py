"""recipe plugin — registration, gating, and pure recipe_card behaviour."""

from __future__ import annotations

import json

import pytest

import plugins.recipe as plugin_pkg
import plugins.recipe.tools as tools
import plugins.recipe.config as recipe_config


def _parse(result: str):
    return json.loads(result)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(
        recipe_config, "load_config", lambda: recipe_config.RecipeConfig(enabled=True)
    )


@pytest.fixture
def disabled(monkeypatch):
    monkeypatch.setattr(
        recipe_config, "load_config", lambda: recipe_config.RecipeConfig(enabled=False)
    )


def _base_args(**over):
    args = {
        "title": "Test Soup",
        "ingredients": [
            {"name": "water", "amount": 2, "unit": "cup"},
            {"name": "garlic cloves", "amount": 3},
        ],
        "steps": [
            {"title": "Boil", "content": "Boil the water", "timer_seconds": 300},
            {"content": "Add garlic"},
        ],
    }
    args.update(over)
    return args


def test_register_emits_one_tool():
    captured = []

    class _Ctx:
        def register_tool(self, **kw):
            captured.append(kw)

    plugin_pkg.register(_Ctx())
    assert [c["name"] for c in captured] == ["recipe_card"]
    assert captured[0]["toolset"] == "recipe"


def test_check_fn_enabled(enabled):
    assert tools.check_recipe_requirements() is True


def test_check_fn_disabled(disabled):
    assert tools.check_recipe_requirements() is False


def test_blocked_when_disabled(disabled):
    assert _parse(tools.handle_recipe_card(_base_args()))["error"] == "plugin_disabled"


def test_default_servings_no_scaling(enabled):
    out = _parse(tools.handle_recipe_card(_base_args()))
    assert out["success"] is True
    r = out["recipe"]
    assert r["base_servings"] == 4 and r["servings"] == 4 and r["scale"] == 1.0
    assert r["ingredients"][0] == {"id": "0001", "name": "water", "amount": 2.0, "unit": "cup"}
    # countable item keeps unit None and auto-id
    assert r["ingredients"][1]["id"] == "0002" and r["ingredients"][1]["unit"] is None
    # steps get ids + timer normalized
    assert r["steps"][0]["id"] == "step-1" and r["steps"][0]["timer_seconds"] == 300
    assert r["steps"][1]["timer_seconds"] is None


def test_scaling_doubles_amounts(enabled):
    out = _parse(tools.handle_recipe_card(_base_args(base_servings=4, servings=8)))
    r = out["recipe"]
    assert r["scale"] == 2.0
    assert r["ingredients"][0]["amount"] == 4.0
    assert r["ingredients"][1]["amount"] == 6.0


def test_invalid_unit_rejected(enabled):
    args = _base_args(ingredients=[{"name": "flour", "amount": 1, "unit": "smidgen"}])
    assert _parse(tools.handle_recipe_card(args))["error"] == "bad_args"


def test_missing_amount_rejected(enabled):
    args = _base_args(ingredients=[{"name": "salt"}])
    out = _parse(tools.handle_recipe_card(args))
    assert out["error"] == "bad_args"
    assert "amount" in out["message"]


def test_missing_title_and_empty_lists_rejected(enabled):
    assert _parse(tools.handle_recipe_card(_base_args(title="  ")))["error"] == "bad_args"
    assert _parse(tools.handle_recipe_card(_base_args(ingredients=[])))["error"] == "bad_args"
    assert _parse(tools.handle_recipe_card(_base_args(steps=[])))["error"] == "bad_args"


def test_custom_ids_preserved(enabled):
    args = _base_args(
        ingredients=[{"id": "w", "name": "water", "amount": 1, "unit": "l"}],
        steps=[{"id": "s1", "content": "do it"}],
    )
    r = _parse(tools.handle_recipe_card(args))["recipe"]
    assert r["ingredients"][0]["id"] == "w"
    assert r["steps"][0]["id"] == "s1"
