"""Codex worker adapter (handoff-first, opt-in execution).

This module is the local-side glue between Hermes' orchestrator and the
**official** Codex CLI (``codex``) that ships from OpenAI. Its job is
narrow on purpose:

* Detect whether ``codex`` is installed on the host (without crashing if
  it isn't, and without inspecting any process state we don't own).
* Materialize a high-quality, structured implementation prompt and a
  matching ``status.json`` on disk under ``<workspace>/workers/codex/``.
* Default to **handoff-required** mode — the user copies the prompt into
  whatever official Codex surface they're already signed into, then drops
  the resulting artifacts back into the worker directory. We do not call
  ``chatgpt.com``, do not scrape cookies, do not automate web UI, do not
  proxy a subscription.
* When (and only when) the operator has explicitly opted in *and* the
  local ``codex`` CLI is present, optionally invoke the official CLI as a
  subprocess and collect the standard set of output artifacts.

Outputs collected at the end of a run:

* ``output.md``         — narrative report from the worker
* ``patch.diff``        — unified diff of all proposed edits
* ``changed-files.txt`` — newline-delimited list of modified paths
* ``test-output.txt``   — captured stdout/stderr of validation commands
* ``status.json``       — machine-readable run status

The adapter is dependency-free beyond the standard library so it works in
the same environments Hermes itself supports (Linux, macOS, Windows,
Termux). It never imports the Hermes core — orchestrators call into it,
not the other way around.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)

WORKER_NAME = "codex"
DEFAULT_WORKER_SUBDIR = Path("workers") / WORKER_NAME

PROMPT_FILENAME = "prompt.md"
STATUS_FILENAME = "status.json"
OUTPUT_FILENAME = "output.md"
PATCH_FILENAME = "patch.diff"
CHANGED_FILES_FILENAME = "changed-files.txt"
TEST_OUTPUT_FILENAME = "test-output.txt"

# Operators flip this to actually shell out to ``codex``. Default is off;
# silent execution of an external coding agent is exactly the kind of
# surprise this adapter exists to avoid.
EXECUTE_ENV_VAR = "HERMES_CODEX_WORKER_EXECUTE"

# Mode strings recorded in status.json.
MODE_HANDOFF = "handoff-required"
MODE_EXECUTED = "executed"
MODE_EXECUTION_FAILED = "execution-failed"


# ── data classes ───────────────────────────────────────────────────────────


@dataclass
class CodexDetection:
    """Result of probing the local machine for the official Codex CLI."""

    available: bool
    path: Optional[str] = None
    version: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "path": self.path,
            "version": self.version,
            "error": self.error,
        }


@dataclass
class CodexTask:
    """Structured description of one implementation task for Codex.

    All fields are optional except ``mission`` and ``task`` so callers can
    supply only the evidence they actually have. The prompt builder formats
    every supplied field into a well-labeled section so the worker can read
    it without parsing markdown semantically.
    """

    mission: str
    task: str
    repo_evidence: str = ""
    files_to_inspect: Sequence[str] = field(default_factory=list)
    files_likely_to_edit: Sequence[str] = field(default_factory=list)
    acceptance_criteria: Sequence[str] = field(default_factory=list)
    validation_commands: Sequence[str] = field(default_factory=list)
    do_not_change: Sequence[str] = field(default_factory=list)
    notes: str = ""
    task_id: Optional[str] = None


@dataclass
class CodexRunResult:
    """Outcome of :func:`run_worker`."""

    mode: str
    detection: CodexDetection
    workdir: Path
    prompt_path: Path
    status_path: Path
    artifacts: dict = field(default_factory=dict)
    returncode: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "detection": self.detection.to_dict(),
            "workdir": str(self.workdir),
            "prompt_path": str(self.prompt_path),
            "status_path": str(self.status_path),
            "artifacts": {name: str(path) for name, path in self.artifacts.items()},
            "returncode": self.returncode,
            "error": self.error,
        }


# ── detection ──────────────────────────────────────────────────────────────


def detect_codex(
    *,
    command: str = "codex",
    timeout: float = 3.0,
    env: Optional[Mapping[str, str]] = None,
) -> CodexDetection:
    """Detect the official local Codex CLI.

    Equivalent to ``command -v codex`` followed by a defensive ``--version``
    probe. Never raises: a missing binary, a crash inside the binary, or a
    timeout all return ``available=False`` with the failure recorded so the
    caller can log it and continue.
    """

    path = shutil.which(command)
    if not path:
        return CodexDetection(available=False, error=f"{command!r} not found on PATH")

    version: Optional[str] = None
    version_error: Optional[str] = None
    try:
        proc = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=dict(env) if env is not None else None,
            check=False,
        )
        candidate = (proc.stdout or proc.stderr or "").strip().splitlines()
        if candidate:
            version = candidate[0].strip() or None
        if proc.returncode != 0 and not version:
            version_error = (
                f"`{command} --version` exited with {proc.returncode}"
            )
    except (subprocess.TimeoutExpired, OSError) as exc:
        version_error = f"version probe failed: {exc}"
    except Exception as exc:  # pragma: no cover - defensive
        version_error = f"unexpected error probing version: {exc}"

    return CodexDetection(
        available=True,
        path=path,
        version=version,
        error=version_error,
    )


# ── prompt construction ────────────────────────────────────────────────────


def _format_bullets(items: Iterable[str]) -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        return "_(none provided)_"
    return "\n".join(f"- {entry}" for entry in cleaned)


def build_prompt(task: CodexTask) -> str:
    """Format ``task`` as the structured markdown prompt Codex consumes."""

    mission = task.mission.strip() or "(no mission supplied)"
    implementation = task.task.strip() or "(no implementation task supplied)"
    evidence = task.repo_evidence.strip() or "_(no repository evidence summary supplied)_"
    notes = task.notes.strip()

    sections = [
        "# Codex Worker — Implementation Task",
        "",
        "You are running as the **Codex worker** invoked by the muse local",
        "orchestrator. Follow this prompt literally. Do not invent extra",
        "scope, do not refactor unrelated code, and do not skip the output",
        "contract at the bottom — the orchestrator parses those files.",
        "",
        "## Mission",
        "",
        mission,
        "",
        "## Repository evidence",
        "",
        evidence,
        "",
        "## Files to inspect",
        "",
        _format_bullets(task.files_to_inspect),
        "",
        "## Files likely to edit",
        "",
        _format_bullets(task.files_likely_to_edit),
        "",
        "## Exact implementation task",
        "",
        implementation,
        "",
        "## Acceptance criteria",
        "",
        _format_bullets(task.acceptance_criteria),
        "",
        "## Validation commands",
        "",
        _format_bullets(task.validation_commands),
        "",
        "## What NOT to change",
        "",
        _format_bullets(task.do_not_change),
    ]

    if notes:
        sections.extend(["", "## Additional notes", "", notes])

    sections.extend([
        "",
        "## Output contract",
        "",
        "Write every artifact below into the worker directory the",
        "orchestrator handed you. Do not skip any of them — even on",
        "failure, emit the file with a short note explaining what",
        "happened so the orchestrator can read the result.",
        "",
        f"- `{OUTPUT_FILENAME}` — narrative report (what you did, what you",
        "  tried, anything you deferred and why).",
        f"- `{PATCH_FILENAME}` — unified diff of every edit (`git diff`",
        "  against the starting commit). Empty file if no changes.",
        f"- `{CHANGED_FILES_FILENAME}` — newline-delimited list of paths",
        "  you modified. Empty file if no changes.",
        f"- `{TEST_OUTPUT_FILENAME}` — captured stdout/stderr of the",
        "  validation commands above. Include exit codes.",
        f"- `{STATUS_FILENAME}` — JSON document with at minimum",
        '  `{"status": "success"|"failed"|"deferred", "summary": "..."}`.',
        "",
        "If a validation command fails, record that honestly in",
        f"`{STATUS_FILENAME}` and `{OUTPUT_FILENAME}` rather than silently",
        "papering over it.",
        "",
    ])

    return "\n".join(sections).rstrip() + "\n"


# ── workspace materialization ──────────────────────────────────────────────


def _ensure_workdir(workspace: Path, *, subdir: Path = DEFAULT_WORKER_SUBDIR) -> Path:
    workdir = (workspace / subdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _initial_status(
    *,
    task: CodexTask,
    detection: CodexDetection,
    mode: str,
    workdir: Path,
    prompt_path: Path,
) -> dict:
    return {
        "worker": WORKER_NAME,
        "mode": mode,
        "status": "pending" if mode == MODE_HANDOFF else "running",
        "created_at": _now_iso(),
        "task_id": task.task_id,
        "mission": task.mission.strip() or None,
        "detection": detection.to_dict(),
        "workdir": str(workdir),
        "prompt_path": str(prompt_path),
        "expected_artifacts": [
            OUTPUT_FILENAME,
            PATCH_FILENAME,
            CHANGED_FILES_FILENAME,
            TEST_OUTPUT_FILENAME,
            STATUS_FILENAME,
        ],
        "instructions": (
            "Hand the contents of prompt.md to the official Codex CLI or "
            "Codex surface you are signed into. After Codex finishes, drop "
            "the five output files listed above into this directory so the "
            "muse orchestrator can collect them."
            if mode == MODE_HANDOFF
            else "Codex CLI execution requested by operator; see status updates after the run."
        ),
    }


def write_prompt_and_status(
    task: CodexTask,
    workspace: Path,
    *,
    detection: Optional[CodexDetection] = None,
    mode: str = MODE_HANDOFF,
    subdir: Path = DEFAULT_WORKER_SUBDIR,
) -> tuple[Path, Path]:
    """Materialize ``prompt.md`` and ``status.json`` for the worker."""

    if detection is None:
        detection = detect_codex()

    workdir = _ensure_workdir(workspace, subdir=subdir)
    prompt_path = workdir / PROMPT_FILENAME
    status_path = workdir / STATUS_FILENAME

    prompt_path.write_text(build_prompt(task), encoding="utf-8")
    status_payload = _initial_status(
        task=task,
        detection=detection,
        mode=mode,
        workdir=workdir,
        prompt_path=prompt_path,
    )
    status_path.write_text(
        json.dumps(status_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return prompt_path, status_path


# ── artifact collection ────────────────────────────────────────────────────


_ARTIFACT_FILENAMES: tuple[str, ...] = (
    OUTPUT_FILENAME,
    PATCH_FILENAME,
    CHANGED_FILES_FILENAME,
    TEST_OUTPUT_FILENAME,
    STATUS_FILENAME,
)


def collect_artifacts(workdir: Path) -> dict[str, Path]:
    """Return a mapping of artifact name → path for every artifact present."""

    found: dict[str, Path] = {}
    for name in _ARTIFACT_FILENAMES:
        candidate = workdir / name
        if candidate.is_file():
            found[name] = candidate
    return found


def _update_status(
    status_path: Path,
    *,
    mode: str,
    status: str,
    returncode: Optional[int] = None,
    error: Optional[str] = None,
    extra: Optional[Mapping[str, object]] = None,
) -> None:
    payload: dict[str, object] = {}
    if status_path.is_file():
        try:
            payload = json.loads(status_path.read_text(encoding="utf-8") or "{}")
            if not isinstance(payload, dict):
                payload = {}
        except (OSError, json.JSONDecodeError):
            payload = {}
    payload["worker"] = WORKER_NAME
    payload["mode"] = mode
    payload["status"] = status
    payload["updated_at"] = _now_iso()
    if returncode is not None:
        payload["returncode"] = returncode
    if error is not None:
        payload["error"] = error
    if extra:
        for key, value in extra.items():
            payload[key] = value
    status_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# ── execution ──────────────────────────────────────────────────────────────


def _execution_enabled(env: Optional[Mapping[str, str]]) -> bool:
    raw = (env if env is not None else os.environ).get(EXECUTE_ENV_VAR, "")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def run_worker(
    task: CodexTask,
    workspace: Path,
    *,
    execute: Optional[bool] = None,
    subdir: Path = DEFAULT_WORKER_SUBDIR,
    env: Optional[Mapping[str, str]] = None,
    timeout: Optional[float] = None,
    extra_codex_args: Optional[Sequence[str]] = None,
) -> CodexRunResult:
    """Prepare (and optionally execute) a Codex worker invocation.

    Default behavior is **handoff-required**: write ``prompt.md`` and
    ``status.json`` under ``workers/codex/``, then return so the operator
    can drive Codex themselves. Execution only happens when the caller
    passes ``execute=True`` (or sets ``HERMES_CODEX_WORKER_EXECUTE=1``)
    AND the local ``codex`` CLI is detected. We deliberately do not fall
    back to web automation or subscription proxying.
    """

    workspace = Path(workspace)
    detection = detect_codex(env=env)

    if execute is None:
        execute = _execution_enabled(env)

    initial_mode = MODE_EXECUTED if (execute and detection.available) else MODE_HANDOFF
    prompt_path, status_path = write_prompt_and_status(
        task,
        workspace,
        detection=detection,
        mode=initial_mode,
        subdir=subdir,
    )
    workdir = prompt_path.parent

    result = CodexRunResult(
        mode=initial_mode,
        detection=detection,
        workdir=workdir,
        prompt_path=prompt_path,
        status_path=status_path,
    )

    if initial_mode == MODE_HANDOFF:
        # Either execution wasn't requested, or codex isn't installed.
        if execute and not detection.available:
            result.error = (
                "Codex CLI execution requested but the official `codex` "
                "binary was not found on PATH; falling back to handoff."
            )
            _update_status(
                status_path,
                mode=MODE_HANDOFF,
                status="pending",
                error=result.error,
            )
        result.artifacts = collect_artifacts(workdir)
        return result

    # Execution path. Codex CLI is present and the operator opted in.
    assert detection.path is not None  # narrowed by detection.available
    cmd: List[str] = [detection.path]
    if extra_codex_args:
        cmd.extend(extra_codex_args)

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=dict(env) if env is not None else None,
            input=prompt_path.read_text(encoding="utf-8"),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        result.mode = MODE_EXECUTION_FAILED
        result.error = f"codex CLI timed out after {exc.timeout}s"
        _update_status(
            status_path,
            mode=MODE_EXECUTION_FAILED,
            status="failed",
            error=result.error,
        )
        result.artifacts = collect_artifacts(workdir)
        return result
    except (OSError, subprocess.SubprocessError) as exc:
        result.mode = MODE_EXECUTION_FAILED
        result.error = f"codex CLI failed to start: {exc}"
        _update_status(
            status_path,
            mode=MODE_EXECUTION_FAILED,
            status="failed",
            error=result.error,
        )
        result.artifacts = collect_artifacts(workdir)
        return result

    # The CLI may stream its own artifacts straight to the workdir; we also
    # capture stdout/stderr so the orchestrator never loses run output.
    stdout_log = workdir / "codex.stdout.log"
    stderr_log = workdir / "codex.stderr.log"
    stdout_log.write_text(proc.stdout or "", encoding="utf-8")
    stderr_log.write_text(proc.stderr or "", encoding="utf-8")

    result.returncode = proc.returncode
    run_status = "success" if proc.returncode == 0 else "failed"
    if proc.returncode != 0:
        result.mode = MODE_EXECUTION_FAILED
        result.error = (
            f"codex CLI exited with {proc.returncode}; see codex.stderr.log"
        )
    _update_status(
        status_path,
        mode=result.mode,
        status=run_status,
        returncode=proc.returncode,
        error=result.error,
        extra={
            "stdout_log": str(stdout_log),
            "stderr_log": str(stderr_log),
        },
    )
    result.artifacts = collect_artifacts(workdir)
    return result


__all__ = [
    "CodexDetection",
    "CodexRunResult",
    "CodexTask",
    "MODE_EXECUTED",
    "MODE_EXECUTION_FAILED",
    "MODE_HANDOFF",
    "WORKER_NAME",
    "build_prompt",
    "collect_artifacts",
    "detect_codex",
    "run_worker",
    "write_prompt_and_status",
]
