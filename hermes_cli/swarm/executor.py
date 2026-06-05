"""Real per-grain execution — each grain runs as its own specialized LLM.

``PromptOnlyExecutor`` (in ``coordinator``) is the safe default: it isolates and
materialises each grain's spec but launches no model. This module is the
*acting* counterpart: :class:`AgentExecutor` actually spawns the specialized
:class:`AIAgent` for each grain (via :func:`specialist.spawn_agent`), runs it in
the grain's isolated git worktree, and writes the scoring artifacts
(``output.md`` / ``patch.diff`` / ``changed-files.txt`` / ``validation-output.txt``
/ ``status.json`` / ``usage.json``) the convergence layer consumes.

The model call lives behind an injectable :class:`AgentRunner` seam, so the
executor's orchestration (worktree provisioning, parallelism, artifact writing,
result mapping) is unit-testable without a network. The default runner lazily
imports the agent runtime and emits a usage sidecar so per-job cost metering
works exactly as for any other Hermes worker.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol, Sequence
import json
import subprocess

from hermes_cli.swarm.grain import Grain, SwarmPlan, now_iso
from hermes_cli.swarm.specialist import GrainAgentSpec
from hermes_cli.swarm.coordinator import SwarmGrainResult

__all__ = [
    "GrainRunOutput",
    "AgentRunner",
    "DefaultAgentRunner",
    "AgentExecutor",
]


@dataclass
class GrainRunOutput:
    """What a single grain run produced — mapped onto scoring artifacts."""

    output_md: str = ""
    patch_diff: str = ""
    changed_files: tuple[str, ...] = ()
    validation_output: str = ""
    status: dict[str, Any] = field(default_factory=dict)
    usage: Optional[dict[str, Any]] = None
    success: bool = True
    error: Optional[str] = None


class AgentRunner(Protocol):
    """Runs one grain's specialized agent in ``workdir`` and returns its output."""

    def run(self, spec: GrainAgentSpec, workdir: Path, grain: Grain) -> GrainRunOutput: ...


class DefaultAgentRunner:
    """Spawn the grain's specialized :class:`AIAgent` and run it in its worktree.

    Captures the working-tree diff as ``patch.diff``, runs the grain's
    verification commands for ``validation-output.txt``, and folds the agent's
    token usage into a ``usage.json`` sidecar. Lazily imports the agent runtime,
    so importing this module never drags in the model stack.
    """

    def __init__(self, *, run_verification: bool = True) -> None:
        self.run_verification = run_verification

    def run(self, spec: GrainAgentSpec, workdir: Path, grain: Grain) -> GrainRunOutput:
        from hermes_cli.swarm.specialist import spawn_agent

        agent = spawn_agent(spec)
        task = f"{grain.intent}\n\nWork only within: {', '.join(grain.domain.globs)}"
        try:
            reply = agent.chat(task)
            success = True
            error = None
        except Exception as exc:  # a model/runtime failure is a grain failure
            reply = ""
            success = False
            error = repr(exc)

        patch = _git_diff(workdir)
        changed = _git_changed_files(workdir)
        validation = ""
        if self.run_verification and grain.verification_plan:
            validation, vok = _run_commands(workdir, grain.verification_plan)
            success = success and vok

        usage = _extract_usage(agent)
        return GrainRunOutput(
            output_md=reply or "",
            patch_diff=patch,
            changed_files=changed,
            validation_output=validation,
            status={
                "success": success,
                "model": spec.model_lane,
                "grain_id": grain.grain_id,
                "ended_at": now_iso(),
            },
            usage=usage,
            success=success,
            error=error,
        )


