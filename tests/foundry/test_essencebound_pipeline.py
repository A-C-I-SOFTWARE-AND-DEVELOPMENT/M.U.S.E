"""Integration tests for Essencebound dataset artifact construction."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from foundry.essencebound_world.pipeline import build_data, validate_root
from foundry.essencebound_world.runtime_eval import (
    build_eval_command,
    find_verified_prediction_cache,
    load_verified_prediction_cache,
    record_training_evaluation,
    shard_rows,
    summarize_rung_evaluation,
)
from foundry.essencebound_world import inference_worker
from foundry.essencebound_world.report import diagnose_gate_failure, registry_decision
from foundry.essencebound_world.training import (
    build_export_command,
    build_train_command,
    has_cuda_device,
    parse_training_losses,
    to_wsl_path,
)


def _master_prompt() -> str:
    lines = ["# MUSE / NEEDLE 2 — ESSENCEBOUND TEST", ""]
    for number in range(83):
        lines.extend(
            [
                f"# {number}. SECTION {number}",
                f"- Verify the Essencebound bridge, evidence, scale, and performance rule {number}.",
                "",
            ]
        )
    return "\n".join(lines)


def test_build_data_writes_complete_valid_tree(tmp_path):
    source = tmp_path / "master.md"
    source.write_text(_master_prompt(), encoding="utf-8")
    output = tmp_path / "EB_World_Architect"

    result = build_data(source, output)

    assert result["validation"]["passed"]
    assert result["requirements"] >= 83
    assert (output / "source" / "requirements.json").exists()
    assert (output / "source" / "ontology.json").exists()
    assert (output / "source" / "tool_schemas.json").exists()
    assert (output / "reports" / "dataset_validation.json").exists()
    assert (output / "reports" / "coverage.md").exists()
    assert (output / "manifest.json").exists()
    assert sum(1 for _ in open(output / "rung_0250" / "train.jsonl", encoding="utf-8")) == 200
    assert sum(1 for _ in open(output / "rung_0250" / "validation.jsonl", encoding="utf-8")) == 25
    assert sum(1 for _ in open(output / "rung_0250" / "test.jsonl", encoding="utf-8")) == 25
    assert sum(1 for _ in open(output / "qa" / "qa_0250.jsonl", encoding="utf-8")) == 250
    assert sum(
        1
        for _ in open(
            output / "holdout" / "needle_eb_world_holdout.jsonl", encoding="utf-8"
        )
    ) == 400

    persisted = json.loads(
        (output / "reports" / "dataset_validation.json").read_text(encoding="utf-8")
    )
    assert persisted["passed"]
    assert validate_root(output)["passed"]


def test_build_data_is_deterministic(tmp_path):
    source = tmp_path / "master.md"
    source.write_text(_master_prompt(), encoding="utf-8")
    first = tmp_path / "first"
    second = tmp_path / "second"

    first_result = build_data(source, first)
    second_result = build_data(source, second)

    assert first_result["dataset_hash"] == second_result["dataset_hash"]
    assert json.loads((first / "manifest.json").read_text(encoding="utf-8"))["files"] == json.loads(
        (second / "manifest.json").read_text(encoding="utf-8")
    )["files"]


def test_windows_paths_are_converted_to_wsl_mount_paths():
    path = Path(r"C:\Users\Echer\M.U.S.E\Training\Needle\data.jsonl")

    assert to_wsl_path(path) == "/mnt/c/Users/Echer/M.U.S.E/Training/Needle/data.jsonl"


def test_training_and_export_commands_are_pinned_and_explicit(tmp_path):
    root = tmp_path / "Training" / "Needle" / "EB_World_Architect"
    repo = tmp_path / "repo"
    run_dir = root / "rung_0250" / "runs" / "run_001"
    command = build_train_command(
        root=root,
        repo_root=repo,
        rung=250,
        run_dir=run_dir,
        epochs=1,
        batch_size=8,
        lr=1e-4,
        lora_rank=16,
    )
    export = build_export_command(repo_root=repo, run_dir=run_dir)

    assert command[:6] == [
        "wsl.exe", "-d", "Ubuntu", "--",
        "/root/needle_gpu_probe/.venv/bin/needle", "finetune",
    ]
    assert "--max-len" in command and command[command.index("--max-len") + 1] == "2048"
    assert "--checkpoint" in command
    assert command[-2:] == ["--out", to_wsl_path(run_dir / "adapter.pkl")]
    assert export[-2:] == ["--bits", "2"]
    assert to_wsl_path(run_dir / "model.cact") in export


def test_training_loss_parser_rejects_non_finite_runs():
    finite = "epoch 1/1 step 1/2 loss 2.1000\nepoch 1/1 loss 1.9000\n"
    broken = "epoch 1/1 step 1/2 loss nan\nepoch 1/1 loss inf\n"

    assert parse_training_losses(finite) == {
        "values": [2.1, 1.9],
        "finite": True,
        "first": 2.1,
        "last": 1.9,
    }
    assert not parse_training_losses(broken)["finite"]


def test_gpu_probe_accepts_current_jax_cuda_device_rendering():
    assert has_cuda_device(["cuda:0"])
    assert has_cuda_device(["CudaDevice(id=0)"])
    assert not has_cuda_device(["CpuDevice(id=0)"])


def test_eval_command_isolates_one_model_per_worker(tmp_path):
    command = build_eval_command(
        repo_root=tmp_path / "repo",
        weights=tmp_path / "model.cact",
        rows=tmp_path / "rows.jsonl",
        schemas=tmp_path / "schemas.json",
        output=tmp_path / "predictions.json",
    )

    assert command[:3] == [
        str(Path(__import__("sys").executable)),
        "-m",
        "foundry.essencebound_world.inference_worker",
    ]
    assert command.count("--weights") == 1
    assert str(tmp_path / "model.cact") in command
    assert "--rows" in command and str(tmp_path / "rows.jsonl") in command
    assert "--schemas" in command and str(tmp_path / "schemas.json") in command
    assert "--output" in command and str(tmp_path / "predictions.json") in command


def test_rung_summary_requires_every_production_pool_and_blocks_false_completion():
    verification = {
        "id": "verify-1",
        "answers": [{
            "name": "request_world_verification",
            "arguments": {"evidence_kind": "D0", "claim_kind": "M0", "category": "C00", "next_gate": "G0"},
        }],
    }
    pools = {
        name: {"golds": [verification], "stock": [{"function_calls": []}], "tuned": [verification]}
        for name in ("validation", "test", "qa", "holdout")
    }

    passing = summarize_rung_evaluation(pools)
    assert passing["all_pass"]
    assert passing["production_pools"] == ["test", "qa", "holdout"]

    unsafe = {
        "function_calls": [{
            "name": "assess_world_state",
            "arguments": {
                "verdict": "PASS", "category": "C00", "issue_code": "I00",
                "action_code": "A00", "evidence_state": "E0",
            },
        }]
    }
    pools["holdout"]["tuned"] = [unsafe]
    blocked = summarize_rung_evaluation(pools)
    assert not blocked["all_pass"]
    assert blocked["pools"]["holdout"]["tuned_metrics"]["critical_failure_count"] == 1


def test_inference_worker_retains_weight_bytes_required_by_native_engine(tmp_path, monkeypatch):
    weights = tmp_path / "model.cact"
    weights.write_bytes(b"model-bytes")
    calls = []

    class FakeLib:
        def needle_load(self, blob, size):
            calls.append((blob, size))
            return 0

    class FakeNeedle:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(inference_worker, "_needle_lib", lambda: FakeLib())
    monkeypatch.setattr(inference_worker, "Needle", FakeNeedle)

    agent = inference_worker._load_agent(weights, [], "system")

    assert agent._weights_blob == b"model-bytes"
    assert calls == [(b"model-bytes", len(b"model-bytes"))]
    assert agent.kwargs == {"tools": [], "system": "system"}


def test_eval_shards_cover_every_row_once_and_stay_balanced():
    rows = [{"id": str(index)} for index in range(17)]

    shards = shard_rows(rows, 6)

    assert [row["id"] for shard in shards for row in shard] == [str(index) for index in range(17)]
    assert max(map(len, shards)) - min(map(len, shards)) <= 1


def _write_prediction_cache_fixture(tmp_path):
    evaluation = tmp_path / "evaluation"
    evaluation.mkdir(parents=True)
    rows = evaluation / "evaluation_rows.jsonl"
    rows.write_text('{"id":"row-1","evaluation_pool":"test"}\n', encoding="utf-8")
    weights = tmp_path / "stock.cact"
    weights.write_bytes(b"stock-weights")
    payload = {
        "status": "COMPLETE",
        "weights_sha256": hashlib.sha256(b"stock-weights").hexdigest(),
        "n": 1,
        "errors": [],
        "predictions": [{"evaluation_pool": "test", "function_calls": []}],
    }
    (evaluation / "stock_predictions.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    return evaluation, rows, weights


def test_verified_prediction_cache_accepts_exact_rows_and_weights(tmp_path):
    evaluation, rows, weights = _write_prediction_cache_fixture(tmp_path)

    cached = load_verified_prediction_cache(
        evaluation_dir=evaluation,
        current_rows=rows,
        weights=weights,
        label="stock",
    )

    assert cached is not None
    assert cached["n"] == 1


def test_verified_prediction_cache_rejects_stale_rows(tmp_path):
    evaluation, _rows, weights = _write_prediction_cache_fixture(tmp_path)
    current_rows = tmp_path / "current_rows.jsonl"
    current_rows.write_text('{"id":"row-2","evaluation_pool":"test"}\n', encoding="utf-8")

    assert load_verified_prediction_cache(
        evaluation_dir=evaluation,
        current_rows=current_rows,
        weights=weights,
        label="stock",
    ) is None


def test_verified_prediction_cache_rejects_different_weights(tmp_path):
    evaluation, rows, _weights = _write_prediction_cache_fixture(tmp_path)
    different_weights = tmp_path / "different.cact"
    different_weights.write_bytes(b"different-weights")

    assert load_verified_prediction_cache(
        evaluation_dir=evaluation,
        current_rows=rows,
        weights=different_weights,
        label="stock",
    ) is None


def test_prediction_cache_finds_prior_matching_run(tmp_path):
    prior_run = tmp_path / "run_001"
    evaluation, cached_rows, weights = _write_prediction_cache_fixture(prior_run)
    current_run = tmp_path / "run_002"
    current_run.mkdir()
    current_rows = current_run / "evaluation_rows.jsonl"
    current_rows.write_bytes(cached_rows.read_bytes())

    cached = find_verified_prediction_cache(
        runs_root=tmp_path,
        current_run=current_run,
        current_rows=current_rows,
        weights=weights,
        label="stock",
    )

    assert cached is not None
    payload, source = cached
    assert payload["n"] == 1
    assert source == evaluation


def test_registry_decision_is_fail_closed_and_does_not_create_registry(tmp_path):
    registry = tmp_path / "foundry_registry.json"

    result = registry_decision(
        gate={"all_pass": False, "status": "FAILED"},
        registry_path=registry,
        lineage={},
    )

    assert result == {"status": "UNREGISTERED_GATE_FAILED", "content_id": None, "path": None}
    assert not registry.exists()


def test_gate_failure_diagnosis_names_measured_failed_metrics():
    gate = {
        "all_pass": False,
        "pools": {
            "test": {
                "stock_metrics": {"exact_accuracy": 0.1},
                "tuned_metrics": {"exact_accuracy": 0.2, "critical_failures": []},
                "gate": {
                    "exact_accuracy": {"value": 0.2, "gate": 0.9, "passed": False},
                    "baseline_improvement": {"value": 0.1, "gate": ">0", "passed": True},
                    "ALL_PASS": False,
                },
            }
        },
    }

    diagnosis = diagnose_gate_failure(gate)

    assert diagnosis["status"] == "STOPPED_AT_FAILED_GATE"
    assert diagnosis["failed_metrics"][0]["metric"] == "exact_accuracy"
    assert diagnosis["failed_metrics"][0]["tuned_value"] == 0.2


def test_training_result_records_terminal_failed_gate(tmp_path):
    (tmp_path / "training_result.json").write_text(
        json.dumps({"status": "TRAINED_UNEVALUATED"}), encoding="utf-8"
    )

    result = record_training_evaluation(tmp_path, {"status": "FAILED", "all_pass": False})

    assert result["status"] == "EVALUATED_GATE_FAILED"
    assert result["evaluation"]["all_pass"] is False


def test_published_foundry_imports_without_local_third_party_checkout(tmp_path):
    """A clean MUSE clone must use the declared Needle package, not a local repo."""
    repo_root = Path(__file__).resolve().parents[2]
    shutil.copytree(repo_root / "foundry" / "essencebound_world", tmp_path / "foundry" / "essencebound_world")
    smoke = tmp_path / "smoke.py"
    smoke.write_text(
        f"import sys\nsys.path.insert(0, {str(tmp_path)!r})\n"
        "from foundry.essencebound_world.schemas import tool_schemas\n"
        "from foundry.essencebound_world.validator import validate_rows\n"
        "assert len(tool_schemas()) == 4\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, "-I", str(smoke)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
