"""The strict non-regression ratchet — the "never worsens itself" guarantee.

This is the research fabric's load-bearing validator. It composes the existing
single-dimension :func:`benchmark_gate.evaluate_improvement` into a multi-domain
rule modeled on **AlphaGo Zero's evaluator gate** (a challenger replaced the
champion only if it won >55% of head-to-head games — AlphaZero paper,
arXiv:1712.01815).

A challenger passes the wall only if **all** of the following hold:

1. **No required domain dropped** — a missing score is a failure, never a pass.
2. **Meet/beat champion on every domain** — per-domain via ``evaluate_improvement``
   with zero margin; a single regression fails the whole verdict.
3. **Absolute floor** — every domain >= ``ABSOLUTE_FLOOR`` (0.80).
4. **Composite margin** — weighted composite >= champion composite + ``COMPOSITE_MARGIN``.
5. **Evaluator gate** — head-to-head challenger win-rate >= ``EVAL_WIN_MARGIN`` (0.55).
6. **Held-out / post-cutoff wall** — the held-out scores independently clear the
   floor and meet the champion (anti-overfit / anti-contamination).
7. **Safety non-regression** — counts that are *bad when higher*
   (hallucinations, owner-corrections) may not rise; ``SAFETY_DOMAINS`` may only
   rise. Model candidates may additionally delegate to
   ``model_scorecard.promotion_eligible`` (see :func:`evaluate_ratchet`).
8. **Cold start** (``champion is None``) — floor + held-out floor only; the first
   passing challenger becomes the baseline.

Thresholds are never lowered here. The optional ambition layer
(:mod:`research_fabric.ambition`) may only *raise* the bar on top of this.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from muse_cli.jarvis_prime.benchmark_gate import evaluate_improvement
from muse_cli.jarvis_prime.gates import GateOutcome

from .catalog import (
    ABSOLUTE_FLOOR,
    COMPOSITE_MARGIN,
    EVAL_WIN_MARGIN,
    REQUIRED_DOMAINS,
    SAFETY_DOMAINS,
)


@dataclass(frozen=True)
class RatchetVerdict:
    """The structured outcome of one ratchet evaluation."""

    passed: bool
    # domain -> (champion_score | None, candidate_score | None, ok)
    per_domain: dict[str, tuple[Optional[float], Optional[float], bool]]
    composite_champion: Optional[float]
    composite_candidate: float
    composite_delta: float
    eval_win_rate: Optional[float]
    floor_violations: tuple[str, ...]
    dropped_domains: tuple[str, ...]
    safety_regressions: tuple[str, ...]
    holdout_ok: bool
    cold_start: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "per_domain": {
                d: {"champion": c, "candidate": k, "ok": ok}
                for d, (c, k, ok) in self.per_domain.items()
            },
            "composite_champion": self.composite_champion,
            "composite_candidate": self.composite_candidate,
            "composite_delta": self.composite_delta,
            "eval_win_rate": self.eval_win_rate,
            "floor_violations": list(self.floor_violations),
            "dropped_domains": list(self.dropped_domains),
            "safety_regressions": list(self.safety_regressions),
            "holdout_ok": self.holdout_ok,
            "cold_start": self.cold_start,
            "reasons": list(self.reasons),
        }


def _composite(scores: Mapping[str, float], domains: tuple[str, ...]) -> float:
    present = [scores[d] for d in domains if d in scores]
    if not present:
        return 0.0
    return round(sum(present) / len(present), 4)


def evaluate_ratchet(
    *,
    champion_domain_scores: Optional[Mapping[str, float]],
    candidate_domain_scores: Mapping[str, float],
    holdout_scores: Optional[Mapping[str, float]] = None,
    candidate_safety_counts: Optional[Mapping[str, float]] = None,
    champion_safety_counts: Optional[Mapping[str, float]] = None,
    eval_win_rate: Optional[float] = None,
    required_domains: tuple[str, ...] = REQUIRED_DOMAINS,
    floor: float = ABSOLUTE_FLOOR,
    composite_margin: float = COMPOSITE_MARGIN,
    eval_win_margin: float = EVAL_WIN_MARGIN,
) -> RatchetVerdict:
    """Evaluate the strict non-regression ratchet. See module docstring.

    ``champion_domain_scores=None`` triggers cold-start mode (floor-only).
    ``candidate_safety_counts`` / ``champion_safety_counts`` hold counts that are
    *bad when higher* (e.g. ``{"hallucination": 0, "owner_correction": 1}``);
    a rise fails the wall. The win-rate check is skipped (not failed) only when
    no champion exists (cold start) — a warm run with no win-rate fails closed.
    """

    reasons: list[str] = []
    dropped: list[str] = []
    floor_violations: list[str] = []
    safety_regressions: list[str] = []
    per_domain: dict[str, tuple[Optional[float], Optional[float], bool]] = {}

    cold_start = champion_domain_scores is None
    holdout = dict(holdout_scores or {})

    # ---- (1) coverage + (2) per-domain non-regression + (3) floor ----------
    for domain in required_domains:
        cand = candidate_domain_scores.get(domain)
        champ = None if champion_domain_scores is None else champion_domain_scores.get(domain)

        if cand is None:
            dropped.append(domain)
            per_domain[domain] = (champ, None, False)
            continue

        ok = True
        # (3) absolute floor
        if cand < floor:
            floor_violations.append(domain)
            ok = False
        # (2) meet/beat champion (reuse the single-dimension gate)
        if champ is not None:
            gate = evaluate_improvement(champ, cand, task=domain, min_margin=0.0)
            # A tie (delta == 0) is acceptable for non-regression on a single
            # domain — the composite margin (4) is what enforces real gain.
            if gate.outcome is GateOutcome.FAIL and cand < champ:
                ok = False
                safety_or = " (SAFETY)" if domain in SAFETY_DOMAINS else ""
                reasons.append(
                    f"domain '{domain}'{safety_or} regressed: {cand:.4f} < champion {champ:.4f}"
                )
        per_domain[domain] = (champ, cand, ok)

    if dropped:
        reasons.append(f"required domains missing a score: {dropped}")
    if floor_violations:
        reasons.append(
            f"below absolute floor {floor:.2f}: {floor_violations}"
        )

    # ---- (7) safety-count non-regression -----------------------------------
    cand_counts = dict(candidate_safety_counts or {})
    champ_counts = dict(champion_safety_counts or {})
    for name, cand_val in cand_counts.items():
        champ_val = champ_counts.get(name)
        if champ_val is not None and cand_val > champ_val:
            safety_regressions.append(name)
            reasons.append(
                f"safety count '{name}' rose: {cand_val} > champion {champ_val}"
            )

    # ---- composite (4) ------------------------------------------------------
    composite_candidate = _composite(candidate_domain_scores, required_domains)
    composite_champion = (
        None
        if champion_domain_scores is None
        else _composite(champion_domain_scores, required_domains)
    )
    composite_delta = (
        round(composite_candidate - composite_champion, 4)
        if composite_champion is not None
        else composite_candidate
    )

    # ---- (6) held-out wall --------------------------------------------------
    holdout_ok = True
    if holdout:
        for domain, score in holdout.items():
            if score < floor:
                holdout_ok = False
                reasons.append(
                    f"held-out '{domain}' below floor {floor:.2f}: {score:.4f}"
                )
            if champion_domain_scores is not None:
                champ = champion_domain_scores.get(domain)
                if champ is not None and score < champ:
                    holdout_ok = False
                    reasons.append(
                        f"held-out '{domain}' regressed vs champion: "
                        f"{score:.4f} < {champ:.4f}"
                    )
    else:
        # No held-out evidence at all is not allowed for a warm promotion;
        # cold start may proceed on the visible floor alone.
        if not cold_start:
            holdout_ok = False
            reasons.append("no held-out / post-cutoff evidence supplied")

    # ---- assemble pass/fail -------------------------------------------------
    if cold_start:
        passed = (
            not dropped
            and not floor_violations
            and holdout_ok
        )
        if passed:
            reasons.append(
                "cold start: first challenger clears the floor and becomes the baseline"
            )
        return RatchetVerdict(
            passed=passed,
            per_domain=per_domain,
            composite_champion=None,
            composite_candidate=composite_candidate,
            composite_delta=composite_delta,
            eval_win_rate=eval_win_rate,
            floor_violations=tuple(floor_violations),
            dropped_domains=tuple(dropped),
            safety_regressions=tuple(safety_regressions),
            holdout_ok=holdout_ok,
            cold_start=True,
            reasons=tuple(reasons),
        )

    # Warm run.
    all_domains_ok = all(ok for _, _, ok in per_domain.values())

    # (4) composite margin
    composite_ok = composite_delta >= composite_margin
    if not composite_ok:
        reasons.append(
            f"composite gain {composite_delta:+.4f} < required margin {composite_margin:.4f}"
        )

    # (5) evaluator gate
    if eval_win_rate is None:
        eval_ok = False
        reasons.append(
            f"no challenger eval win-rate supplied (need >= {eval_win_margin:.2f})"
        )
    else:
        eval_ok = eval_win_rate >= eval_win_margin
        if not eval_ok:
            reasons.append(
                f"evaluator gate: win-rate {eval_win_rate:.3f} < {eval_win_margin:.2f}"
            )

    passed = (
        all_domains_ok
        and not dropped
        and not floor_violations
        and not safety_regressions
        and composite_ok
        and eval_ok
        and holdout_ok
    )
    if passed:
        reasons.append(
            f"ratchet passed: every domain non-regressing, composite "
            f"{composite_delta:+.4f}, eval win-rate {eval_win_rate:.3f}"
        )

    return RatchetVerdict(
        passed=passed,
        per_domain=per_domain,
        composite_champion=composite_champion,
        composite_candidate=composite_candidate,
        composite_delta=composite_delta,
        eval_win_rate=eval_win_rate,
        floor_violations=tuple(floor_violations),
        dropped_domains=tuple(dropped),
        safety_regressions=tuple(safety_regressions),
        holdout_ok=holdout_ok,
        cold_start=False,
        reasons=tuple(reasons),
    )


class RatchetWall:
    """Thin object wrapper around :func:`evaluate_ratchet` for injection/config."""

    def __init__(
        self,
        *,
        required_domains: tuple[str, ...] = REQUIRED_DOMAINS,
        floor: float = ABSOLUTE_FLOOR,
        composite_margin: float = COMPOSITE_MARGIN,
        eval_win_margin: float = EVAL_WIN_MARGIN,
    ) -> None:
        self.required_domains = required_domains
        self.floor = floor
        self.composite_margin = composite_margin
        self.eval_win_margin = eval_win_margin

    def evaluate(self, **kwargs: Any) -> RatchetVerdict:
        kwargs.setdefault("required_domains", self.required_domains)
        kwargs.setdefault("floor", self.floor)
        kwargs.setdefault("composite_margin", self.composite_margin)
        kwargs.setdefault("eval_win_margin", self.eval_win_margin)
        return evaluate_ratchet(**kwargs)


__all__ = ["RatchetVerdict", "evaluate_ratchet", "RatchetWall"]
