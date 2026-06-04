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
        # T4 (the advertised free GPU) has no bf16 — must pick precision by hardware
        assert "bf16=true" not in low
        assert "is_bfloat16_supported" in r.script


def test_dpo_stage_emits_real_dpo_trainer() -> None:
    r = ft.generate_recipe("data/prefs.jsonl", stage=ft.TrainingStage.DPO)
    assert r.stage.value == "dpo"
    assert "DPOTrainer" in r.script and "DPOConfig" in r.script
    assert "ORPO" not in r.script  # not mislabeled ORPO


def test_grpo_recipe_wires_the_gate_reward() -> None:
    r = ft.generate_recipe("data/x.jsonl", stage=ft.TrainingStage.GRPO)
    assert "reward_from_gate_summary" in r.script
    assert "GRPOTrainer" in r.script
    # The recipe points at the wired real-gate reward, not just the stub.
    assert "reward_for_work" in r.script


# --- reward_for_work: the reward wired to the REAL gate machinery ----------


def _gate_packet(prompt: str):
    from hermes_cli.jarvis_prime.natural_language_coder import build_work_packet

    return build_work_packet(prompt).to_gate_packet()


def test_reward_for_work_runs_real_gates() -> None:
    packet = _gate_packet("add retry logic to the gateway module and add tests")
    gr = ft.reward_for_work(packet)
    assert isinstance(gr, ft.GateReward)
    # Calibrated in [0, 1] and derived from a real GateSummary (has results).
    assert 0.0 <= gr.reward <= 1.0
    assert gr.summary.get("results")
    # The graded reward agrees with feeding the same summary to the dict path.
    assert gr.reward == ft.reward_from_gate_summary(gr.summary)
    assert gr.verifiable == ft.verifiable_pass(gr.summary)


def test_reward_for_work_is_deterministic() -> None:
    packet = _gate_packet("add a function to the gateway module")
    assert ft.reward_for_work(packet).reward == ft.reward_for_work(packet).reward


# --- run_free_loop: harvest -> export -> recipe (real local work) ----------


def _make_store(tmp_path):
    from hermes_cli.jarvis_prime.learning_dataset import DatasetStore

    return DatasetStore(path=tmp_path / "dataset.jsonl")


def test_free_loop_empty_store_not_ready_but_emits_recipes(tmp_path) -> None:
    store = _make_store(tmp_path)
    rep = ft.run_free_loop(store=store, dataset_path=tmp_path / "ds.jsonl")
    assert rep.harvested == 0
    assert rep.ready is False
    assert [r.stage.value for r in rep.recipes] == ["sft", "orpo", "grpo"]
    assert all(r.valid_python() for r in rep.recipes)
    assert rep.to_dict()["paid_api"] is False


def test_free_loop_harvests_owner_approved_trace(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from hermes_cli.jarvis_prime import semantic_frontend as sf
    from hermes_cli.jarvis_prime.backend_selector import (
        BackendContext,
        BackendTarget,
    )
    from hermes_cli.jarvis_prime.ir_compilers import get_compiler
    from hermes_cli.jarvis_prime.nlp_training import export_compile_trace

    store = _make_store(tmp_path)
    parse = sf.parse("add a function to the gateway module")
    result = get_compiler(BackendTarget.REPO_WORK_PACKET).compile(
        parse.graph, BackendContext(repo_root=str(tmp_path))
    )
    export_compile_trace(result, parse, store=store, owner_approve=True)

    ds = tmp_path / "ds.jsonl"
    rep = ft.run_free_loop(store=store, dataset_path=ds)
    assert rep.harvested >= 1
    assert rep.ready is True
    assert ds.exists()  # the exported JSONL is real, local work


def test_free_loop_write_dir_emits_scripts(tmp_path) -> None:
    store = _make_store(tmp_path)
    out = tmp_path / "recipes"
    rep = ft.run_free_loop(
        store=store, dataset_path=tmp_path / "ds.jsonl", write_dir=out
    )
    assert rep.written_to == str(out)
    assert (out / "train_sft.py").exists()
    assert (out / "train_grpo.py").exists()


# --- CLI: free-loop + promote ----------------------------------------------


def test_cli_free_loop_json(capsys, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert main(["learning", "free-loop", "--json"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["paid_api"] is False
    assert [r["stage"] for r in rep["recipes"]] == ["sft", "orpo", "grpo"]
    assert rep["ready"] is False  # fresh store has no approved traces


def test_cli_free_loop_stage_filter(capsys, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert main(["learning", "free-loop", "--stage", "sft", "--json"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert [r["stage"] for r in rep["recipes"]] == ["sft"]


def test_cli_promote_no_scorecards_not_eligible(capsys, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    rc = main(["learning", "promote", "--candidate", "openrouter:qwen",
               "--task-class", "coding_build", "--json"])
    assert rc == 1  # not eligible -> nonzero
    out = json.loads(capsys.readouterr().out)
    assert out["eligible"] is False
    assert out["candidate"] == "openrouter:qwen"
    assert out["task_class"] == "coding_build"


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


def test_cli_write_plus_json_keeps_stdout_pure_json(capsys, tmp_path) -> None:
    rc = main(["learning", "free-recipe", "data/x.jsonl", "--stage", "sft",
               "--json", "--write", str(tmp_path)])
    assert rc == 0
    captured = capsys.readouterr()
    # stdout must be parseable JSON; the "wrote ..." status goes to stderr.
    json.loads(captured.out)
    assert "wrote" in captured.err
    assert (tmp_path / "train_sft.py").exists()
