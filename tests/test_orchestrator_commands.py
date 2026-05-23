"""Tests for the orchestrator CLI command surface."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pytest

from hermes_cli import orchestrator_commands as cmds
from hermes_cli.orchestrator.job_controller import JobController
from hermes_cli.workers import ALL_WORKERS, get_worker, HermesLocalWorker
from hermes_cli.workers.base import WorkerStatus


@pytest.fixture
def jobs_root(tmp_path: Path) -> Path:
    return tmp_path / "jobs"


# ── workers / list ──────────────────────────────────────────────────


def test_cmd_workers_lists_all_adapters() -> None:
    out = io.StringIO()
    rc = cmds.cmd_workers(stdout=out)
    assert rc == 0
    data = json.loads(out.getvalue())
    names = {row["name"] for row in data}
    assert {"hermes_local", "codex", "claude_code", "aider", "goose"} <= names
    # Bundled worker is always available.
    bundled = next(row for row in data if row["name"] == "hermes_local")
    assert bundled["bundled"] is True
    assert bundled["available"] is True


def test_cmd_list_empty_returns_empty_array(jobs_root: Path) -> None:
    out = io.StringIO()
    assert cmds.cmd_list(jobs_root=jobs_root, stdout=out) == 0
    assert json.loads(out.getvalue()) == []


# ── run ─────────────────────────────────────────────────────────────


def test_cmd_run_dry_run_creates_job_and_selects_winner(
    jobs_root: Path,
) -> None:
    out = io.StringIO()
    rc = cmds.cmd_run(
        "Fix the docs",
        jobs_root=jobs_root,
        workers=["hermes_local"],
        dry_run=True,
        stdout=out,
    )
    assert rc == 0
    payload = json.loads(out.getvalue())
    assert payload["selected"] == "hermes_local"
    job_id = payload["job_id"]
    # Job folder must have the contract files.
    job_dir = jobs_root / job_id
    assert (job_dir / "job.json").exists()
    assert (job_dir / "prompt.md").exists()
    assert (job_dir / "selected.json").exists()
    assert (job_dir / "workers" / "hermes_local").is_dir()


def test_cmd_run_rejects_empty_prompt(jobs_root: Path) -> None:
    out = io.StringIO()
    rc = cmds.cmd_run("   ", jobs_root=jobs_root, stdout=out)
    assert rc == 2


def test_cmd_run_rejects_unknown_worker(jobs_root: Path) -> None:
    out = io.StringIO()
    rc = cmds.cmd_run(
        "do something",
        jobs_root=jobs_root,
        workers=["doesnotexist"],
        stdout=out,
    )
    assert rc == 2


def test_cmd_run_with_injected_runner(jobs_root: Path) -> None:
    """When ``runner`` is supplied (non-dry-run), it must be the only path."""

    captured: list[list[str]] = []

    def runner(cmd, cwd, env):
        captured.append(cmd)
        if cmd[:2] == ["git", "diff"]:
            return 0, "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
        return 0, "HERMES_DONE: ok\n"

    out = io.StringIO()
    rc = cmds.cmd_run(
        "Hello",
        jobs_root=jobs_root,
        workers=["hermes_local"],
        dry_run=False,
        runner=runner,
        stdout=out,
    )
    assert rc == 0
    assert any(c[0] == "hermes" for c in captured)


# ── show ────────────────────────────────────────────────────────────


def test_cmd_show_returns_full_status(jobs_root: Path) -> None:
    controller = JobController(jobs_root)
    ctx = controller.create("Hello", job_id="my-job")
    controller.set_status(ctx, WorkerStatus.DONE)
    controller.mark_selected(ctx, "hermes_local", 50.0)

    out = io.StringIO()
    rc = cmds.cmd_show("my-job", jobs_root=jobs_root, stdout=out)
    assert rc == 0
    payload = json.loads(out.getvalue())
    assert payload["id"] == "my-job"
    assert payload["status"] == WorkerStatus.DONE
    assert payload["selected"]["worker"] == "hermes_local"


def test_cmd_show_unknown_job_returns_1(jobs_root: Path) -> None:
    out = io.StringIO()
    rc = cmds.cmd_show("nope", jobs_root=jobs_root, stdout=out)
    assert rc == 1


# ── publish ─────────────────────────────────────────────────────────


def _seed_publishable_job(jobs_root: Path) -> str:
    controller = JobController(jobs_root)
    ctx = controller.create("seed", job_id="seed-job")
    wdir = ctx.job_dir / "workers" / "hermes_local"
    wdir.mkdir(parents=True)
    (wdir / "output.diff").write_text(
        "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
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
    controller.mark_selected(ctx, "hermes_local", 100.0)
    controller.write_validation(ctx, {"gates": {}, "overall": True})
    return ctx.job_id


def test_cmd_publish_dry_run_writes_publish_json(jobs_root: Path) -> None:
    jid = _seed_publishable_job(jobs_root)
    out = io.StringIO()
    rc = cmds.cmd_publish(
        jid,
        jobs_root=jobs_root,
        branch="feat/test",
        dry_run=True,
        runner=lambda *a, **k: (0, ""),
        stdout=out,
    )
    assert rc == 0
    publish_json = jobs_root / jid / "publish.json"
    assert publish_json.exists()
    payload = json.loads(publish_json.read_text())
    assert payload["dry_run"] is True
    assert payload["branch"] == "feat/test"
    assert "git checkout -B feat/test" in payload["commands"][0]


def test_cmd_publish_protected_branch_returns_nonzero(jobs_root: Path) -> None:
    jid = _seed_publishable_job(jobs_root)
    out = io.StringIO()
    rc = cmds.cmd_publish(
        jid, jobs_root=jobs_root, branch="main", dry_run=True, stdout=out,
    )
    assert rc == 5


def test_cmd_publish_missing_job_returns_1(jobs_root: Path) -> None:
    out = io.StringIO()
    rc = cmds.cmd_publish("nope", jobs_root=jobs_root, branch="feat/x", stdout=out)
    assert rc == 1


# ── validate ────────────────────────────────────────────────────────


def test_cmd_validate_no_selection_returns_1(jobs_root: Path) -> None:
    controller = JobController(jobs_root)
    controller.create("hi", job_id="needs-select")
    out = io.StringIO()
    rc = cmds.cmd_validate("needs-select", jobs_root=jobs_root, stdout=out)
    assert rc == 1


def test_cmd_validate_writes_validation_json(jobs_root: Path) -> None:
    jid = _seed_publishable_job(jobs_root)
    # Remove the seeded validation so we re-produce it via the gates.
    (jobs_root / jid / "validation.json").unlink()

    def runner(cmd, cwd, env):
        return 0, ""

    out = io.StringIO()
    rc = cmds.cmd_validate(
        jid, jobs_root=jobs_root, runner=runner, stdout=out,
    )
    assert rc == 0
    payload = json.loads((jobs_root / jid / "validation.json").read_text())
    assert payload["overall"] is True
    assert "py_compile" in payload["gates"]


# ── argparse glue / main entry ──────────────────────────────────────


def test_build_parser_accepts_run_command() -> None:
    parser = cmds.build_parser()
    args = parser.parse_args([
        "run", "do a thing", "--worker", "hermes_local",
    ])
    assert args.cmd == "run"
    assert args.prompt == "do a thing"
    assert args.workers == ["hermes_local"]
    assert args.dry_run is True  # default
    assert args.base_branch == "main"


def test_build_parser_accepts_publish_command() -> None:
    parser = cmds.build_parser()
    args = parser.parse_args([
        "publish", "abc", "--branch", "feat/x", "--execute",
    ])
    assert args.cmd == "publish"
    assert args.dry_run is False
    assert args.base == "main"
    assert args.require_validation is True


def test_build_parser_rejects_unknown() -> None:
    parser = cmds.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["nonsense"])


def test_main_workers_smoke(capsys) -> None:
    rc = cmds.main(["workers"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    names = {row["name"] for row in data}
    assert "hermes_local" in names


def test_jobs_root_env_var(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERMES_ORCHESTRATOR_JOBS_ROOT", str(tmp_path / "envroot"))
    out = io.StringIO()
    rc = cmds.cmd_list(jobs_root=None, stdout=out)
    assert rc == 0
    assert (tmp_path / "envroot").exists()
