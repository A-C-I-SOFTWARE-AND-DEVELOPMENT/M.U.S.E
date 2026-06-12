"""SIA worker adapter — Hexo Labs' Self-Improving AI as a Hermes worker.

SIA (https://github.com/hexo-ai/sia, MIT) coordinates three agents —
meta, target, and feedback — over successive *generations* to
autonomously improve an agent's scaffold against a task. This adapter
runs that loop **inside an isolation sandbox** (``isolation.py``), so
SIA iterates freely on a *copy* of a target without ever touching the
live runtime. The orchestrator drives it through the standard
five-step contract (``detect → prepare_prompt → run → collect → score``).

Promotion of a winning generation into the live tree is **not** done
here — it is owner-gated via
:mod:`muse_cli.jarvis_prime.sia_self_improve`, which turns a
benchmark-beating candidate into a JARVIS proposal that needs the
owner's authorization. This module only produces and scores candidates
in the sandbox.

SIA is an external CLI (like goose/codex/aider): install it in its own
environment with ``pip install 'sia-agent[claude]'`` and make sure ``sia``
is on ``PATH``. It is deliberately not a Hermes dependency — its pins
conflict with Hermes' locked env. See
``docs/integrations/sia-self-improvement.md``.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from muse_cli.workers.base import (
    WorkerAdapter,
    WorkerArtifacts,
    WorkerDetection,
    WorkerPrompt,
    WorkerRunResult,
    WorkerScore,
    detect_command,
)
from muse_cli.workers.isolation import IsolationError, prepare_workspace
from muse_cli.workers.registry import register
from muse_cli.workers.sia_assets import materialize_task_dir

WORKER_NAME = "sia"
DEFAULT_COMMAND = "sia"

# Keys we try, in order, when extracting a [0,1] score from a generation's
# ``agent_execution.json``. SIA's young schema varies, so we parse tolerantly
# and let the benchmark gate be the authority on baseline-vs-candidate.
_SCORE_KEYS: tuple[str, ...] = (
    "score",
    "final_score",
    "mean_score",
    "accuracy",
    "pass_rate",
    "passrate",
    "success_rate",
    "reward",
)

# Hard ceiling on generations regardless of caller request — bounds cost.
_MAX_GEN_CEILING = 10


@dataclass(frozen=True)
class SiaConfig:
    """Per-invocation knobs for the SIA CLI."""

    command: str = DEFAULT_COMMAND
    backend: str = "claude"  # "claude" | "openhands"
    max_gen: int = 3
    run_id: str = "1"
    meta_model: str = "haiku"
    task_model: str = "claude-haiku-4-5-20251001"
    timeout_seconds: int = 1800
    extra_args: tuple[str, ...] = field(default_factory=tuple)


def _default_runner(argv: list[str], *, cwd: str, timeout: int):
    """Run the SIA CLI. Returns a ``subprocess.CompletedProcess``-like object."""
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


class SiaWorker(WorkerAdapter):
    """Sandboxed self-improvement worker backed by the ``sia`` CLI."""

    id = WORKER_NAME
    display_name = "SIA — Hexo Labs self-improving agent"
    # SIA produces *candidate* scaffolds in a sandbox; turning one into a live
    # change is owner-gated downstream. The candidate-generation step itself is
    # confined to ``.hermes-orchestrator/`` and never edits the live tree.
    requires_approval = True

    def __init__(
        self,
        repo_root: Optional[str] = None,
        config: Optional[SiaConfig] = None,
        runner: Optional[Callable[..., Any]] = None,
    ) -> None:
        self._repo_root = repo_root
        self._config = config or SiaConfig()
        self._runner = runner or _default_runner
        self._runs: dict[str, dict[str, Any]] = {}

    # -- helpers --------------------------------------------------------
    def _root(self) -> Path:
        return Path(self._repo_root) if self._repo_root else Path.cwd()

    @staticmethod
    def _objective(job: Any) -> str:
        return str(
            getattr(job, "prompt", "") or getattr(job, "objective", "") or ""
        ).strip()

    @staticmethod
    def _target_path(job: Any) -> str:
        return str(getattr(job, "target_path", "") or "").strip()

    def _target_name(self, job: Any) -> str:
        tp = self._target_path(job)
        return Path(tp).name if tp else "target"

    @staticmethod
    def _task_name(job: Any) -> str:
        name = str(
            getattr(job, "task", "") or getattr(job, "benchmark", "") or ""
        ).strip()
        return name or "custom"

    @staticmethod
    def _acceptance(job: Any) -> tuple[str, ...]:
        acc = (
            getattr(job, "acceptance_criteria", None)
            or getattr(job, "acceptance", None)
            or ()
        )
        if isinstance(acc, (list, tuple)):
            return tuple(str(x) for x in acc)
        return ()

    def _job_key(self, job: Any) -> str:
        return str(getattr(job, "job_id", None) or self._objective(job) or id(job))

    def _read_baseline(self, job: Any) -> str:
        tp = self._target_path(job)
        if not tp:
            return ""
        p = Path(tp)
        if not p.is_absolute():
            p = self._root() / tp
        try:
            return p.read_text(encoding="utf-8") if p.is_file() else ""
        except OSError:
            return ""

    def _extract_score(self, data: Any) -> Optional[float]:
        """Best-effort [0,1] score from a generation's execution payload."""

        def _scan(d: dict[str, Any]) -> Optional[float]:
            for key in _SCORE_KEYS:
                if key in d:
                    try:
                        v = float(d[key])
                    except (TypeError, ValueError):
                        continue
                    if 1.0 < v <= 100.0:  # looks like a percentage
                        v = v / 100.0
                    return max(0.0, min(1.0, v))
            return None

        if not isinstance(data, dict):
            return None
        found = _scan(data)
        if found is not None:
            return found
        metrics = data.get("metrics")
        if isinstance(metrics, dict):
            return _scan(metrics)
        return None

    def _parse_runs(self, cwd: Path) -> list[dict[str, Any]]:
        runs_root = Path(cwd) / "runs"
        out: list[dict[str, Any]] = []
        if not runs_root.exists():
            return out
        for run_dir in sorted(runs_root.glob("run_*")):
            for gen_dir in sorted(run_dir.glob("gen_*")):
                try:
                    gen_n = int(gen_dir.name.split("_")[-1])
                except ValueError:
                    gen_n = len(out) + 1
                target_agent = gen_dir / "target_agent.py"
                execution = gen_dir / "agent_execution.json"
                improvement = gen_dir / "improvement.md"
                score: Optional[float] = None
                if execution.is_file():
                    try:
                        score = self._extract_score(
                            json.loads(execution.read_text(encoding="utf-8"))
                        )
                    except (OSError, json.JSONDecodeError):
                        score = None
                out.append({
                    "gen": gen_n,
                    "dir": str(gen_dir),
                    "target_agent": str(target_agent) if target_agent.is_file() else "",
                    "execution": str(execution) if execution.is_file() else "",
                    "improvement": str(improvement) if improvement.is_file() else "",
                    "score": score,
                })
        return out

    @staticmethod
    def _best_gen(generations: list[dict[str, Any]]) -> Optional[int]:
        scored = [g for g in generations if isinstance(g.get("score"), (int, float))]
        if not scored:
            return None
        best = max(scored, key=lambda g: float(g["score"]))
        return int(best["gen"])

    # -- WorkerAdapter five-step contract -------------------------------
    def detect(self) -> WorkerDetection:
        cmd = self._config.command
        on_path = detect_command(cmd)
        importable = importlib.util.find_spec("sia") is not None
        if on_path or importable:
            where = shutil.which(cmd) or "import sia"
            return WorkerDetection(
                available=True,
                version="",
                reason=f"SIA available ({where})",
                details={"backend": self._config.backend},
            )
        return WorkerDetection(
            available=False,
            reason="SIA not installed",
            details={
                "install": "pip install 'sia-agent[claude]' (external CLI; put `sia` on PATH)",
                "docs": "docs/integrations/sia-self-improvement.md",
            },
        )

    def prepare_prompt(self, job: Any) -> WorkerPrompt:
        return WorkerPrompt(
            text=self._objective(job),
            role="self-improve-target",
            metadata={
                "target_path": self._target_path(job),
                "task": self._task_name(job),
                "max_gen": min(self._config.max_gen, _MAX_GEN_CEILING),
            },
        )

    def run(self, job: Any) -> WorkerRunResult:
        objective = self._objective(job)
        if not objective:
            return WorkerRunResult(ok=False, error="empty objective")

        cfg = self._config
        repo = self._root()
        t0 = time.monotonic()

        try:
            workspace = prepare_workspace(
                repo,
                job_id=str(getattr(job, "job_id", None) or "sia-job"),
                worker_id=self.id,
                metadata={
                    "objective": objective,
                    "target_path": self._target_path(job),
                    "task": self._task_name(job),
                },
            )
        except IsolationError as exc:
            return WorkerRunResult(
                ok=False,
                error=f"sandbox setup failed: {exc}",
                duration_seconds=time.monotonic() - t0,
            )

        task_dir = workspace.root / "task"
        materialize_task_dir(
            task_dir,
            objective=objective,
            target_name=self._target_name(job),
            baseline_code=self._read_baseline(job),
            acceptance=self._acceptance(job),
        )

        max_gen = max(1, min(cfg.max_gen, _MAX_GEN_CEILING))
        argv = [
            cfg.command,
            "--task_dir",
            str(task_dir),
            "--max_gen",
            str(max_gen),
            "--run_id",
            str(cfg.run_id),
            "--backend",
            cfg.backend,
            "--meta_model",
            cfg.meta_model,
            "--task_model",
            cfg.task_model,
            *cfg.extra_args,
        ]
        cwd = workspace.working_dir()

        error: Optional[str] = None
        exit_code: Optional[int] = None
        stdout = ""
        stderr = ""
        try:
            proc = self._runner(argv, cwd=str(cwd), timeout=cfg.timeout_seconds)
            exit_code = getattr(proc, "returncode", None)
            stdout = getattr(proc, "stdout", "") or ""
            stderr = getattr(proc, "stderr", "") or ""
        except subprocess.TimeoutExpired:
            error = f"sia timed out after {cfg.timeout_seconds}s"
        except FileNotFoundError:
            error = f"{cfg.command!r} not found on PATH"
        except OSError as exc:
            error = f"failed to launch {cfg.command!r}: {exc}"

        # Persist logs inside the sandbox (never outside).
        try:
            workspace.stdout_log.write_text(stdout, encoding="utf-8")
            workspace.stderr_log.write_text(stderr, encoding="utf-8")
        except OSError:
            pass

        generations = self._parse_runs(cwd)
        self._runs[self._job_key(job)] = {
            "workspace": workspace,
            "task_dir": task_dir,
            "cwd": cwd,
            "generations": generations,
            "error": error,
            "exit_code": exit_code,
        }

        ok = error is None and (exit_code in (0, None)) and bool(generations)
        return WorkerRunResult(
            ok=ok,
            exit_code=int(exit_code) if isinstance(exit_code, int) else 0,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=time.monotonic() - t0,
            error=error or "",
            details={
                "workspace": str(workspace.root),
                "generations": len(generations),
                "best_gen": self._best_gen(generations),
            },
        )

    def collect(self, job: Any) -> WorkerArtifacts:
        ctx = self._runs.get(self._job_key(job))
        if not ctx:
            return WorkerArtifacts(notes="no SIA run recorded for this job")
        generations = ctx["generations"]
        workspace = ctx["workspace"]
        files = tuple(g["target_agent"] for g in generations if g["target_agent"])
        logs = (str(workspace.stdout_log), str(workspace.stderr_log))
        best_gen = self._best_gen(generations)
        return WorkerArtifacts(
            files=files,
            logs=logs,
            workspace_path=str(workspace.root),
            notes=f"{len(generations)} generation(s); best gen={best_gen}",
            details={
                "generations": generations,
                "best_gen": best_gen,
                "task_dir": str(ctx["task_dir"]),
                "error": ctx["error"],
            },
        )

    def score(self, artifacts: WorkerArtifacts) -> WorkerScore:
        generations = (artifacts.details or {}).get("generations") or []
        scored = [
            (g["gen"], float(g["score"]))
            for g in generations
            if isinstance(g.get("score"), (int, float))
        ]
        if not scored:
            return WorkerScore(
                value=0.0,
                confidence=0.0,
                rationale="no parsable generation scores",
            )
        best = max(s for _, s in scored)
        components = {f"gen_{n}": max(0.0, min(1.0, s)) for n, s in scored}
        return WorkerScore(
            value=max(0.0, min(1.0, best)),
            confidence=min(1.0, len(scored) / max(1, len(generations))),
            rationale=f"best of {len(scored)} scored generation(s)",
            components=components,
        )


# Self-register on import so the orchestrator can dispatch to it. ``replace``
# keeps re-imports (tests, reloads) idempotent.
register(SiaWorker(), replace=True)
