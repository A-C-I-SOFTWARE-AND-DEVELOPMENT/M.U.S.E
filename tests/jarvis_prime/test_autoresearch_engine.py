"""Tests for the governed autoresearch experiment driver (fakes only, no GPU)."""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Optional, Sequence

import pytest

from hermes_cli.jarvis_prime.research_fabric.autoresearch.engine import (
    AutoresearchRun,
    EditContext,
    ExperimentConfig,
    ExperimentEdit,
    bpb_gate_score,
    gate_margin_for_bpb_delta,
    parse_summary,
    run_experiment_loop,
    summarize_idea_classes,
)
from hermes_cli.jarvis_prime.research_fabric.autoresearch.platform import (
    DeviceProfile,
    H100_BF16_PEAK_FLOPS,
    default_vram_budget_mb,
    honest_mfu,
)

SUMMARY = """\
some training noise
---
val_bpb:          0.997900
training_seconds: 300.1
total_seconds:    325.9
peak_vram_mb:     45060.2
mfu_percent:      39.80
total_tokens_M:   499.6
num_steps:        953
num_params_M:     50.3
depth:            8
"""


class _Completed:
    def __init__(self, stdout: str, returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


class FakeGit:
    """Records git calls; emulates rev-parse / reset enough for the driver."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.commits = 0

    def __call__(self, args: Sequence[str], cwd: str) -> _Completed:
        args = list(args)
        self.calls.append(args)
        if "commit" in args:
            self.commits += 1
        if args[:2] == ["rev-parse", "--short=7"]:
            return _Completed(f"c{self.commits:06d}")
        return _Completed("")

    def resets(self) -> int:
        return sum(1 for c in self.calls if c and c[0] == "reset")


def _scripted_runner(outputs: list):
    """Each call pops the next scripted output: a summary string, an Exception
    instance to raise, or a plain non-summary string (crash)."""

    def runner(argv, *, cwd, timeout, env=None):
        item = outputs.pop(0)
        if isinstance(item, Exception):
            raise item
        return _Completed(item)

    return runner


def _summary(bpb: float, vram_mb: float = 9000.0) -> str:
    return SUMMARY.replace("0.997900", f"{bpb:.6f}").replace("45060.2", f"{vram_mb:.1f}")


def _edits(*descriptions: str):
    items = list(descriptions)

    def provider(ctx: EditContext) -> Optional[ExperimentEdit]:
        if not items:
            return None
        desc = items.pop(0)
        return ExperimentEdit(description=desc, train_py=f"# {desc}\n")

    return provider


def _config(tmp_path: Path, **overrides) -> ExperimentConfig:
    defaults = dict(
        tag="t1",
        workspace_dir=str(tmp_path / "ws"),
        max_experiments=10,
        vram_budget_mb=12000.0,
        watchdog_seconds=600.0,
    )
    defaults.update(overrides)
    return ExperimentConfig(**defaults)


def _run(config: ExperimentConfig, outputs: list, provider) -> tuple[AutoresearchRun, FakeGit]:
    git = FakeGit()
    run = run_experiment_loop(
        config,
        propose_edit=provider,
        subprocess_runner=_scripted_runner(outputs),
        git_runner=git,
    )
    return run, git


def test_parse_summary_verbatim_block_and_crash() -> None:
    parsed = parse_summary(SUMMARY)
    assert parsed is not None
    assert parsed["val_bpb"] == pytest.approx(0.9979)
    assert parsed["peak_vram_mb"] == pytest.approx(45060.2)
    assert parsed["depth"] == 8
    assert parse_summary("Traceback (most recent call last):\nBoom\n") is None
    assert parse_summary("") is None


def test_bpb_gate_score_monotone_decreasing_in_unit_interval() -> None:
    values = [0.0, 0.5, 0.9, 1.0, 1.5, 10.0]
    scores = [bpb_gate_score(v) for v in values]
    assert all(0.0 < s <= 1.0 for s in scores)
    assert scores == sorted(scores, reverse=True)  # lower bpb => higher score
    assert bpb_gate_score(0.9) > bpb_gate_score(1.0)
    # margin transform: improving by delta must clear exactly that margin
    margin = gate_margin_for_bpb_delta(1.0, 0.05)
    assert bpb_gate_score(0.95) - bpb_gate_score(1.0) == pytest.approx(margin)
    assert gate_margin_for_bpb_delta(1.0, 0.0) == 0.0


def test_keep_and_reset_follow_program_md(tmp_path: Path) -> None:
    # baseline 1.0 -> improve 0.99 (keep) -> worse 0.995 (discard+reset)
    run, git = _run(
        _config(tmp_path),
        [_summary(1.0), _summary(0.99), _summary(0.995)],
        _edits("lower lr", "wider mlp"),
    )
    statuses = [r.status for r in run.results]
    assert statuses == ["keep", "keep", "discard"]
    assert run.baseline is not None and run.baseline.val_bpb == pytest.approx(1.0)
    assert run.champion is not None and run.champion.val_bpb == pytest.approx(0.99)
    assert git.resets() == 1  # only the discard resets
    assert run.stopped_reason == "edit_provider_exhausted"


def test_crash_records_log_tail_and_flywheel_failure(tmp_path: Path, monkeypatch) -> None:
    run, _ = _run(
        _config(tmp_path),
        [_summary(1.0), "Traceback (most recent call last):\nValueError: boom\n"],
        _edits("broken idea"),
    )
    crash = run.results[1]
    assert crash.status == "crash"
    assert "ValueError: boom" in crash.log_tail
    assert crash.val_bpb is None
    # flywheel failure auto-queued (hermetic HERMES_HOME from conftest)
    import os

    queue = Path(os.environ["HERMES_HOME"]) / "flywheel" / "improvement_queue.jsonl"
    assert queue.exists()
    entries = [json.loads(line) for line in queue.read_text(encoding="utf-8").splitlines()]
    assert any("broken idea" in e["summary"] for e in entries)


def test_watchdog_timeout_kills_and_records_failure(tmp_path: Path) -> None:
    timeout_exc = subprocess.TimeoutExpired(cmd="uv run train.py", timeout=600)
    run, git = _run(
        _config(tmp_path),
        [_summary(1.0), timeout_exc],
        _edits("hangs forever"),
    )
    killed = run.results[1]
    assert killed.status == "killed"
    assert "watchdog" in killed.reason
    assert git.resets() == 1  # killed edit is reverted


def test_infeasible_vram_never_becomes_champion(tmp_path: Path) -> None:
    # The bpb winner blows the 12GB budget; the modest improver is champion.
    run, git = _run(
        _config(tmp_path),
        [_summary(1.0), _summary(0.90, vram_mb=13000.0), _summary(0.98)],
        _edits("huge model wins bpb", "modest improvement"),
    )
    assert [r.status for r in run.results] == ["keep", "infeasible", "keep"]
    assert run.champion is not None and run.champion.val_bpb == pytest.approx(0.98)
    assert run.best_infeasible is not None
    assert run.best_infeasible.val_bpb == pytest.approx(0.90)
    assert "VRAM" in run.best_infeasible.reason
    assert git.resets() == 1


def test_max_experiments_ceiling(tmp_path: Path) -> None:
    run, _ = _run(
        _config(tmp_path, max_experiments=2),
        [_summary(1.0), _summary(0.99), _summary(0.98)],
        _edits("a", "b", "c"),
    )
    assert len(run.results) == 2
    assert run.stopped_reason == "max_experiments"


def test_wall_clock_ceiling_with_fake_clock(tmp_path: Path) -> None:
    ticks = iter(float(i) * 100.0 for i in range(100))
    git = FakeGit()
    run = run_experiment_loop(
        _config(tmp_path, max_wall_clock_seconds=250.0),
        propose_edit=_edits("a", "b", "c", "d"),
        subprocess_runner=_scripted_runner([_summary(1.0)] * 5),
        git_runner=git,
        clock=lambda: next(ticks),
    )
    assert run.stopped_reason == "wall_clock"
    assert len(run.results) < 5


def test_cost_ceiling(tmp_path: Path) -> None:
    # Fake clock advances 50s per call => 50s/experiment; at $72/h that is
    # $1/experiment, so a $2 ceiling stops the loop after 2 experiments.
    ticks = iter(float(i) * 50.0 for i in range(100))
    git = FakeGit()
    run = run_experiment_loop(
        _config(
            tmp_path,
            max_cost_usd=2.0,
            cost_per_hour_usd=72.0,
            max_wall_clock_seconds=1e9,
        ),
        propose_edit=_edits("a", "b", "c", "d"),
        subprocess_runner=_scripted_runner([_summary(1.0)] * 5),
        git_runner=git,
        clock=lambda: next(ticks),
    )
    assert run.stopped_reason == "cost_ceiling"
    assert run.total_cost_usd >= 2.0
    assert len(run.results) == 2


def test_results_tsv_mirror_format(tmp_path: Path) -> None:
    run, _ = _run(
        _config(tmp_path),
        [_summary(1.0), "no summary here"],
        _edits("crashy"),
    )
    lines = Path(run.results_tsv_path).read_text(encoding="utf-8").splitlines()
    assert lines[0] == "commit\tval_bpb\tmemory_gb\tstatus\tdescription"
    assert len(lines) == 3
    baseline_row = lines[1].split("\t")
    assert baseline_row[1] == "1.000000"
    assert baseline_row[3] == "keep"
    crash_row = lines[2].split("\t")
    assert crash_row[1] == "0.000000" and crash_row[2] == "0.0" and crash_row[3] == "crash"


def test_workspace_seeded_from_vendor_payload(tmp_path: Path) -> None:
    run, git = _run(_config(tmp_path), [_summary(1.0)], _edits())
    ws = Path(run.workspace_path)
    for name in ("prepare.py", "train.py", "program.md", "pyproject.toml"):
        assert (ws / name).exists()
    # Branch created per program.md naming.
    assert ["checkout", "--quiet", "-b", "autoresearch/t1"] in git.calls


def test_provided_baseline_skips_experiment_zero(tmp_path: Path) -> None:
    run, _ = _run(
        _config(tmp_path, baseline_bpb=1.0),
        [_summary(0.99)],
        _edits("first idea"),
    )
    assert run.baseline is None
    assert run.results[0].description == "first idea"
    assert run.champion is not None and run.champion.val_bpb == pytest.approx(0.99)


def test_honest_mfu_renormalization_and_vram_budget() -> None:
    profile = DeviceProfile(
        name="NVIDIA GeForce RTX 5070",
        capability=(12, 0),
        total_vram_mb=12288.0,
        peak_bf16_flops=61.7e12,
        fa3_repo="kernels-community/flash-attn3",
    )
    honest = honest_mfu(2.0, profile)
    assert honest == pytest.approx(2.0 * H100_BF16_PEAK_FLOPS / 61.7e12)
    assert honest_mfu(2.0, None) is None
    unknown = DeviceProfile("Mystery GPU", (8, 9), 8192.0, None, "kernels-community/flash-attn3")
    assert honest_mfu(2.0, unknown) is None
    assert default_vram_budget_mb(profile) == pytest.approx(12288.0 * 0.9)
    assert default_vram_budget_mb(None) == 0.0


def test_summarize_idea_classes_digest(tmp_path: Path) -> None:
    run, _ = _run(
        _config(tmp_path),
        [_summary(1.0), _summary(0.99), _summary(1.5), "boom"],
        _edits("raise lr", "gelu", "wild idea"),
    )
    digest = summarize_idea_classes(run.results)
    assert "raise lr" in digest.split("discarded:")[0]  # kept section
    assert "gelu" in digest.split("discarded:")[1]
    assert "wild idea (crash)" in digest
    assert math.isfinite(run.total_cost_usd)
