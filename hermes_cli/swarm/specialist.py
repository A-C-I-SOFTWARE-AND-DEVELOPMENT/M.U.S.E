"""Specialized grain-agents — each grain becomes its own LLM.

This module realises the "every agent is its own specialized LLM with the full
Hermes/JARVIS capability set" requirement. For a grain it builds a
:class:`GrainAgentSpec` that bundles:

* a **token-juice** context pack (priority-ordered, budget-bounded, provenance
  tagged) scoped to the grain's mission + its private memory namespace + the
  shared swarm blackboard — reusing :class:`TokenJuiceCompiler`;
* the grain's **own** model lane, toolset, and iteration budget;
* a **dedicated Memory Tree namespace** so grains never cross-write memory.

It also provides the *dynamic* half of the non-overlap guarantee: a
:func:`claim_grain` lease over the grain's file-domain that is rejected if it
overlaps any other **active** claim (the runtime backstop behind the static
``prove_disjoint`` check and the per-grain git worktree).

The actual model spawn (:func:`spawn_agent`) lazily imports the agent runtime,
so importing this module never drags in the full agent stack — keeping the spec
builders unit-testable without a network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence
import json
import os
import time

from hermes_cli.swarm.grain import FileDomain, Grain, now_iso

__all__ = [
    "GrainAgentSpec",
    "build_grain_agent_spec",
    "DomainClaimError",
    "DomainClaim",
    "claim_grain",
    "release_grain",
    "spawn_agent",
]


# ---------------------------------------------------------------------------
# Specialized-agent spec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GrainAgentSpec:
    """Everything needed to instantiate one grain's specialized LLM."""

    grain_id: str
    model_lane: str
    toolsets: tuple[str, ...]
    iteration_budget: int
    token_budget: int
    memory_namespace: str
    system_prompt: str
    context: str  # rendered token-juice context pack
    dropped_context: tuple[str, ...] = ()
    used_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "grain_id": self.grain_id,
            "model_lane": self.model_lane,
            "toolsets": list(self.toolsets),
            "iteration_budget": self.iteration_budget,
            "token_budget": self.token_budget,
            "memory_namespace": self.memory_namespace,
            "used_tokens": self.used_tokens,
            "dropped_context": list(self.dropped_context),
            "system_prompt": self.system_prompt,
            "context": self.context,
        }


def _system_prompt(grain: Grain, goal: str) -> str:
    lines = [
        f"You are the specialized agent for grain `{grain.grain_id}`.",
        f"Swarm goal: {goal}",
        f"Your task: {grain.intent}",
        "",
        "You own ONLY these files (your file-domain). Never write outside it —",
        "another agent owns the rest and your work runs in an isolated git",
        "worktree:",
    ]
    lines += [f"  - {g}" for g in grain.domain.globs]
    if grain.domain.forbidden:
        lines.append("Explicitly forbidden within your domain:")
        lines += [f"  - {g}" for g in grain.domain.forbidden]
    if grain.acceptance_criteria:
        lines.append("")
        lines.append("Acceptance criteria:")
        lines += [f"  - {c}" for c in grain.acceptance_criteria]
    if grain.verification_plan:
        lines.append("")
        lines.append("Verification (run these; they must pass):")
        lines += [f"  - {c}" for c in grain.verification_plan]
    if grain.owner_gated_actions:
        lines.append("")
        lines.append(
            "OWNER-GATED actions present — do NOT perform these without the owner's "
            'exact reply "Yes, with authorization.":'
        )
        lines += [f"  - {a}" for a in grain.owner_gated_actions]
    lines.append("")
    lines.append(f"Risk class: {grain.risk_class}.")
    return "\n".join(lines)


def build_grain_agent_spec(
    grain: Grain,
    *,
    goal: str,
    blackboard_namespace: str,
    memory_store: Optional[Any] = None,
    repo_snippets: Sequence[tuple[str, str]] = (),
    compiler: Optional[Any] = None,
    default_toolsets: Sequence[str] = ("coding", "filesystem"),
) -> GrainAgentSpec:
    """Build the specialized-LLM spec for ``grain``.

    The token-juice context pack is scoped to the grain's mission and reads from
    the grain's *private* memory namespace plus the shared swarm blackboard, so
    a grain sees the swarm-wide decisions and its own notes but not another
    grain's private working memory.
    """

    system = _system_prompt(grain, goal)

    context_text = ""
    dropped: tuple[str, ...] = ()
    used = 0
    try:
        if compiler is None:
            from hermes_cli.jarvis_prime.tokenjuice import TokenJuiceCompiler

            compiler = TokenJuiceCompiler()
        compiled = compiler.compile(
            grain.intent,
            grain.token_budget,
            memory_store=memory_store,
            memory_namespaces=[grain.memory_namespace, blackboard_namespace],
            repo_snippets=tuple(repo_snippets),
        )
        context_text = compiled.render()
        dropped = tuple(compiled.dropped)
        used = compiled.used_tokens
    except Exception:
        # Token-juice is an enhancement, not a hard dependency of the spec.
        context_text = ""

    toolsets = tuple(grain.toolset_hint) or tuple(default_toolsets)
    return GrainAgentSpec(
        grain_id=grain.grain_id,
        model_lane=grain.model_lane,
        toolsets=toolsets,
        iteration_budget=grain.iteration_budget,
        token_budget=grain.token_budget,
        memory_namespace=grain.memory_namespace,
        system_prompt=system,
        context=context_text,
        dropped_context=dropped,
        used_tokens=used,
    )