class AgentExecutor:
    """Runs each grain as its own specialized LLM in an isolated worktree.

    Grains run in a bounded thread pool (default mirrors the safe concurrency
    cap). Each grain's artifacts are written into its worktree so the
    convergence layer (:mod:`hermes_cli.swarm.converge`) can score/merge them.
    """

    def __init__(
        self,
        *,
        agent_runner: Optional[AgentRunner] = None,
        concurrency: int = 2,
        max_concurrency: int = 8,
        use_worktrees: bool = True,
        base_ref: Optional[str] = None,
    ) -> None:
        self.agent_runner = agent_runner or DefaultAgentRunner()
        self.concurrency = max(1, min(concurrency, max_concurrency))
        self.use_worktrees = use_worktrees
        self.base_ref = base_ref

    def run(
        self, repo: Path, plan: SwarmPlan, specs: dict[str, GrainAgentSpec]
    ) -> list[SwarmGrainResult]:
        repo = Path(repo)
        worktrees = self._provision(repo, plan) if self.use_worktrees else {}

        results: dict[str, SwarmGrainResult] = {
            g.grain_id: SwarmGrainResult(grain_id=g.grain_id, state="pending")
            for g in plan.grains
        }

        def _one(grain: Grain) -> None:
            res = results[grain.grain_id]
            res.started_at = now_iso()
            workdir = worktrees.get(grain.grain_id, repo)
            res.worktree_path = str(workdir)
            try:
                out = self.agent_runner.run(specs[grain.grain_id], workdir, grain)
            except Exception as exc:  # runner crash → failed grain, never raises out
                res.state = "failed"
                res.error = f"runner exception: {exc!r}"
                res.ended_at = now_iso()
                return
            _write_artifacts(workdir, out)
            res.state = "completed" if out.success else "failed"
            res.error = out.error
            res.ended_at = now_iso()

        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            futures = [pool.submit(_one, g) for g in plan.grains]
            for fut in as_completed(futures):
                fut.result()  # _one swallows its own errors; this re-raises bugs

        return [results[g.grain_id] for g in plan.grains]

    def _provision(self, repo: Path, plan: SwarmPlan) -> dict[str, Path]:
        from hermes_cli import worktrees as wt

        out: dict[str, Path] = {}
        for grain in plan.grains:
            info = wt.create_worktree(
                repo,
                job_id=plan.job_id,
                worker_id=grain.grain_id,
                base_ref=self.base_ref,
                extra_metadata={"intent": grain.intent, "lane": grain.model_lane},
            )
            out[grain.grain_id] = Path(info.path)
        return out


# ---------------------------------------------------------------------------
# Artifact writing + git helpers
# ---------------------------------------------------------------------------


def _write_artifacts(workdir: Path, out: GrainRunOutput) -> None:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "output.md").write_text(out.output_md or "", encoding="utf-8")
    (workdir / "patch.diff").write_text(out.patch_diff or "", encoding="utf-8")
    (workdir / "changed-files.txt").write_text(
        "\n".join(out.changed_files) + ("\n" if out.changed_files else ""),
        encoding="utf-8",
    )
    (workdir / "validation-output.txt").write_text(
        out.validation_output or "", encoding="utf-8"
    )
    (workdir / "status.json").write_text(
        json.dumps(out.status, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if out.usage is not None:
        (workdir / "usage.json").write_text(
            json.dumps(out.usage, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def _git(workdir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(workdir),
        capture_output=True,
        text=True,
        check=False,
    )


def _git_diff(workdir: Path) -> str:
    try:
        proc = _git(workdir, "add", "-A")
        proc = _git(workdir, "diff", "--cached")
        return proc.stdout if proc.returncode == 0 else ""
    except OSError:
        return ""


def _git_changed_files(workdir: Path) -> tuple[str, ...]:
    try:
        proc = _git(workdir, "diff", "--cached", "--name-only")
        if proc.returncode != 0:
            return ()
        return tuple(l.strip() for l in proc.stdout.splitlines() if l.strip())
    except OSError:
        return ()


def _run_commands(workdir: Path, commands: Sequence[str]) -> tuple[str, bool]:
    chunks: list[str] = []
    ok = True
    for cmd in commands:
        try:
            proc = subprocess.run(
                cmd, cwd=str(workdir), shell=True, capture_output=True, text=True,
                check=False, timeout=300,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            chunks.append(f"$ {cmd}\n[error launching: {exc!r}]")
            ok = False
            continue
        chunks.append(f"$ {cmd}\n{proc.stdout}{proc.stderr}")
        if proc.returncode != 0:
            ok = False
    return "\n\n".join(chunks), ok


def _extract_usage(agent: Any) -> Optional[dict[str, Any]]:
    try:
        from agent.conversation_loop import build_usage_record

        record = build_usage_record(getattr(agent, "last_result", None) or agent)
        if isinstance(record, dict):
            return record
    except Exception:
        pass
    return None
