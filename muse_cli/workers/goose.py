"""Goose worker adapter.

Goose (Block) is best for local agent recipes, provider experiments,
extension-driven tasks, and desktop/CLI workflows. This adapter:

1. Detects whether the ``goose`` CLI is installed.
2. Writes a worker-tuned ``prompt.md`` into the workspace.
3. Defaults to **handoff-required** — the user runs ``goose`` manually
   with the prepared prompt or recipe.
4. When ``execute=True`` and the binary is available, invokes
   ``goose run`` non-interactively with conservative defaults.
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

WORKER_NAME = "goose"
DEFAULT_COMMAND = "goose"

# Goose's ``run`` subcommand accepts an instructions file with
# ``--instructions PATH`` and runs in non-interactive mode. We
# explicitly do **not** auto-approve tool calls; the user has to opt in.
_SAFE_RUN_FLAGS: tuple[str, ...] = (
    "--no-session",
)


@dataclass(frozen=True)
class GooseConfig:
    """Knobs the caller can override per invocation."""

    command: str = DEFAULT_COMMAND
    recipe: Optional[str] = None
    extensions: tuple[str, ...] = field(default_factory=tuple)
    extra_args: tuple[str, ...] = field(default_factory=tuple)
    timeout_seconds: int = 900


def render_prompt(task: WorkerTask) -> str:
    """Build the worker-tuned ``prompt.md`` body for Goose."""
    title = task.title.strip() or "Untitled task"
    instructions = task.instructions.strip() or "(no instructions provided)"
    body = (
        f"# {title}\n\n"
        "You are running inside the Goose CLI. Goose is best when you"
        " can lean on a recipe or an extension to do the work — favor"
        " existing extensions over ad-hoc shell. Treat this workspace as"
        " a sandbox; do not push, force-update, or modify shared"
        " infrastructure.\n\n"
        "## Task\n"
        f"{instructions}\n"
        + render_files_block(task.files)
        + render_context_block(task.context)
        + render_acceptance_block(task.acceptance_criteria)
        + "\n## Guardrails\n"
        "- No destructive shell commands (``rm -rf``, ``git reset --hard``,"
        " ``git push --force``).\n"
        "- Do not auto-approve tool calls; ask the human if a tool needs"
        " elevated permissions.\n"
        "- If a needed extension is missing, list what would unlock the"
        " task instead of installing silently.\n"
        "- If the task is ambiguous, ask one focused question.\n"
    )
    return body


def build_handoff_command(
    config: GooseConfig,
    workspace: Path,
) -> str:
    """Return a copy-pasteable ``goose`` invocation for manual handoff."""
    parts = [config.command, "run", *_SAFE_RUN_FLAGS]
    if config.recipe:
        parts.extend(["--recipe", config.recipe])
    for ext in config.extensions:
        parts.extend(["--with-extension", ext])
    parts.extend(config.extra_args)
    prompt_path = (workspace / "prompt.md").as_posix()
    parts.extend(["--instructions", prompt_path])
    return " ".join(parts)


def run(
    task: WorkerTask,
    workspace: Path,
    *,
    execute: bool = False,
    repo_root: Optional[Path] = None,
    config: Optional[GooseConfig] = None,
) -> WorkerResult:
    """Prepare (and optionally execute) a Goose run.

    ``execute=False`` (default) is the handoff path: prompt + status are
    written and the user runs Goose manually. ``execute=True`` requires
    the ``goose`` binary on ``$PATH``; missing binaries fall back to
    ``COMMAND_NOT_FOUND`` rather than crashing.
    """
    cfg = config or GooseConfig()
    workspace = ensure_workspace(workspace)
    repo_root = (repo_root or Path.cwd()).resolve()

    prompt_body = render_prompt(task)
    prompt_path = write_prompt(workspace, prompt_body)
    available = detect_command(cfg.command)
    handoff_command = build_handoff_command(cfg, workspace)

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

    argv = [cfg.command, "run", *_SAFE_RUN_FLAGS]
    if cfg.recipe:
        argv.extend(["--recipe", cfg.recipe])
    for ext in cfg.extensions:
        argv.extend(["--with-extension", ext])
    argv.extend(cfg.extra_args)
    argv.extend(["--instructions", str(prompt_path)])

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