# ---------------------------------------------------------------------------
# Dynamic domain claim — the runtime non-overlap backstop
# ---------------------------------------------------------------------------


class DomainClaimError(RuntimeError):
    """Raised when a grain's file-domain overlaps an already-active claim."""

    def __init__(self, grain_id: str, other_job: str, other_grain: str) -> None:
        self.grain_id = grain_id
        self.other_job = other_job
        self.other_grain = other_grain
        super().__init__(
            f"grain {grain_id!r} file-domain overlaps active claim "
            f"{other_job}:{other_grain}"
        )


@dataclass(frozen=True)
class DomainClaim:
    job_id: str
    grain_id: str
    lease_id: str
    globs: tuple[str, ...]
    claimed_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "grain_id": self.grain_id,
            "lease_id": self.lease_id,
            "globs": list(self.globs),
            "claimed_at": self.claimed_at,
        }


def _registry_path(repo: Path) -> Path:
    return Path(repo) / ".hermes-orchestrator" / "swarm-claims.json"


def _read_registry(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _write_registry(path: Path, claims: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(claims, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def claim_grain(
    repo: Path,
    job_id: str,
    grain: Grain,
    *,
    lease_store: Optional[Any] = None,
    ttl: float = 3600.0,
    host_id: Optional[str] = None,
) -> DomainClaim:
    """Acquire a worker-lease claim over ``grain``'s file-domain.

    Rejects (``DomainClaimError``) if the domain overlaps any other *active*
    claim — this catches runtime drift the static ``prove_disjoint`` could not
    foresee (e.g. a second concurrent swarm on the same checkout). Records the
    claim both in the durable lease store and a JSON registry sidecar.
    """

    repo = Path(repo)
    registry = _registry_path(repo)
    existing = _read_registry(registry)

    this_domain = grain.domain
    for claim in existing:
        # A claim from this same grain (re-entrant) does not conflict.
        if claim.get("job_id") == job_id and claim.get("grain_id") == grain.grain_id:
            continue
        other = FileDomain(globs=tuple(claim.get("globs") or ("**",)))
        if not this_domain.disjoint(other):
            raise DomainClaimError(
                grain.grain_id,
                str(claim.get("job_id", "?")),
                str(claim.get("grain_id", "?")),
            )

    lease_id = f"{job_id}:{grain.grain_id}"
    # Best-effort durable lease (observational; never blocks on store errors).
    try:
        from hermes_cli import worker_lease as wl
        from hermes_cli.worker_lease_store import DEFAULT_HOST_ID, WorkerLeaseStore

        store = lease_store if lease_store is not None else WorkerLeaseStore.load()
        lease = wl.WorkerLease(
            lease_id=lease_id,
            job_id=job_id,
            worker_id=grain.grain_id,
            host_id=host_id or DEFAULT_HOST_ID,
        )
        lease = wl.acquire(lease, now=time.time(), ttl=max(1.0, float(ttl)))
        store.upsert(lease)
    except Exception:
        pass

    claim = DomainClaim(
        job_id=job_id,
        grain_id=grain.grain_id,
        lease_id=lease_id,
        globs=tuple(grain.domain.globs),
    )
    existing.append(claim.to_dict())
    _write_registry(registry, existing)
    return claim


def release_grain(repo: Path, job_id: str, grain_id: str) -> bool:
    """Drop a grain's claim from the registry. Returns True if one was removed."""

    repo = Path(repo)
    registry = _registry_path(repo)
    existing = _read_registry(registry)
    kept = [
        c
        for c in existing
        if not (c.get("job_id") == job_id and c.get("grain_id") == grain_id)
    ]
    if len(kept) == len(existing):
        return False
    _write_registry(registry, kept)
    return True


def spawn_agent(spec: GrainAgentSpec, *, parent_agent: Optional[Any] = None) -> Any:
    """Instantiate the specialized :class:`AIAgent` for a grain.

    Lazily imports the agent runtime. The grain's spec drives the model lane,
    restricted toolset, independent iteration budget, and its token-juice
    context pack (prepended to the ephemeral system prompt). This is the point
    at which a grain "becomes its own specialized LLM."
    """

    from run_agent import AIAgent

    ephemeral = spec.system_prompt
    if spec.context:
        ephemeral = f"{spec.system_prompt}\n\n{spec.context}"

    kwargs: dict[str, Any] = {
        "enabled_toolsets": list(spec.toolsets),
        "max_iterations": spec.iteration_budget,
        "ephemeral_system_prompt": ephemeral,
        "skip_context_files": True,
    }
    if parent_agent is not None:
        for attr in ("base_url", "api_key", "provider"):
            value = getattr(parent_agent, attr, None)
            if value is not None:
                kwargs[attr] = value
    return AIAgent(**kwargs)
