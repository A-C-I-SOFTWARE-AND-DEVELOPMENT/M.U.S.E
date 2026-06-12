"""Evolutionary archive of grain-agent variants (Darwin-Gödel / HGM pattern).

A self-improving swarm keeps a *lineage* of grain-agent variants — tweaks to a
grain's system-prompt, toolset, or model lane — and only promotes a variant when
it **empirically beats** the incumbent on a benchmark. This module is that
archive: an append-only JSONL of :class:`GrainVariant` records, with promotion
gated by :func:`muse_cli.jarvis_prime.benchmark_gate.evaluate_improvement`.

It never mutates a live agent. Promotion records the *winner* (and its score
margin) into the archive; wiring a promoted variant back into the default grain
spec is an explicit, owner-visible step (a proposal), not a silent self-edit —
matching the constitution's no-silent-overwrite rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional
import json
import os

from muse_cli.swarm.grain import now_iso

__all__ = [
    "GrainVariant",
    "VariantArchive",
    "benchmark_gated_promotion",
]


@dataclass
class GrainVariant:
    """One candidate variation of a grain-agent's configuration + its score."""

    variant_id: str
    grain_kind: str  # the grain family this variant targets (e.g. a lane/intent)
    parent_id: Optional[str] = None
    system_prompt_delta: str = ""
    toolset: tuple[str, ...] = ()
    model_lane: str = "claude"
    benchmark_task: str = "custom"
    benchmark_score: Optional[float] = None
    benchmark_ran: bool = False
    promoted: bool = False
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["toolset"] = list(self.toolset)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GrainVariant":
        return cls(
            variant_id=str(data["variant_id"]),
            grain_kind=str(data.get("grain_kind", "")),
            parent_id=data.get("parent_id"),
            system_prompt_delta=str(data.get("system_prompt_delta", "")),
            toolset=tuple(data.get("toolset", ())),
            model_lane=str(data.get("model_lane", "claude")),
            benchmark_task=str(data.get("benchmark_task", "custom")),
            benchmark_score=data.get("benchmark_score"),
            benchmark_ran=bool(data.get("benchmark_ran", False)),
            promoted=bool(data.get("promoted", False)),
            created_at=str(data.get("created_at", now_iso())),
        )


def _default_archive_path() -> Path:
    try:
        from hermes_constants import get_hermes_home

        home = Path(get_hermes_home())
    except Exception:
        home = Path(os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes"))
    return home / "jarvis_prime" / "swarm_variant_archive.jsonl"


@dataclass
class VariantArchive:
    """Append-only store of grain-agent variants under HERMES_HOME."""

    path: Optional[Path] = None

    def _resolved(self) -> Path:
        return Path(self.path) if self.path is not None else _default_archive_path()

    def add(self, variant: GrainVariant) -> GrainVariant:
        p = self._resolved()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(variant.to_dict(), sort_keys=True) + "\n")
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass
        return variant

    def all(self) -> list[GrainVariant]:
        p = self._resolved()
        if not p.exists():
            return []
        out: list[GrainVariant] = []
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(GrainVariant.from_dict(json.loads(line)))
            except (ValueError, KeyError):
                continue
        return out

    def best_for(self, grain_kind: str) -> Optional[GrainVariant]:
        scored = [
            v
            for v in self.all()
            if v.grain_kind == grain_kind and v.benchmark_score is not None
        ]
        if not scored:
            return None
        return max(scored, key=lambda v: v.benchmark_score or 0.0)


def benchmark_gated_promotion(
    incumbent_score: float,
    variant: GrainVariant,
    *,
    min_margin: Optional[float] = None,
    archive: Optional[VariantArchive] = None,
) -> dict[str, Any]:
    """Promote ``variant`` only if it beats ``incumbent_score`` on the benchmark.

    Returns a record with the gate outcome. The variant is written to the
    archive either way (with ``promoted`` reflecting the gate), so the lineage is
    preserved — losers included, exactly like an evolutionary archive.
    """

    from muse_cli.jarvis_prime.benchmark_gate import evaluate_improvement
    from muse_cli.jarvis_prime.gates import GateOutcome

    if variant.benchmark_score is None or not variant.benchmark_ran:
        result_outcome = GateOutcome.SKIPPED
        reason = "variant has no benchmark score"
    else:
        kwargs: dict[str, Any] = {
            "task": variant.benchmark_task,
            "benchmark_ran": variant.benchmark_ran,
        }
        if min_margin is not None:
            kwargs["min_margin"] = min_margin
        gate = evaluate_improvement(incumbent_score, variant.benchmark_score, **kwargs)
        result_outcome = gate.outcome
        reason = gate.reason

    variant.promoted = result_outcome == GateOutcome.PASS
    (archive or VariantArchive()).add(variant)
    return {
        "variant_id": variant.variant_id,
        "grain_kind": variant.grain_kind,
        "outcome": result_outcome.value,
        "reason": reason,
        "promoted": variant.promoted,
        "incumbent_score": incumbent_score,
        "candidate_score": variant.benchmark_score,
    }
