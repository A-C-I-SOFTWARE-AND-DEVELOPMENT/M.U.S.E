"""Unit tests for the Claude Code worker adapter.

Covers the four behaviours called out in Phase 10:

  * absent-command detection,
  * prompt generation,
  * handoff status, and
  * artifact collection.

Each test stays hermetic — no real ``claude`` binary is invoked. The
``runner`` hook on :func:`detect` / :func:`run_claude_cli` is used to
inject fake ``subprocess.run`` callables so we can exercise version-
probe edge cases without touching the host.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest

from hermes_cli.workers import claude_code as cc


# ── helpers ───────────────────────────────────────────────────────────────


class _FakeProc:
    def __init__(
        self,
        *,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _runner_returning(
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
):
    def run(*_args, **_kwargs):
        return _FakeProc(returncode=returncode, stdout=stdout, stderr=stderr)

    return run


def _runner_raising(exc: BaseException):
    def run(*_args, **_kwargs):
        raise exc

    return run


def _sample_task(**overrides: object) -> cc.WorkerTask:
    base: dict[str, object] = {
        "mission": "Audit the kanban swarm scheduler for safety regressions.",
        "repo_evidence": [
            "hermes_cli/kanban_swarm.py:80-220",
            "tests/test_kanban_swarm.py",
        ],
        "decision_ledger": "docs/plans/2026-05-15-acp-zed-edit-approval-diffs.md",
        "architecture_questions": [
            "Does the dispatcher preserve the single-scheduler invariant?",
        ],
        "risk_questions": [
            "What happens if a worker crashes mid-update?",
        ],
        "review_checklist": [
            "Verifier waits on every worker.",
            "Synthesizer cannot run before verifier.",
        ],
    }
    base.update(overrides)
    return cc.WorkerTask(**base)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture


# ── detection ─────────────────────────────────────────────────────────────


def test_detect_absent_binary_does_not_raise():
    with patch("hermes_cli.workers.claude_code.shutil.which", return_value=None):
        det = cc.detect()
    assert det.available is False
    assert det.path is None
    assert det.version is None
    assert det.notes  # has a "go install it" note
    assert any("not on PATH" in n for n in det.notes)


def test_detect_present_parses_version():
    runner = _runner_returning(stdout="claude 1.2.3 (build abc123)\n")
    with patch(
        "hermes_cli.workers.claude_code.shutil.which",
        return_value="/usr/local/bin/claude",
    ):
        det = cc.detect(runner=runner)
    assert det.available is True
    assert det.path == "/usr/local/bin/claude"
    assert det.version == "1.2.3"
    assert det.notes == ()


def test_detect_version_probe_timeout_is_soft():
    runner = _runner_raising(subprocess.TimeoutExpired(cmd=["claude"], timeout=5.0))
    with patch(
        "hermes_cli.workers.claude_code.shutil.which", return_value="/x/claude"
    ):
        det = cc.detect(runner=runner)
    assert det.available is True
    assert det.path == "/x/claude"
    assert det.version is None
    assert any("timed out" in n for n in det.notes)


def test_detect_version_probe_unparseable_output_is_soft():
    runner = _runner_returning(stdout="claude (no version reported)\n")
    with patch(
        "hermes_cli.workers.claude_code.shutil.which", return_value="/x/claude"
    ):
        det = cc.detect(runner=runner)
    assert det.available is True
    assert det.version is None
    assert any("unparseable" in n for n in det.notes)


def test_detect_skip_version_probe():
    with patch(
        "hermes_cli.workers.claude_code.shutil.which", return_value="/x/claude"
    ):
        det = cc.detect(probe_version=False)
    assert det.available is True
    assert det.path == "/x/claude"
    assert det.version is None
    assert det.notes == ()


def test_detect_oserror_does_not_propagate():
    runner = _runner_raising(OSError("permission denied"))
    with patch(
        "hermes_cli.workers.claude_code.shutil.which", return_value="/x/claude"
    ):
        det = cc.detect(runner=runner)
    assert det.available is True
    assert det.version is None
    assert any("probe failed" in n for n in det.notes)


# ── prompt generation ────────────────────────────────────────────────────


def test_prepare_workspace_writes_prompt_and_status(tmp_path: Path):
    task = _sample_task()
    det = cc.ClaudeCodeDetection(
        available=True, path="/x/claude", version="1.2.3", notes=()
    )
    prepared = cc.prepare_workspace(task, tmp_path, detection=det)

    assert prepared.workdir == tmp_path / "workers" / "claude-code"
    assert prepared.prompt_path.is_file()
    assert prepared.status_path.is_file()
    assert prepared.mode == cc.RUN_MODE_HANDOFF
    assert prepared.expected_artifacts == cc.EXPECTED_ARTIFACTS
    assert "patch.diff" not in prepared.required_artifacts


def test_prompt_includes_all_required_sections(tmp_path: Path):
    task = _sample_task()
    prepared = cc.prepare_workspace(
        task,
        tmp_path,
        detection=cc.ClaudeCodeDetection(available=False),
    )
    body = prepared.prompt_path.read_text(encoding="utf-8")
    for heading in (
        "# Claude Code worker — handoff prompt",
        "## Mission",
        "## Repo evidence",
        "## Decision ledger",
        "## Architecture questions",
        "## Risk questions",
        "## Review checklist",
        "## Expected output",
        "### Scoring axes",
        "## Run mode",
        "## Detection snapshot",
    ):
        assert heading in body, f"missing heading: {heading}"
    # The mission text round-trips verbatim
    assert task.mission in body
    # Repo evidence + checklist items appear
    assert "hermes_cli/kanban_swarm.py:80-220" in body
    assert "Verifier waits on every worker." in body
    # Each scoring axis is listed with its weight
    for axis, weight in cc.SCORING_WEIGHTS.items():
        assert f"`{axis}`" in body
        assert f"{weight:.2f}" in body
    # Expected output enumerates every artifact
    for name in cc.EXPECTED_ARTIFACTS:
        assert f"`{name}`" in body


def test_prompt_drops_patch_diff_when_code_changes_disabled(tmp_path: Path):
    task = _sample_task(propose_code_changes=False)
    prepared = cc.prepare_workspace(task, tmp_path)
    assert "patch.diff" not in prepared.expected_artifacts
    assert "patch.diff" not in prepared.required_artifacts
    body = prepared.prompt_path.read_text(encoding="utf-8")
    assert "patch.diff" not in body


def test_prompt_handles_empty_questions_and_no_ledger(tmp_path: Path):
    task = cc.WorkerTask(mission="Quick check.")
    prepared = cc.prepare_workspace(task, tmp_path)
    body = prepared.prompt_path.read_text(encoding="utf-8")
    assert "No decision ledger was supplied" in body
    assert "no explicit architecture questions" in body
    assert "no explicit risk questions" in body
    # Default checklist gets injected
    assert "Confirm the change is consistent" in body


def test_prepare_workspace_rejects_blank_mission(tmp_path: Path):
    with pytest.raises(ValueError, match="non-empty"):
        cc.prepare_workspace(cc.WorkerTask(mission="   "), tmp_path)


def test_prepare_workspace_rejects_unknown_mode(tmp_path: Path):
    with pytest.raises(ValueError, match="invalid run mode"):
        cc.prepare_workspace(_sample_task(), tmp_path, mode="bogus")


# ── handoff status ───────────────────────────────────────────────────────


def test_status_json_default_is_handoff_required(tmp_path: Path):
    det = cc.ClaudeCodeDetection(
        available=True, path="/x/claude", version="1.2.3", notes=()
    )
    prepared = cc.prepare_workspace(_sample_task(), tmp_path, detection=det)
    payload = json.loads(prepared.status_path.read_text(encoding="utf-8"))
    assert payload["worker"] == "claude-code"
    assert payload["mode"] == cc.RUN_MODE_HANDOFF
    assert payload["handoff_required"] is True
    assert payload["scoring_weights"] == dict(cc.SCORING_WEIGHTS)
    assert payload["detection"]["path"] == "/x/claude"
    assert payload["detection"]["version"] == "1.2.3"
    assert payload["expected_artifacts"] == list(cc.EXPECTED_ARTIFACTS)
    assert "patch.diff" not in payload["required_artifacts"]


def test_run_claude_cli_refuses_without_allow_execute(tmp_path: Path):
    det = cc.ClaudeCodeDetection(available=True, path="/x/claude", version="1.2.3")
    prepared = cc.prepare_workspace(
        _sample_task(), tmp_path, mode=cc.RUN_MODE_EXECUTE, detection=det
    )
    res = cc.run_claude_cli(prepared)  # allow_execute defaults to False
    assert res.invoked is False
    assert res.returncode is None
    assert res.error and "allow_execute=False" in res.error


def test_run_claude_cli_refuses_in_handoff_mode(tmp_path: Path):
    det = cc.ClaudeCodeDetection(available=True, path="/x/claude", version="1.2.3")
    prepared = cc.prepare_workspace(_sample_task(), tmp_path, detection=det)
    res = cc.run_claude_cli(prepared, allow_execute=True)
    assert res.invoked is False
    assert res.error and "handoff-required" in res.error


def test_run_claude_cli_refuses_when_cli_missing(tmp_path: Path):
    det = cc.ClaudeCodeDetection(available=False)
    prepared = cc.prepare_workspace(
        _sample_task(), tmp_path, mode=cc.RUN_MODE_EXECUTE, detection=det
    )
    res = cc.run_claude_cli(prepared, allow_execute=True)
    assert res.invoked is False
    assert res.error and "not installed" in res.error


def test_run_claude_cli_invokes_official_binary_only(tmp_path: Path):
    det = cc.ClaudeCodeDetection(available=True, path="/usr/local/bin/claude")
    prepared = cc.prepare_workspace(
        _sample_task(), tmp_path, mode=cc.RUN_MODE_EXECUTE, detection=det
    )
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        captured["cwd"] = kwargs.get("cwd")
        return _FakeProc(returncode=0, stdout="ok", stderr="")

    res = cc.run_claude_cli(
        prepared,
        allow_execute=True,
        runner=fake_run,
        extra_args=["--quiet"],
    )
    assert res.invoked is True
    assert res.returncode == 0
    assert res.stdout == "ok"
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert cmd[0] == "/usr/local/bin/claude"
    assert "--print" in cmd
    assert str(prepared.prompt_path) in cmd
    assert "--quiet" in cmd
    assert captured["cwd"] == str(prepared.workdir)


# ── artifact collection ──────────────────────────────────────────────────


def _write(workdir: Path, name: str, body: str) -> None:
    (workdir / name).write_text(body, encoding="utf-8")


def test_collect_artifacts_all_present(tmp_path: Path):
    prepared = cc.prepare_workspace(_sample_task(), tmp_path)
    workdir = prepared.workdir
    _write(workdir, "output.md", "summary\n")
    _write(workdir, "architecture-review.md", "arch\n")
    _write(workdir, "risk-review.md", "risk\n")
    _write(workdir, "patch.diff", "diff\n")
    # overwrite status.json with a Claude-Code-shaped verdict
    verdict = {
        "worker": "claude-code",
        "verdict": "approve",
        "confidence": 0.82,
        "scores": {
            "architecture_fit": 0.9,
            "risk_control": 0.8,
            "maintainability": 0.7,
            "correctness": 0.85,
            "repo_fit": 0.75,
        },
    }
    (workdir / "status.json").write_text(
        json.dumps(verdict), encoding="utf-8"
    )

    collected = cc.collect_artifacts(prepared)
    assert collected.complete is True
    assert collected.missing_required == ()
    assert set(collected.present) == set(cc.EXPECTED_ARTIFACTS)
    assert collected.status is not None
    assert collected.status["verdict"] == "approve"

    weighted = cc.score(collected.status["scores"])  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture
    expected = (
        0.9 * 0.30
        + 0.8 * 0.25
        + 0.7 * 0.20
        + 0.85 * 0.15
        + 0.75 * 0.10
    )
    assert weighted == pytest.approx(expected)


def test_collect_artifacts_missing_required(tmp_path: Path):
    prepared = cc.prepare_workspace(_sample_task(), tmp_path)
    workdir = prepared.workdir
    _write(workdir, "output.md", "summary\n")
    # arch and risk reviews missing on purpose
    (workdir / "status.json").write_text(
        json.dumps({"worker": "claude-code", "verdict": "block"}),
        encoding="utf-8",
    )
    collected = cc.collect_artifacts(prepared)
    assert collected.complete is False
    assert "architecture-review.md" in collected.missing_required
    assert "risk-review.md" in collected.missing_required
    assert "output.md" not in collected.missing_required
    assert collected.status is not None
    assert collected.status["verdict"] == "block"


def test_collect_artifacts_missing_patch_is_not_required(tmp_path: Path):
    prepared = cc.prepare_workspace(_sample_task(), tmp_path)
    workdir = prepared.workdir
    _write(workdir, "output.md", "summary\n")
    _write(workdir, "architecture-review.md", "arch\n")
    _write(workdir, "risk-review.md", "risk\n")
    (workdir / "status.json").write_text(
        json.dumps({"worker": "claude-code", "verdict": "approve"}),
        encoding="utf-8",
    )
    collected = cc.collect_artifacts(prepared)
    assert collected.complete is True
    assert "patch.diff" not in collected.present


def test_collect_artifacts_malformed_status_marks_incomplete(tmp_path: Path):
    prepared = cc.prepare_workspace(_sample_task(), tmp_path)
    workdir = prepared.workdir
    _write(workdir, "output.md", "summary\n")
    _write(workdir, "architecture-review.md", "arch\n")
    _write(workdir, "risk-review.md", "risk\n")
    (workdir / "status.json").write_text("not json {{{", encoding="utf-8")
    collected = cc.collect_artifacts(prepared)
    assert collected.status is None
    assert "status.json" in collected.missing_required
    assert collected.complete is False


# ── scoring ──────────────────────────────────────────────────────────────


def test_score_clamps_and_treats_missing_axes_as_zero():
    # All axes at 1.0 → weighted score equals the sum of weights (1.0).
    perfect = {axis: 1.0 for axis in cc.SCORING_WEIGHTS}
    assert cc.score(perfect) == pytest.approx(1.0)

    # No axes scored → 0.0.
    assert cc.score({}) == 0.0

    # Out-of-range values are clamped, non-numeric values become zero.
    weird = {
        "architecture_fit": 5.0,          # clamped to 1.0
        "risk_control": -0.4,             # clamped to 0.0
        "maintainability": "0.5",         # stringified float coerces
        "correctness": "not a number",    # → 0.0
        # repo_fit absent → 0.0
        "extra_axis": 1.0,                # ignored
    }
    expected = 1.0 * 0.30 + 0.0 * 0.25 + 0.5 * 0.20 + 0.0 * 0.15 + 0.0 * 0.10
    assert cc.score(weird) == pytest.approx(expected)  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture


def test_scoring_weights_sum_to_one():
    assert sum(cc.SCORING_WEIGHTS.values()) == pytest.approx(1.0)


# ── miscellaneous helpers ────────────────────────────────────────────────


def test_describe_round_trip(tmp_path: Path):
    det = cc.ClaudeCodeDetection(
        available=True, path="/x/claude", version="9.9.9", notes=()
    )
    prepared = cc.prepare_workspace(_sample_task(), tmp_path, detection=det)
    snap = cc.describe(prepared)
    assert snap["worker"] == "claude-code"
    assert snap["mode"] == cc.RUN_MODE_HANDOFF
    assert Path(str(snap["workdir"])) == prepared.workdir
    assert Path(str(snap["prompt_path"])) == prepared.prompt_path
    assert snap["detection"]["path"] == "/x/claude"  # ty: ignore[not-subscriptable]  # mock/duck-typed test fixture


def test_iter_expected_artifact_paths_matches_workdir(tmp_path: Path):
    prepared = cc.prepare_workspace(_sample_task(), tmp_path)
    paths = list(cc.iter_expected_artifact_paths(prepared))
    expected = [prepared.workdir / name for name in cc.EXPECTED_ARTIFACTS]
    assert paths == expected


def test_collected_as_dict_is_json_safe(tmp_path: Path):
    prepared = cc.prepare_workspace(_sample_task(), tmp_path)
    _write(prepared.workdir, "output.md", "x")
    _write(prepared.workdir, "architecture-review.md", "x")
    _write(prepared.workdir, "risk-review.md", "x")
    (prepared.workdir / "status.json").write_text(
        json.dumps({"verdict": "approve"}), encoding="utf-8"
    )
    collected = cc.collect_artifacts(prepared)
    snap = cc.collected_as_dict(collected)
    # round-trips through json
    body = json.dumps(snap)
    again = json.loads(body)
    assert again["complete"] is True
    assert again["status"]["verdict"] == "approve"


# Imports used only for typing in fixtures above — silence vulture.
_ = Optional
