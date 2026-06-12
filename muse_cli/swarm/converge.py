"""Convergence — turn many candidate grain outputs into one chosen result.

Two convergence modes:

* **cooperative** (the default for a Swarm Grainler Parallel job): grains own
  *disjoint* file-domains, so there is nothing to choose between — every grain's
  output is kept, and the only job here is the conflict backstop (a sanity check
  that the disjoint-domain guarantee held at runtime).
* **competitive / best-of-N**: several candidates attempt the *same* grain; we
  score them with the deterministic, test-weighted :mod:`muse_cli.scoring`
  engine and pick the winner with :func:`muse_cli.merge_engine.select_winner`.

Per the research, the primary selection signal is **tests**, not an LLM judge:
``scoring.py`` rewards diffs that apply cleanly and pass validation and rejects
secret-leaking or high-risk-without-tests candidates outright. An LLM judge, if
ever added, is a *tiebreak* only — never the arbiter — because judges show
self-preference and gold-answer bias.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

__all__ = [
    "ConflictReport",
    "ConvergenceResult",
    "detect_runtime_conflicts",
    "converge_cooperative",
    "converge_competitive",
]


@dataclass
class ConflictReport:
    """A pair of grains that touched the same file at runtime (should be empty)."""

    grain_a: str
    grain_b: str
    files: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"grain_a": self.grain_a, "grain_b": self.grain_b, "files": list(self.files)}


@dataclass
class ConvergenceResult:
    mode: str
    winner: Optional[str] = None
    kept: list[str] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[ConflictReport] = field(default_factory=list)
    requires_manual_review: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "winner": self.winner,
            "kept": self.kept,
            "rejected": self.rejected,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "requires_manual_review": self.requires_manual_review,
            "notes": self.notes,
        }


def detect_runtime_conflicts(
    changed_by_grain: Mapping[str, Sequence[str]]
) -> list[ConflictReport]:
    """Backstop: report any two grains that changed a common file.

    With a proven-disjoint plan + worktree isolation this is always empty; a
    non-empty result means runtime drift escaped the static + physical layers
    and must be surfaced (never silently merged).
    """

    reports: list[ConflictReport] = []
    items = [(g, set(files)) for g, files in changed_by_grain.items()]
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            ga, fa = items[i]
            gb, fb = items[j]
            common = tuple(sorted(fa & fb))
            if common:
                reports.append(ConflictReport(grain_a=ga, grain_b=gb, files=common))
    return reports


def converge_cooperative(changed_by_grain: Mapping[str, Sequence[str]]) -> ConvergenceResult:
    """Keep every grain; verify the disjoint-domain guarantee held at runtime."""

    conflicts = detect_runtime_conflicts(changed_by_grain)
    result = ConvergenceResult(
        mode="cooperative",
        kept=list(changed_by_grain.keys()),
        conflicts=conflicts,
        requires_manual_review=bool(conflicts),
    )
    if conflicts:
        result.notes.append(
            "Runtime file overlap detected despite disjoint domains — needs "
            "manual review (not merged automatically)."
        )
    else:
        result.notes.append("All grains kept; no runtime file overlap.")
    return result


def converge_competitive(
    candidates_dir: Path,
    out_dir: Path,
    *,
    user_profile: Optional[Any] = None,
) -> ConvergenceResult:
    """Best-of-N: score candidate outputs under ``candidates_dir`` and pick one.

    Each immediate subdirectory of ``candidates_dir`` is one candidate's
    artifact dir (``output.md`` / ``patch.diff`` / ``changed-files.txt`` /
    ``validation-output.txt`` / ``status.json``). Writes the six canonical merge
    artifacts into ``out_dir`` and returns the chosen winner.
    """

    from muse_cli.merge_engine import run_merge

    merge = run_merge(Path(candidates_dir), Path(out_dir), user_profile=user_profile)
    winner_id = getattr(merge.winner, "worker_id", None) if merge.winner else None
    rejected = [
        {"worker_id": r.worker_id, "reason": r.reason}
        for r in getattr(merge, "rejected", [])
    ]
    conflicts = [
        ConflictReport(
            grain_a=getattr(c, "winner_id", "?"),
            grain_b=getattr(c, "other_id", "?"),
            files=tuple(getattr(c, "files", ()) or ()),
        )
        for c in getattr(merge, "conflicts", [])
    ]
    result = ConvergenceResult(
        mode="competitive",
        winner=winner_id,
        kept=[winner_id] if winner_id else [],
        rejected=rejected,
        conflicts=conflicts,
        requires_manual_review=getattr(merge, "requires_manual_review", winner_id is None),
    )
    if winner_id:
        result.notes.append(f"Winner selected by test-weighted scoring: {winner_id}.")
    else:
        result.notes.append("No clear winner — manual review required.")
    return result
