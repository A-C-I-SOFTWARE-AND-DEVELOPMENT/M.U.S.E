"""CLI command handlers for ``hermes orchestrate``.

This module is the boundary between argparse and the orchestrator
internals. Each ``cmd_*`` function takes a parsed namespace (or
keyword args, in tests) and returns an integer exit code. Tests call
them directly rather than going through argparse.

The commands are:

* ``run <prompt>`` — create a job, fan out to detected workers,
  score the outputs, validate, write artifacts.
* ``list``         — print known jobs (id, title, status, selected worker).
* ``show <id>``    — print the full status of a single job as JSON.
* ``publish <id>`` — publish the selected worker via the GitHub publisher.
* ``workers``      — list available worker adapters and whether each is detected.

Every command takes ``--jobs-root`` (default ``~/.hermes/orchestrator/jobs``)
and is hermetic by default — no command performs side effects outside
``--jobs-root`` unless explicitly asked (``publish`` without ``--dry-run``).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from hermes_cli.orchestrator import (
    JobController,
    JobNotFoundError,
    PyCompileGate,
    ShellSyntaxGate,
    NoSecretsGate,
    publish,
    run_gates,
    score_worker,
    select_best,
)
from hermes_cli.orchestrator.validation_gates import all_passed
from hermes_cli.workers import ALL_WORKERS, detect_available, get_worker
from hermes_cli.workers.base import WorkerStatus

DEFAULT_JOBS_ROOT = Path.home() / ".hermes" / "orchestrator" / "jobs"


def _resolve_jobs_root(arg: str | os.PathLike | None) -> Path:
    if arg:
        return Path(arg).expanduser()
    env = os.environ.get("HERMES_ORCHESTRATOR_JOBS_ROOT")
    if env:
        return Path(env).expanduser()
    return DEFAULT_JOBS_ROOT


def _emit(stream, payload: Any) -> None:
    if isinstance(payload, (dict, list)):
        stream.write(json.dumps(payload, indent=2, sort_keys=True))
        stream.write("\n")
    else:
        stream.write(str(payload))
        stream.write("\n")


# ── commands ────────────────────────────────────────────────────────


def cmd_run(
    prompt: str,
    *,
    jobs_root: Path | None = None,
    workers: list[str] | None = None,
    dry_run: bool = True,
    title: str = "",
    base_branch: str = "main",
    runner=None,
    stdout=None,
) -> int:
    stdout = stdout or sys.stdout
    jobs_root = _resolve_jobs_root(jobs_root)
    controller = JobController(jobs_root)

    if not prompt or not prompt.strip():
        stdout.write("error: prompt is required\n")
        return 2

    ctx = controller.create(prompt, title=title, base_branch=base_branch)

    if workers:
        try:
            worker_classes = [get_worker(name) for name in workers]
        except KeyError as exc:
            stdout.write(f"error: {exc}\n")
            return 2
    else:
        worker_classes = detect_available()
        if not worker_classes:
            stdout.write("error: no workers detected\n")
            return 3

    controller.set_status(ctx, WorkerStatus.RUNNING)
    for cls in worker_classes:
        adapter = cls()
        result = adapter.run(ctx, runner=runner, dry_run=dry_run)
        controller.write_worker_result(ctx, adapter, result)

    winner, score = select_best(ctx.job_dir)
    if winner is None:
        controller.set_status(ctx, WorkerStatus.FAILED)
        _emit(stdout, {"job_id": ctx.job_id, "selected": None, "status": "failed"})
        return 4

    controller.mark_selected(ctx, winner, score.total if score else 0.0)
    controller.set_status(ctx, WorkerStatus.DONE)

    _emit(
        stdout,
        {
            "job_id": ctx.job_id,
            "selected": winner,
            "score": score.total if score else 0.0,
            "workers": [c.name for c in worker_classes],
        },
    )
    return 0


def cmd_list(*, jobs_root: Path | None = None, stdout=None) -> int:
    stdout = stdout or sys.stdout
    controller = JobController(_resolve_jobs_root(jobs_root))
    rows = []
    for jid in controller.list():
        info = controller.status(jid)
        selected = None
        if info.get("has_selected"):
            sel_path = controller.jobs_root / jid / "selected.json"
            try:
                selected = json.loads(sel_path.read_text(encoding="utf-8")).get("worker")
            except (OSError, json.JSONDecodeError):
                selected = None
        rows.append(
            {
                "id": jid,
                "title": info.get("title", ""),
                "status": info.get("status"),
                "selected": selected,
            }
        )
    _emit(stdout, rows)
    return 0


def cmd_show(job_id: str, *, jobs_root: Path | None = None, stdout=None) -> int:
    stdout = stdout or sys.stdout
    controller = JobController(_resolve_jobs_root(jobs_root))
    try:
        info = controller.status(job_id)
    except JobNotFoundError as exc:
        stdout.write(f"error: job not found: {exc}\n")
        return 1
    # Augment with selected / validation / publish file contents if present.
    job_dir = controller.jobs_root / job_id
    for name in ("selected", "validation", "publish"):
        path = job_dir / f"{name}.json"
        if path.exists():
            try:
                info[name] = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                info[name] = {"_error": "invalid json"}
    _emit(stdout, info)
    return 0


def cmd_publish(
    job_id: str,
    *,
    jobs_root: Path | None = None,
    branch: str | None = None,
    base: str = "main",
    dry_run: bool = True,
    runner=None,
    require_validation: bool = True,
    stdout=None,
) -> int:
    stdout = stdout or sys.stdout
    controller = JobController(_resolve_jobs_root(jobs_root))
    try:
        ctx = controller.load(job_id)
    except JobNotFoundError as exc:
        stdout.write(f"error: job not found: {exc}\n")
        return 1
    branch = branch or f"hermes-orchestrator/{ctx.job_id}"
    result = publish(
        ctx.job_dir,
        branch=branch,
        base=base,
        dry_run=dry_run,
        runner=runner,
        require_validation=require_validation,
    )
    controller.write_publish(ctx, result.to_dict())
    _emit(stdout, result.to_dict())
    return 0 if result.ok else 5


def cmd_workers(*, stdout=None) -> int:
    stdout = stdout or sys.stdout
    rows = [
        {
            "name": cls.name,
            "binary": cls.binary,
            "bundled": cls.bundled,
            "available": cls.detect(),
            "description": cls.description,
        }
        for cls in ALL_WORKERS
    ]
    _emit(stdout, rows)
    return 0


def cmd_validate(
    job_id: str,
    *,
    jobs_root: Path | None = None,
    runner=None,
    stdout=None,
) -> int:
    """Run validation gates against the selected worker's output."""
    stdout = stdout or sys.stdout
    controller = JobController(_resolve_jobs_root(jobs_root))
    try:
        ctx = controller.load(job_id)
    except JobNotFoundError as exc:
        stdout.write(f"error: job not found: {exc}\n")
        return 1
    selected_path = ctx.job_dir / "selected.json"
    if not selected_path.exists():
        stdout.write("error: no selected worker\n")
        return 1
    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    diff_path = ctx.job_dir / "workers" / selected["worker"] / "output.diff"
    diff = diff_path.read_text(encoding="utf-8") if diff_path.exists() else ""

    gates = [
        PyCompileGate(),
        ShellSyntaxGate(),
        NoSecretsGate(diff=diff),
    ]
    results = run_gates(ctx.repo_dir, gates, runner=runner)
    payload = {
        "gates": {name: r.to_dict() for name, r in results.items()},
        "overall": all_passed(results),
    }
    controller.write_validation(ctx, payload)
    _emit(stdout, payload)
    return 0 if payload["overall"] else 6


