"""Aider worker adapter.

Aider is best for git-native edits, repo-map guided implementation,
lint/test repair, and small/medium pair-programming changes. This
adapter:

1. Detects whether the ``aider`` CLI is installed.
2. Writes a worker-tuned ``prompt.md`` into the workspace.
3. Defaults to **handoff-required** — the user runs ``aider`` manually
   with the prepared prompt.
4. When ``execute=True`` and the binary is available, invokes Aider
   with conservative flags (no auto-commit, no destructive shortcuts,
   no streaming-yes).
5. Writes ``status.json``; on execution, also captures ``output.md``,
   ``patch.diff`` and ``changed-files.txt``.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from muse_cli.workers.base import (
    WorkerResult,
    WorkerStatus,
    WorkerTask,
    collect_git_artifacts,
    detect_command,
    ensure_workspace,
    render_acceptance_block,
    render_context_block,
    render_files_block,
    write_prompt,
    write_status,
)

WORKER_NAME = "aider"
DEFAULT_COMMAND = "aider"

# Flags Aider documents as safe for non-interactive use. We intentionally
# refuse to pass ``--yes-always`` (auto-applies every suggestion) or to
# enable auto-commits — destructive shortcuts have to be requested by
# the human running the tool, not by the orchestrator.
_SAFE_FLAGS: tuple[str, ...] = (
    "--no-auto-commits",
    "--no-stream",
    "--no-pretty",
    "--no-check-update",
    "--no-show-release-notes",
    "--no-analytics",
)


@dataclass(frozen=True)
class AiderConfig:
    """Knobs the caller can override per invocation."""

    command: str = DEFAULT_COMMAND
    model: Optional[str] = None
    extra_args: tuple[str, ...] = field(default_factory=tuple)
    timeout_seconds: int = 600


def render_prompt(task: WorkerTask) -> str:
    """Build the worker-tuned ``prompt.md`` body for Aider."""
    title = task.title.strip() or "Untitled task"
    instructions = task.instructions.strip() or "(no instructions provided)"
    body = (
        f"# {title}\n\n"
        "You are running inside the Aider CLI. Aider is best at small/"
        "medium git-native edits guided by the repo map. Stay within the "
        "files listed below unless absolutely necessary, ask before "
        "touching files outside scope, and let the human commit — do not "
        "use ``/commit`` or any auto-commit flag.\n\n"
        "## Task\n"
        f"{instructions}\n"
        + render_files_block(task.files)
        + render_context_block(task.context)
        + render_acceptance_block(task.acceptance_criteria)
        + "\n## Guardrails\n"
        "- No destructive shell commands (``rm -rf``, ``git reset --hard``,"
        " ``git push --force``).\n"
        "- No auto-commits — the human reviews ``patch.diff`` and commits.\n"
        "- If the change needs a new dependency or migration, stop and"
        " describe it instead of installing.\n"
        "- If the task is ambiguous, ask one focused question.\n"
    )
    return body


def build_handoff_command(
    config: AiderConfig,
    workspace: Path,
    task: WorkerTask,
) -> str:
    """Return a copy-pasteable ``aider`` invocation for manual handoff."""
    parts = [config.command, *_SAFE_FLAGS]
    if config.model:
        parts.extend(["--model", config.model])
    parts.extend(config.extra_args)
    if task.files:
        parts.extend(task.files)
    prompt_path = (workspace / "prompt.md").as_posix()
    parts.extend(["--message-file", prompt_path])
    return " ".join(parts)


def run(
    task: WorkerTask,
    workspace: Path,
    *,
    execute: bool = False,
    repo_root: Optional[Path] = None,
    config: Optional[AiderConfig] = None,
) -> WorkerResult:
    """Prepare (and optionally execute) an Aider run.

    ``execute=False`` (default) is the handoff path: prompt + status are
    written and the user runs Aider manually. ``execute=True`` requires
    the ``aider`` binary on ``$PATH``; if it is missing, the result
    falls back to ``COMMAND_NOT_FOUND`` rather than crashing.
    """
    cfg = config or AiderConfig()
    workspace = ensure_workspace(workspace)
    repo_root = (repo_root or Path.cwd()).resolve()

    prompt_body = render_prompt(task)
    prompt_path = write_prompt(workspace, prompt_body)
    available = detect_command(cfg.command)
    handoff_command = build_handoff_command(cfg, workspace, task)

    if not execute:
        result = WorkerResult(
            worker=WORKER_NAME,
            status=WorkerStatus.HANDOFF_REQUIRED,
            workspace=workspace,
            prompt_path=prompt_path,
            status_path=workspace / "status.json",
            command_available=available,
            handoff_command=handoff_command,
        )
        result.status_path = write_status(workspace, result)
        return result

    if not available:
        result = WorkerResult(
            worker=WORKER_NAME,
            status=WorkerStatus.COMMAND_NOT_FOUND,
            workspace=workspace,
            prompt_path=prompt_path,
            status_path=workspace / "status.json",
            command_available=False,
            handoff_command=handoff_command,
            error=f"{cfg.command!r} not found on PATH",
        )
        result.status_path = write_status(workspace, result)
        return result

    argv = [cfg.command, *_SAFE_FLAGS]
    if cfg.model:
        argv.extend(["--model", cfg.model])
    argv.extend(cfg.extra_args)
    if task.files:
        argv.extend(task.files)
    argv.extend(["--message-file", str(prompt_path)])

    output_path = workspace / "output.md"
    error: Optional[str] = None
    exit_code: Optional[int] = None
    try:
        proc = subprocess.run(
            argv,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=cfg.timeout_seconds,
            check=False,
        )
        exit_code = proc.returncode
        output_path.write_text(
            (proc.stdout or "") + (proc.stderr or ""),
            encoding="utf-8",
        )
    except subprocess.TimeoutExpired as exc:
        error = f"timed out after {cfg.timeout_seconds}s"
        output_path.write_text(
            (exc.stdout or "") + (exc.stderr or ""),  # ty: ignore[unsupported-operator]  # dynamic config/plugin path
            encoding="utf-8",
        )
    except OSError as exc:
        error = f"failed to launch {cfg.command!r}: {exc}"

    patch_path, changed_files_path = collect_git_artifacts(workspace, repo_root)

    status = WorkerStatus.EXECUTED if error is None else WorkerStatus.FAILED
    result = WorkerResult(
        worker=WORKER_NAME,
        status=status,
        workspace=workspace,
        prompt_path=prompt_path,
        status_path=workspace / "status.json",
        command_available=True,
        handoff_command=handoff_command,
        output_path=output_path if output_path.exists() else None,
        patch_path=patch_path,
        changed_files_path=changed_files_path,
        exit_code=exit_code,
        error=error,
    )
    result.status_path = write_status(workspace, result)
    return result
