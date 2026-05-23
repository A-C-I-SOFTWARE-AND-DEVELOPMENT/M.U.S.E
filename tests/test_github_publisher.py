"""Tests for the GitHub publisher.

The publisher must NEVER call out to ``gh`` or ``git push`` during
tests. Every test passes a fake runner that records commands and
returns canned exit codes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli.orchestrator.github_publisher import (
    PublishResult,
    publish,
)
from hermes_cli.orchestrator.job_controller import JobController


def _seed_job(
    tmp_path: Path,
    *,
    with_diff: bool = True,
    validation_overall: bool = True,
    with_validation: bool = True,
) -> Path:
    controller = JobController(tmp_path / "jobs")
    ctx = controller.create("Test job", title="t")
    if with_diff:
        wdir = ctx.job_dir / "workers" / "hermes_local"
        wdir.mkdir(parents=True)
        (wdir / "output.diff").write_text(
            "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"
        )
        (wdir / "log.txt").write_text("ok")
        (wdir / "status.json").write_text(
            json.dumps({"worker": "hermes_local", "status": "done"})
        )
        (wdir / "result.json").write_text(
            json.dumps(
                {"worker": "hermes_local", "success": True, "files_changed": 1,
                 "exit_code": 0, "message": "ok"}
            )
        )
        (ctx.job_dir / "selected.json").write_text(
            json.dumps({"worker": "hermes_local", "score": 100.0})
        )
    if with_validation:
        payload = {
            "gates": {
                "py_compile": {"name": "py_compile", "passed": validation_overall,
                               "message": "ok"},
            },
            "overall": validation_overall,
        }
        (ctx.job_dir / "validation.json").write_text(json.dumps(payload))
    return ctx.job_dir


# ── dry-run behavior ─────────────────────────────────────────────────


def test_publish_dry_run_records_commands_but_does_not_call_runner(
    tmp_path: Path,
) -> None:
    job_dir = _seed_job(tmp_path)

    def boom(*a, **kw):
        raise AssertionError("runner must not be called in dry-run")

    res = publish(job_dir, branch="feat/hermes/test", dry_run=True, runner=boom)
    assert res.dry_run is True
    assert res.pr_url is None
    assert len(res.commands) >= 5
    # First command must check out a new branch
    assert res.commands[0][:2] == ["git", "checkout"]
    # Last command must invoke gh pr create with --draft
    assert res.commands[-1][:3] == ["gh", "pr", "create"]
    assert "--draft" in res.commands[-1]


def test_publish_dry_run_ok_when_validation_passes(tmp_path: Path) -> None:
    job_dir = _seed_job(tmp_path)
    res = publish(job_dir, branch="feat/x", dry_run=True, runner=lambda *a, **k: (0, ""))
    assert res.ok is True
    assert not res.blocked


# ── blocking conditions ──────────────────────────────────────────────


def test_publish_blocks_protected_branch(tmp_path: Path) -> None:
    job_dir = _seed_job(tmp_path)
    res = publish(job_dir, branch="main", dry_run=True)
    assert res.blocked
    assert any("protected" in b for b in res.blocked)
    assert res.ok is False
    assert res.pr_url is None


def test_publish_blocks_invalid_branch_name(tmp_path: Path) -> None:
    job_dir = _seed_job(tmp_path)
    res = publish(job_dir, branch="bad branch name", dry_run=True)
    assert any("invalid branch" in b for b in res.blocked)


def test_publish_blocks_when_no_selected_diff(tmp_path: Path) -> None:
    job_dir = _seed_job(tmp_path, with_diff=False)
    res = publish(job_dir, branch="feat/x", dry_run=True)
    assert any("no selected diff" in b for b in res.blocked)


def test_publish_blocks_when_validation_fails(tmp_path: Path) -> None:
    job_dir = _seed_job(tmp_path, validation_overall=False)
    res = publish(job_dir, branch="feat/x", dry_run=True)
    assert any("validation failed" in b for b in res.blocked)


def test_publish_blocks_when_validation_missing(tmp_path: Path) -> None:
    job_dir = _seed_job(tmp_path, with_validation=False)
    res = publish(job_dir, branch="feat/x", dry_run=True)
    assert any("validation.json missing" in b for b in res.blocked)


def test_publish_skip_validation_flag_allows(tmp_path: Path) -> None:
    job_dir = _seed_job(tmp_path, with_validation=False)
    res = publish(job_dir, branch="feat/x", dry_run=True,
                  require_validation=False)
    assert res.blocked == []


# ── execute path with fake runner ────────────────────────────────────


def test_publish_execute_runs_commands_in_order(tmp_path: Path) -> None:
    job_dir = _seed_job(tmp_path)
    seen: list[list[str]] = []

    def runner(cmd, cwd, env):
        seen.append(cmd)
        if cmd[:3] == ["gh", "pr", "create"]:
            return 0, "https://github.com/o/r/pull/42\n"
        return 0, ""

    res = publish(job_dir, branch="feat/x", dry_run=False, runner=runner)
    assert res.ok is True
    assert res.pr_url == "https://github.com/o/r/pull/42"
    assert res.pr_number == 42
    # Commands ran in the documented order.
    assert seen[0][:2] == ["git", "checkout"]
    assert seen[-1][:3] == ["gh", "pr", "create"]


def test_publish_execute_aborts_on_first_failure(tmp_path: Path) -> None:
    job_dir = _seed_job(tmp_path)
    seen: list[list[str]] = []

    def runner(cmd, cwd, env):
        seen.append(cmd)
        # Fail at the push step
        if cmd[:2] == ["git", "push"]:
            return 1, "push rejected\n"
        return 0, ""

    res = publish(job_dir, branch="feat/x", dry_run=False, runner=runner)
    assert res.ok is False
    assert any("command failed" in b for b in res.blocked)
    assert res.pr_url is None
    # gh pr create must NOT have been attempted after the push failed.
    assert not any(c[:3] == ["gh", "pr", "create"] for c in seen)


# ── serialization ───────────────────────────────────────────────────


def test_publish_result_to_dict_roundtrips() -> None:
    res = PublishResult(
        dry_run=True,
        branch="x",
        base="main",
        pr_url=None,
        commands=[["git", "checkout"], ["gh", "pr", "create"]],
    )
    d = res.to_dict()
    assert d["dry_run"] is True
    assert d["branch"] == "x"
    assert d["base"] == "main"
    assert d["commands"] == ["git checkout", "gh pr create"]
