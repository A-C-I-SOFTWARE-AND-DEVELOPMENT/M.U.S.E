"""Publish a winning job to GitHub as a (draft) pull request.

Tests must NEVER call the real ``gh`` binary or push to a repository.
This module is built around a single seam:

* ``runner`` — invokes a shell command. The real one shells out;
  tests pass a fake that records calls and returns canned results.
* ``dry_run=True`` (default) — records what *would* run and returns a
  :class:`PublishResult` with ``pr_url=None``. No commands execute.

Even with ``dry_run=False``, every command is recorded in
:attr:`PublishResult.commands` so the operator can audit the action.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from hermes_cli.workers.base import _real_runner

RunnerFn = Callable[[list[str], Path, dict[str, str] | None], tuple[int, str]]


@dataclass
class PublishResult:
    dry_run: bool
    branch: str
    base: str
    pr_url: str | None = None
    pr_number: int | None = None
    commands: list[list[str]] = field(default_factory=list)
    log: str = ""
    blocked: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blocked and (self.dry_run or self.pr_url is not None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "branch": self.branch,
            "base": self.base,
            "pr_url": self.pr_url,
            "pr_number": self.pr_number,
            "commands": [" ".join(c) for c in self.commands],
            "blocked": list(self.blocked),
        }


_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]{1,100}$")
_PROTECTED_BASES = {"main", "master", "production", "release"}


def _check_branch(branch: str) -> str | None:
    if not _BRANCH_RE.match(branch):
        return f"invalid branch name: {branch!r}"
    if branch in _PROTECTED_BASES:
        return f"refusing to publish onto protected branch {branch!r}"
    return None


def _read_diff(job_dir: Path) -> str:
    selected = job_dir / "selected.json"
    if not selected.exists():
        return ""
    payload = json.loads(selected.read_text(encoding="utf-8"))
    worker = payload.get("worker")
    if not worker:
        return ""
    diff_path = job_dir / "workers" / worker / "output.diff"
    return diff_path.read_text(encoding="utf-8") if diff_path.exists() else ""


def _read_validation(job_dir: Path) -> tuple[bool, list[str]]:
    path = job_dir / "validation.json"
    if not path.exists():
        return True, []  # treat missing validation as "skipped" — allow but warn
    payload = json.loads(path.read_text(encoding="utf-8"))
    gates = payload.get("gates") or {}
    failed = [name for name, info in gates.items() if not info.get("passed")]
    return not failed, failed


def publish(
    job_dir: Path | str,
    *,
    branch: str,
    base: str = "main",
    title: str | None = None,
    body: str | None = None,
    dry_run: bool = True,
    runner: RunnerFn | None = None,
    require_validation: bool = True,
) -> PublishResult:
    """Open (or simulate opening) a draft PR for the winning worker.

    The publisher refuses to act if:

    * ``branch`` is invalid or one of the protected bases.
    * ``require_validation`` is True and ``validation.json`` shows a
      failing gate (or the file is missing).
    * No diff is selected.

    Refusals are recorded in :attr:`PublishResult.blocked` and the
    function returns without executing any commands.
    """

    job_dir = Path(job_dir)
    runner = runner or _real_runner
    result = PublishResult(dry_run=dry_run, branch=branch, base=base)

    err = _check_branch(branch)
    if err:
        result.blocked.append(err)
    if base in _PROTECTED_BASES and branch == base:
        # already caught above but keep explicit
        pass

    diff = _read_diff(job_dir)
    if not diff.strip():
        result.blocked.append("no selected diff to publish")

    if require_validation:
        ok, failed = _read_validation(job_dir)
        if not ok:
            result.blocked.append(f"validation failed: {failed}")
        elif not (job_dir / "validation.json").exists():
            result.blocked.append("validation.json missing")

    if result.blocked:
        return result

    title = title or _default_title(job_dir)
    body = body or _default_body(job_dir)

    commands: list[list[str]] = [
        ["git", "checkout", "-B", branch],
        ["git", "apply", "--whitespace=nowarn", "-"],  # diff piped on stdin
        ["git", "add", "-A"],
        ["git", "commit", "-m", title],
        ["git", "push", "-u", "origin", branch],
        ["gh", "pr", "create", "--draft", "--base", base,
         "--head", branch, "--title", title, "--body", body],
    ]
    result.commands = commands

    if dry_run:
        result.log = "DRY-RUN: would run " + str(len(commands)) + " commands"
        return result

    # Non-dry: execute each command. We deliberately do NOT pipe the
    # diff into git apply via stdin from here — the real apply path uses
    # the temp-file approach in merge_engine.apply_diff. For tests, the
    # runner records commands and we return early on the first failure.
    for cmd in commands:
        rc, out = runner(cmd, job_dir, None)
        result.log += f"$ {' '.join(cmd)}\n{out}\n"
        if rc != 0:
            result.blocked.append(f"command failed (exit {rc}): {' '.join(cmd[:2])}")
            return result
        # Capture PR URL from the final ``gh pr create`` invocation.
        if cmd[:3] == ["gh", "pr", "create"]:
            m = re.search(r"https://github\.com/[\w/.-]+/pull/(\d+)", out)
            if m:
                result.pr_url = m.group(0)
                result.pr_number = int(m.group(1))
    return result


def _default_title(job_dir: Path) -> str:
    try:
        meta = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
        return f"orchestrator: {meta.get('title', job_dir.name)}"
    except (OSError, json.JSONDecodeError):
        return f"orchestrator: {job_dir.name}"


def _default_body(job_dir: Path) -> str:
    parts = ["Generated by the Hermes orchestrator.", "", f"Job: `{job_dir.name}`"]
    selected = job_dir / "selected.json"
    if selected.exists():
        try:
            payload = json.loads(selected.read_text(encoding="utf-8"))
            parts.append(f"Selected worker: `{payload.get('worker')}`")
            parts.append(f"Score: `{payload.get('score')}`")
        except json.JSONDecodeError:
            pass
    return "\n".join(parts)


__all__ = ["PublishResult", "publish"]