# ── argparse glue ────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hermes orchestrate")
    p.add_argument(
        "--jobs-root",
        default=None,
        help="Override jobs root (default: ~/.hermes/orchestrator/jobs)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run a new orchestration job")
    run_p.add_argument("prompt", help="Prompt text (or @<path> to read a file)")
    run_p.add_argument("--worker", action="append", dest="workers",
                       help="Restrict to specific worker(s); repeat")
    run_p.add_argument("--title", default="", help="Optional job title")
    run_p.add_argument("--base-branch", default="main")
    run_p.add_argument("--execute", dest="dry_run", action="store_false",
                       default=True,
                       help="Actually run workers (default is dry-run)")

    sub.add_parser("list", help="List known jobs")

    show_p = sub.add_parser("show", help="Show a job's status")
    show_p.add_argument("job_id")

    pub_p = sub.add_parser("publish", help="Publish a job to GitHub")
    pub_p.add_argument("job_id")
    pub_p.add_argument("--branch", default=None)
    pub_p.add_argument("--base", default="main")
    pub_p.add_argument("--execute", dest="dry_run", action="store_false",
                       default=True,
                       help="Actually open the PR (default is dry-run)")
    pub_p.add_argument("--skip-validation", dest="require_validation",
                       action="store_false", default=True)

    val_p = sub.add_parser("validate", help="Run validation gates on a job")
    val_p.add_argument("job_id")

    sub.add_parser("workers", help="List worker adapters and detection state")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "run":
        prompt = args.prompt
        if prompt.startswith("@"):
            prompt = Path(prompt[1:]).expanduser().read_text(encoding="utf-8")
        return cmd_run(
            prompt,
            jobs_root=args.jobs_root,
            workers=args.workers,
            dry_run=args.dry_run,
            title=args.title,
            base_branch=args.base_branch,
        )
    if args.cmd == "list":
        return cmd_list(jobs_root=args.jobs_root)
    if args.cmd == "show":
        return cmd_show(args.job_id, jobs_root=args.jobs_root)
    if args.cmd == "publish":
        return cmd_publish(
            args.job_id,
            jobs_root=args.jobs_root,
            branch=args.branch,
            base=args.base,
            dry_run=args.dry_run,
            require_validation=args.require_validation,
        )
    if args.cmd == "validate":
        return cmd_validate(args.job_id, jobs_root=args.jobs_root)
    if args.cmd == "workers":
        return cmd_workers()
    parser.error(f"unknown command {args.cmd}")
    return 2


__all__ = [
    "build_parser",
    "cmd_list",
    "cmd_publish",
    "cmd_run",
    "cmd_show",
    "cmd_validate",
    "cmd_workers",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
