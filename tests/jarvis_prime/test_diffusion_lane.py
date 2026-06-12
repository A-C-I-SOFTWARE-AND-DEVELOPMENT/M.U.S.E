"""Tests for the isolated Phase-5 diffusion lane."""

from __future__ import annotations

import re
from pathlib import Path

from hermes_cli.jarvis_prime.bench.diffusion_lane import (
    build_infill_prompt,
    comparison_table,
    run_diffusion_probe,
)

JP_ROOT = Path(__file__).resolve().parents[2] / "hermes_cli" / "jarvis_prime"


def test_unavailable_when_binary_missing() -> None:
    report = run_diffusion_probe(
        model_path="/nonexistent.gguf", prompts=["x"], which=lambda name: None
    )
    assert report == {"available": False, "reason": "llama-diffusion-cli not on PATH"}


def test_unavailable_when_model_missing(tmp_path: Path) -> None:
    report = run_diffusion_probe(
        model_path=str(tmp_path / "missing.gguf"),
        prompts=["x"],
        which=lambda name: "/usr/bin/fake",
    )
    assert report["available"] is False
    assert "model not found" in report["reason"]


def test_probe_sweeps_steps_with_injected_runner(tmp_path: Path) -> None:
    model = tmp_path / "fake.gguf"
    model.write_bytes(b"gguf")
    calls: list[list[str]] = []

    def fake_runner(cmd: list[str], timeout: float) -> str:
        calls.append(cmd)
        return "denoised output"

    report = run_diffusion_probe(
        model_path=str(model),
        prompts=["p1", "p2"],
        steps_sweep=(64, 128),
        block_length=32,
        cli_runner=fake_runner,
        which=lambda name: "/usr/bin/fake",
    )
    assert report["available"] is True
    assert [s["steps"] for s in report["sweeps"]] == [64, 128]
    assert len(calls) == 4  # 2 steps x 2 prompts
    assert all("--diffusion-block-length" in c for c in calls)
    steps_args = {c[c.index("--diffusion-steps") + 1] for c in calls}
    assert steps_args == {"64", "128"}


def test_infill_prompt_clamps_scaffold_literals() -> None:
    prompt = build_infill_prompt("task", ["# Reasoning: ", ".\nanswer: ", "\n"])
    assert "# Reasoning: ____.\nanswer: ____\n" in prompt


def test_comparison_table_handles_both_availability_states() -> None:
    table = comparison_table({"available": False, "reason": "no model"}, 0.5)
    assert "unavailable (no model)" in table
    table = comparison_table(
        {"available": True, "sweeps": [{"steps": 64, "mean_latency_s": 1.0, "outputs": []}]},
        0.5,
    )
    assert "| diffusion | 64 | 1.000 | 2.00x slower |" in table


def test_lane_is_never_imported_by_runtime_modules() -> None:
    """Isolation gate: no module outside bench/ may import diffusion_lane."""

    pattern = re.compile(r"diffusion_lane")
    offenders = []
    for py in JP_ROOT.rglob("*.py"):
        if py.parent.name == "bench" or "__pycache__" in py.parts:
            continue
        if pattern.search(py.read_text(encoding="utf-8")):
            offenders.append(str(py))
    assert offenders == []
