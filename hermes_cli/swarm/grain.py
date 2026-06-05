"""Grain primitives for the Swarm Grainler Parallel architecture.

A **Grain** is the atomic unit of code work in a swarm. Each grain owns a
*disjoint file-domain* — a set of path globs that no other grain in the same
plan may touch. This module is the non-overlap kernel: it is pure,
deterministic, and has no I/O, so the collision-freedom guarantee can be
unit-tested in isolation.

The central safety property is :func:`FileDomain.disjoint` /
:meth:`SwarmPlan.prove_disjoint`. Glob intersection is undecidable in general,
so the check is deliberately **conservative**: it only declares two domains
disjoint when it can *prove* no concrete path could match a glob in both. Any
uncertainty is reported as an overlap. That bias is the safe one — an
over-reported overlap rejects a plan (no work starts), whereas a missed overlap
would let two agents trample the same file. The field-documented weakness of
git-worktree-only setups ("no mechanism to warn when two worktrees modify the
same files") is closed here, *before* any agent starts.

See ``docs/orchestration/swarm-grainler-parallel.md`` for the architecture.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Sequence

__all__ = [
    "OverlapError",
    "FileDomain",
    "Grain",
    "SwarmPlan",
    "now_iso",
]


class OverlapError(ValueError):
    """Raised when two grains' file-domains cannot be proven disjoint.

    ``pairs`` lists the ``(grain_a, grain_b, glob_a, glob_b)`` collisions so a
    caller can show exactly which assignments conflict.
    """

    def __init__(self, pairs: Sequence[tuple[str, str, str, str]]) -> None:
        self.pairs: list[tuple[str, str, str, str]] = list(pairs)
        detail = "; ".join(
            f"{a}:{ga} ∩ {b}:{gb}" for a, b, ga, gb in self.pairs
        )
        super().__init__(
            f"grain file-domains overlap (cannot prove disjoint): {detail}"
        )


def now_iso() -> str:
    """UTC timestamp, second precision, ``Z`` suffix — matches the runner."""

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Conservative glob intersection
# ---------------------------------------------------------------------------


def _split(glob: str) -> list[str]:
    """Split a glob into path segments, dropping a leading ``./``."""

    g = glob.strip().strip("/")
    if g.startswith("./"):
        g = g[2:]
    return [seg for seg in g.split("/") if seg != ""]


def _segments_can_share(a: str, b: str) -> bool:
    """Could a single path segment be matched by both single-segment globs?

    Sound, not exact: we only return ``False`` when we are *certain* the two
    segments cannot name the same thing — i.e. both are pure literals (no
    ``*``/``?``/``[``) and differ. Any wildcard on either side yields ``True``
    (conservative). This guarantees we never declare disjoint when an overlap
    is possible.
    """

    if a == b:
        return True
    a_wild = any(c in a for c in "*?[")
    b_wild = any(c in b for c in "*?[")
    if not a_wild and not b_wild:
        return False  # two different literals — provably distinct
    # At least one side is a wildcard. A single-char wildcard could still be
    # incompatible in theory, but proving that is not worth it; bias to overlap.
    return True


def _patterns_can_share(a: Sequence[str], b: Sequence[str]) -> bool:
    """Could some concrete path match both segment-pattern lists?

    Handles ``**`` (globstar) which matches zero or more segments. Returns
    ``True`` on any possible shared match; only returns ``False`` when no
    alignment can possibly coincide.
    """

    # Both exhausted → they describe the same (empty) tail.
    if not a and not b:
        return True
    # One exhausted: the other can still match the empty path only if every
    # remaining segment is ``**`` (which can absorb zero segments).
    if not a:
        return all(seg == "**" for seg in b)
    if not b:
        return all(seg == "**" for seg in a)

    if a[0] == "**":
        # ``**`` absorbs zero segments (advance a) OR one segment of b.
        return _patterns_can_share(a[1:], b) or _patterns_can_share(a, b[1:])
    if b[0] == "**":
        return _patterns_can_share(a, b[1:]) or _patterns_can_share(a[1:], b)

    if not _segments_can_share(a[0], b[0]):
        return False
    return _patterns_can_share(a[1:], b[1:])


def globs_overlap(glob_a: str, glob_b: str) -> bool:
    """True when globs ``a`` and ``b`` could match a common path.

    Conservative: returns ``True`` whenever a shared match cannot be ruled out.
    """

    return _patterns_can_share(_split(glob_a), _split(glob_b))


# ---------------------------------------------------------------------------
# FileDomain
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileDomain:
    """A set of path globs a grain is allowed to write.

    ``forbidden`` globs are carved out of the repo for *this* grain but do not
    participate in cross-grain overlap (they only narrow the grain's own reach).
    """

    globs: tuple[str, ...]
    forbidden: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.globs:
            raise ValueError("a FileDomain must declare at least one glob")
        for g in self.globs:
            if not g or not g.strip():
                raise ValueError("file-domain globs must be non-empty")

    def overlapping_pairs(self, other: "FileDomain") -> list[tuple[str, str]]:
        """Return every ``(self_glob, other_glob)`` pair that may share a path."""

        out: list[tuple[str, str]] = []
        for ga in self.globs:
            for gb in other.globs:
                if globs_overlap(ga, gb):
                    out.append((ga, gb))
        return out

    def disjoint(self, other: "FileDomain") -> bool:
        """True only when *no* glob pair across the two domains can share a path."""

        return not self.overlapping_pairs(other)

    def to_dict(self) -> dict[str, Any]:
        return {"globs": list(self.globs), "forbidden": list(self.forbidden)}

    @classmethod
    def from_iterable(
        cls, globs: Iterable[str], forbidden: Iterable[str] = ()
    ) -> "FileDomain":
        return cls(globs=tuple(globs), forbidden=tuple(forbidden))


# ---------------------------------------------------------------------------
# Grain
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Grain:
    """One bounded, non-overlapping unit of code work.

    A grain is a code-scoped specialization of a JARVIS work packet: it carries
    intent, a risk class, the file-domain it owns, owner-gate markers, the
    verification commands that prove it, and a rollback recipe. It also names
    the *specialized agent* that should execute it (model lane + toolset hint),
    so each grain becomes its own specialized LLM at run time.
    """

    grain_id: str
    intent: str
    domain: FileDomain
    risk_class: str = "RC1"
    # Specialized-LLM hints — consumed by ``specialist.build_grain_agent_spec``.
    model_lane: str = "claude"
    toolset_hint: tuple[str, ...] = ()
    # Bounded execution + audit metadata.
    acceptance_criteria: tuple[str, ...] = ()
    verification_plan: tuple[str, ...] = ()
    rollback_plan: tuple[str, ...] = ()
    owner_gated_actions: tuple[str, ...] = ()
    iteration_budget: int = 50
    token_budget: int = 8000
    created_at: str = field(default_factory=now_iso)

    def __post_init__(self) -> None:
        if not self.grain_id or not self.grain_id.strip():
            raise ValueError("grain_id is required")
        if not self.intent or not self.intent.strip():
            raise ValueError(f"grain {self.grain_id!r} needs a non-empty intent")
        if self.iteration_budget < 1:
            raise ValueError("iteration_budget must be >= 1")
        if self.token_budget < 1:
            raise ValueError("token_budget must be >= 1")

    @property
    def memory_namespace(self) -> str:
        """Dedicated Memory Tree namespace so grains never cross-write memory."""

        return f"swarm/grain/{self.grain_id}"

    @property
    def owner_gated(self) -> bool:
        return bool(self.owner_gated_actions)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["domain"] = self.domain.to_dict()
        d["memory_namespace"] = self.memory_namespace
        d["owner_gated"] = self.owner_gated
        return d


# ---------------------------------------------------------------------------
# SwarmPlan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SwarmPlan:
    """A goal decomposed into grains, plus the swarm-wide blackboard namespace."""

    job_id: str
    goal: str
    grains: tuple[Grain, ...]
    created_at: str = field(default_factory=now_iso)

    def __post_init__(self) -> None:
        if not self.job_id or not self.job_id.strip():
            raise ValueError("job_id is required")
        if not self.grains:
            raise ValueError("a SwarmPlan must contain at least one grain")
        seen: set[str] = set()
        for g in self.grains:
            if g.grain_id in seen:
                raise ValueError(f"duplicate grain_id: {g.grain_id!r}")
            seen.add(g.grain_id)

    @property
    def blackboard_namespace(self) -> str:
        """Shared, append-only coordination/audit namespace for this job."""

        return f"swarm/{self.job_id}"

    @property
    def is_trivial(self) -> bool:
        """A one-grain plan needs no swarm — the cost lesson (don't 15× a typo)."""

        return len(self.grains) <= 1

    def overlapping_pairs(self) -> list[tuple[str, str, str, str]]:
        """Every cross-grain ``(grain_a, grain_b, glob_a, glob_b)`` collision."""

        out: list[tuple[str, str, str, str]] = []
        grains = list(self.grains)
        for i in range(len(grains)):
            for j in range(i + 1, len(grains)):
                a, b = grains[i], grains[j]
                for ga, gb in a.domain.overlapping_pairs(b.domain):
                    out.append((a.grain_id, b.grain_id, ga, gb))
        return out

    def prove_disjoint(self) -> None:
        """Raise :class:`OverlapError` unless every grain pair is provably disjoint.

        This is the static, pre-execution non-overlap guarantee. Call it before
        a single worker is spawned; a plan that cannot pass starts zero agents.
        """

        pairs = self.overlapping_pairs()
        if pairs:
            raise OverlapError(pairs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "goal": self.goal,
            "created_at": self.created_at,
            "blackboard_namespace": self.blackboard_namespace,
            "is_trivial": self.is_trivial,
            "grains": [g.to_dict() for g in self.grains],
        }
