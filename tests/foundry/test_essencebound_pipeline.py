"""Integration tests for Essencebound dataset artifact construction."""

import json
from pathlib import Path

from foundry.essencebound_world.pipeline import build_data, validate_root
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
