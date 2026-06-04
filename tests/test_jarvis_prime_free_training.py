"""Tests for the free, continuous, gated training module.

Covers the verifiable gate reward (the RLVR signal), recipe generation
(runnable, paid-API-free), and the CLI surface. No GPU / network needed.
"""

from __future__ import annotations

import ast
import json

from hermes_cli.jarvis_prime import free_training as ft
from hermes_cli.jarvis_prime.__main__ import main


def _summary(**outcomes) -> dict:
    return {
        "results": [{"name": n, "outcome": o} for n, o in outcomes.items()],
        "overall": "fail" if "fail" in outcomes.values() else "pass",
    }


def test_reward_bounds_and_extremes() -> None:
    all_pass = _summary(**{n: "pass" for n in ft.GATE_WEIGHTS})
    all_fail = _summary(**{n: "fail" for n in ft.GATE_WEIGHTS})
    assert ft.reward_from_gate_summary(all_pass) == 1.0
    assert ft.reward_from_gate_summary(all_fail) == 0.0
    assert ft.reward_from_gate_summary({"results": []}) == 0.0


def test_reward_is_monotonic_in_passes() -> None:
    one = ft.reward_from_gate_summary(_summary(test="pass", build="fail"))
    two = ft.reward_from_gate_summary(_summary(test="pass", build="pass"))
    assert 0.0 < one < two <= 1.0


def test_verifiable_pass_strict() -> None:
    assert ft.verifiable_pass(_summary(test="pass", security="pass")) is True
    assert ft.verifiable_pass(_summary(test="fail", security="pass")) is False
    # no pass at all -> not a verified success
    assert ft.verifiable_pass({"results": [{"name": "test", "outcome": "skipped"}]}) is False


def test_reward_components_use_weights() -> None:
    comps = ft.reward_components(_summary(test="pass", build="pass"))
    assert comps["test"] == ft.GATE_WEIGHTS["test"]
    assert comps["build"] == ft.GATE_WEIGHTS["build"]


def test_every_stage_recipe_is_valid_python_and_free() -> None:
    for stage in ft.TrainingStage:
        r = ft.generate_recipe("data/x.jsonl", stage=stage)
        ast.parse(r.script)  # raises on syntax error
        assert r.valid_python()
        assert r.config["paid_api"] is False
        low = r.script.lower()
        # no paid-provider dispatch in a "free" recipe
        assert "together" not in low
        assert "openai" not in low
        assert "unsloth" in low and "trl" in low


def test_grpo_recipe_wires_the_gate_reward() -> None:
    r = ft.generate_recipe("data/x.jsonl", stage=ft.TrainingStage.GRPO)
    assert "reward_from_gate_summary" in r.script
    assert "GRPOTrainer" in r.script


def test_recipe_write(tmp_path) -> None:
    r = ft.generate_recipe("data/x.jsonl", stage=ft.TrainingStage.SFT)
    path = r.write(tmp_path)
    assert path.exists() and path.name == "train_sft.py"
    assert (tmp_path / "recipe_sft.json").exists()


def test_plan_is_free_and_gated() -> None:
    d = ft.FreeContinuousPlan().to_dict()
    assert d["paid_api"] is False
    assert d["reward"] == "hermes-verification-gates"
    assert "sft" in d["stages"] and "grpo" in d["stages"]


def test_cli_free_plan_and_recipe(capsys) -> None:
    assert main(["learning", "free-plan", "--json"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["paid_api"] is False

    assert main(["learning", "free-recipe", "data/x.jsonl",
                 "--stage", "grpo", "--json"]) == 0
    recipe = json.loads(capsys.readouterr().out)
    assert recipe["stage"] == "grpo" and recipe["script_valid_python"] is True
