"""Real per-grain execution that drives a user-specified model endpoint.

The default :class:`hermes_cli.swarm.coordinator.PromptOnlyExecutor` is the safe
"decide, don't act" executor: it isolates each grain in a git worktree and
materialises its specialized prompt + token-juice context, but it never launches
a model. This module provides the *acting* counterpart that targets an
explicit, caller-supplied inference endpoint.

:class:`AIAgentExecutor` implements the :class:`GrainExecutor` protocol. It
takes a ``base_url`` / ``api_key`` / ``model`` / ``provider`` quadruple and
spawns a real :class:`run_agent.AIAgent` per grain, driven by the grain's
specialist system prompt and the swarm goal. Output is written into the
grain's isolated worktree (``output.md``, ``status.json``) so the convergence
layer and audit trail keep working unchanged.

The class is intentionally small and self-contained — it does not depend on
:class:`hermes_cli.swarm.executor.AgentExecutor` so a caller wiring a custom
endpoint (Kimi, OpenRouter, vLLM, ...) can do so without dragging in the
multi-agent worktree fan-out that already has its own
:func:`specialist.spawn_agent` codepath.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
import json

from hermes_cli.swarm.grain import Grain, SwarmPlan, now_iso
from hermes_cli.swarm.specialist import GrainAgentSpec

if TYPE_CHECKING:
    from hermes_cli.swarm.coordinator import SwarmGrainResult

__all__ = [
    "AIAgentExecutor",
    "AIAgentExecutorConfig",
]


@dataclass
class AIAgentExecutorConfig:
    """Configuration for :class:`AIAgentExecutor`.

    All four credentials are required to actually launch the model; if any are
    missing the executor will refuse to construct rather than silently falling
    back to the prompt-only path.
    """

    base_url: str
    api_key: str
    model: str
    provider: str
    max_iterations: int = 25
    concurrency: int = 2
    max_concurrency: int = 8
    use_worktrees: bool = True
    base_ref: Optional[str] = None
    quiet_mode: bool = True
    timeout_seconds: float = 600.0


class AIAgentExecutor:
    """Spawn a real :class:`run_agent.AIAgent` per grain against a user endpoint.

    Each grain gets:

    * an isolated git worktree (physical non-overlap backstop);
    * a specialized system prompt assembled from
      :func:`specialist.build_grain_agent_spec` (file-domain + acceptance +
      verification + owner-gate copy);
    * its own :class:`run_agent.AIAgent` configured with the caller-supplied
      ``base_url`` / ``api_key`` / ``model`` / ``provider`` so all grains in
      the same swarm run against the same endpoint with consistent auth;
    * an ``output.md`` artifact written into its worktree carrying the model's
      final reply, plus a ``status.json`` describing the run.

    The executor returns a :class:`SwarmGrainResult` per grain with
    ``state`` of ``"completed"`` or ``"failed"`` and ``error`` populated on
    failure. A model/runner exception is captured per-grain — it never
    aborts the whole swarm.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        provider: str,
        max_iterations: int = 25,
        concurrency: int = 2,
        max_concurrency: int = 8,
        use_worktrees: bool = True,
        base_ref: Optional[str] = None,
        quiet_mode: bool = True,
        timeout_seconds: float = 600.0,
    ) -> None:
        if not base_url:
            raise ValueError("AIAgentExecutor requires a non-empty base_url")
        if not api_key:
            raise ValueError("AIAgentExecutor requires a non-empty api_key")
        if not model:
            raise ValueError("AIAgentExecutor requires a non-empty model")
        if not provider:
            raise ValueError("AIAgentExecutor requires a non-empty provider")

        self.config = AIAgentExecutorConfig(
            base_url=base_url,
            api_key=api_key,
            model=model,
            provider=provider,
            max_iterations=max_iterations,
            concurrency=max(1, min(int(concurrency), int(max_concurrency))),
            max_concurrency=int(max_concurrency),
            use_worktrees=use_worktrees,
            base_ref=base_ref,
            quiet_mode=quiet_mode,
            timeout_seconds=float(timeout_seconds),
        )

    # ------------------------------------------------------------------ protocol
    def run(
        self,
        repo: Path,
        plan: SwarmPlan,
        specs: dict[str, GrainAgentSpec],
    ) -> list["SwarmGrainResult"]:
        from hermes_cli.swarm.coordinator import SwarmGrainResult  # local import: avoid cycle

        repo = Path(repo)
        worktrees = self._provision(repo, plan) if self.config.use_worktrees else {}

        results: dict[str, SwarmGrainResult] = {
            g.grain_id: SwarmGrainResult(grain_id=g.grain_id, state="pending")
            for g in plan.grains
        }

        def _one(grain: Grain) -> None:
            res = results[grain.grain_id]
            res.started_at = now_iso()
            placement = worktrees.get(grain.grain_id)
            workdir = Path(placement[0]) if placement else repo
            res.worktree_path = str(workdir)
            if placement:
                res.branch = placement[1]

            spec = specs.get(grain.grain_id)
            if spec is None:
                res.state = "failed"
                res.error = f"no GrainAgentSpec for grain {grain.grain_id!r}"
                res.ended_at = now_iso()
                return

            try:
                reply, run_meta = self._run_one_grain(spec, grain, workdir)
            except Exception as exc:  # runner crash → failed grain, never raises out
                res.state = "failed"
                res.error = f"runner exception: {exc!r}"
                res.ended_at = now_iso()
                return

            self._write_artifacts(
                workdir,
                reply=reply,
                spec=spec,
                grain=grain,
                meta=run_meta,
            )
            res.state = "completed" if run_meta.get("success") else "failed"
            res.error = run_meta.get("error")
            res.ended_at = now_iso()

        with ThreadPoolExecutor(max_workers=self.config.concurrency) as pool:
            futures = [pool.submit(_one, g) for g in plan.grains]
            for fut in as_completed(futures):
                fut.result()  # _one swallows its own errors; this re-raises bugs

        return [results[g.grain_id] for g in plan.grains]

    # ------------------------------------------------------------------ internals
    def _run_one_grain(
        self,
        spec: GrainAgentSpec,
        grain: Grain,
        workdir: Path,
    ) -> tuple[str, dict[str, Any]]:
        """Spawn one :class:`AIAgent` and return ``(reply, meta)``.

        Lazily imports :mod:`run_agent` so importing this module never drags
        in the full model stack — matches the conservative import discipline
        of :mod:`hermes_cli.swarm.executor`.
        """
        from run_agent import AIAgent

        ephemeral = spec.system_prompt
        if spec.context:
            ephemeral = f"{spec.system_prompt}\n\n{spec.context}"

        # Keep the grain's workdir as the agent's CWD so any tool/file
        # operations happen inside the isolated worktree, not the repo root.
        original_cwd = Path.cwd()
        try:
            workdir.mkdir(parents=True, exist_ok=True)
            import os

            os.chdir(str(workdir))

            agent = AIAgent(
                base_url=self.config.base_url,
                api_key=self.config.api_key,
                provider=self.config.provider,
                model=self.config.model,
                max_iterations=self.config.max_iterations,
                enabled_toolsets=list(spec.toolsets) if spec.toolsets else None,
                quiet_mode=self.config.quiet_mode,
                ephemeral_system_prompt=ephemeral,
                skip_context_files=True,
                save_trajectories=False,
            )

            task = (
                f"{grain.intent}\n\n"
                f"Work only within: {', '.join(grain.domain.globs)}\n"
                f"Swarm goal: {grain.intent}"
            )

            meta: dict[str, Any] = {
                "grain_id": grain.grain_id,
                "model": self.config.model,
                "provider": self.config.provider,
                "base_url": self.config.base_url,
                "started_at": now_iso(),
            }
            try:
                reply = agent.chat(task)
                meta["success"] = True
                meta["error"] = None
            except Exception as exc:
                reply = ""
                meta["success"] = False
                meta["error"] = repr(exc)
            meta["ended_at"] = now_iso()
            return reply, meta
        finally:
            import os

            os.chdir(str(original_cwd))

    def _write_artifacts(
        self,
        workdir: Path,
        *,
        reply: str,
        spec: GrainAgentSpec,
        grain: Grain,
        meta: dict[str, Any],
    ) -> None:
        workdir = Path(workdir)
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / "output.md").write_text(reply or "", encoding="utf-8")
        try:
            (workdir / "GRAIN_PROMPT.md").write_text(
                spec.system_prompt + "\n", encoding="utf-8"
            )
            if spec.context:
                (workdir / "GRAIN_CONTEXT.md").write_text(
                    spec.context, encoding="utf-8"
                )
        except OSError:
            pass
        (workdir / "status.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _provision(self, repo: Path, plan: SwarmPlan) -> dict[str, tuple[Path, str]]:
        from hermes_cli import worktrees as wt

        out: dict[str, tuple[Path, str]] = {}
        for grain in plan.grains:
            info = wt.create_worktree(
                repo,
                job_id=plan.job_id,
                worker_id=grain.grain_id,
                base_ref=self.config.base_ref,
                extra_metadata={
                    "intent": grain.intent,
                    "lane": grain.model_lane,
                    "executor": "AIAgentExecutor",
                },
            )
            out[grain.grain_id] = (Path(info.path), info.branch)
        return out
