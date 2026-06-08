"""Inductive + deductive reasoning helpers for MUSE.

The user asked for JARVIS to "use inductive/deductive reasoning".
This module provides two structured reasoners:

- **Deductive**: given a rule (general → specific) and a premise,
  derive the conclusion. Validates the rule's preconditions match
  the premise before concluding.
- **Inductive**: given N observations, propose a generalization
  with a confidence proportional to coverage. The reasoner names
  required corroborations before promoting the generalization to a
  durable rule.

Both reasoners are deterministic, stdlib-only, and emit a structured
``Inference`` with confidence + cited evidence. Outputs are usable
in the validation gate and decision ledger.

The runtime should call these BEFORE producing a confident answer —
when neither reasoner can land at high confidence, the runtime
escalates to the research module instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional, Sequence


class ReasoningKind(Enum):
    DEDUCTIVE = "deductive"
    INDUCTIVE = "inductive"


@dataclass(frozen=True)
class Premise:
    """One known fact / observation."""

    statement: str
    confidence: float = 1.0
    citation: Optional[str] = None


@dataclass(frozen=True)
class Rule:
    """If-then rule used by deductive reasoning."""

    name: str
    conditions: tuple[str, ...]
    conclusion: str
    confidence: float = 1.0
    citation: Optional[str] = None


@dataclass(frozen=True)
class Inference:
    kind: ReasoningKind
    conclusion: str
    confidence: float
    evidence: tuple[str, ...]
    reasoning: str
    rule_used: Optional[str] = None
    requires_corroboration: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "conclusion": self.conclusion,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "reasoning": self.reasoning,
            "rule_used": self.rule_used,
            "requires_corroboration": self.requires_corroboration,
        }


def deduce(
    rule: Rule,
    premises: Sequence[Premise],
    strict: bool = True,
) -> Inference:
    """Apply a rule to premises.

    Returns an Inference. If ``strict`` and not all rule conditions
    are matched by some premise, returns the conclusion with low
    confidence and ``requires_corroboration=True`` rather than
    fabricating certainty.
    """

    premise_texts = [p.statement.lower() for p in premises]
    matched_conditions: list[str] = []
    for cond in rule.conditions:
        cond_low = cond.lower()
        if any(cond_low in pt or pt in cond_low for pt in premise_texts):
            matched_conditions.append(cond)

    coverage = len(matched_conditions) / max(1, len(rule.conditions))
    if strict and coverage < 1.0:
        confidence = rule.confidence * coverage * 0.5  # cap below the rule's confidence
        requires_corroboration = True
        reasoning = (
            f"Rule {rule.name!r} requires {len(rule.conditions)} conditions; "
            f"premises cover {len(matched_conditions)}/{len(rule.conditions)}. "
            "Conclusion held with low confidence pending corroboration."
        )
    else:
        confidence = min(
            rule.confidence,
            *(p.confidence for p in premises) if premises else (rule.confidence,),
        )
        requires_corroboration = False
        reasoning = (
            f"Rule {rule.name!r}: all {len(rule.conditions)} conditions matched "
            f"by premises; conclusion follows."
        )

    evidence_bits: list[str] = [f"rule:{rule.name}"]
    if rule.citation:
        evidence_bits.append(f"rule_cite:{rule.citation}")
    for p in premises:
        if p.citation:
            evidence_bits.append(f"premise_cite:{p.citation}")

    return Inference(
        kind=ReasoningKind.DEDUCTIVE,
        conclusion=rule.conclusion,
        confidence=confidence,
        evidence=tuple(evidence_bits),
        reasoning=reasoning,
        rule_used=rule.name,
        requires_corroboration=requires_corroboration,
    )


def induce(
    observations: Sequence[Premise],
    proposed_generalization: str,
    minimum_observations: int = 3,
    corroboration_floor: float = 0.7,
) -> Inference:
    """Propose a generalization from N observations.

    Confidence rises with observation count and average premise
    confidence. If observations < ``minimum_observations`` OR
    confidence < ``corroboration_floor``, ``requires_corroboration``
    is set so the runtime knows to gather more data before
    promoting to a durable rule.
    """

    n = len(observations)
    if n == 0:
        return Inference(
            kind=ReasoningKind.INDUCTIVE,
            conclusion=proposed_generalization,
            confidence=0.0,
            evidence=(),
            reasoning="No observations — cannot induce a generalization.",
            requires_corroboration=True,
        )

    avg_conf = sum(p.confidence for p in observations) / n
    # Coverage saturates around 5 observations; more = diminishing returns.
    coverage = min(1.0, n / 5.0)
    confidence = avg_conf * coverage

    citations = tuple(
        f"obs_cite:{p.citation}" for p in observations if p.citation
    )

    requires_corroboration = (n < minimum_observations) or (confidence < corroboration_floor)

    reasoning = (
        f"Induced from {n} observations; avg confidence {avg_conf:.2f}; "
        f"coverage {coverage:.2f}. "
        + (
            "Promoted at high confidence."
            if not requires_corroboration
            else f"Below floor ({corroboration_floor}) — needs more corroboration."
        )
    )

    return Inference(
        kind=ReasoningKind.INDUCTIVE,
        conclusion=proposed_generalization,
        confidence=confidence,
        evidence=(f"n_observations:{n}",) + citations,
        reasoning=reasoning,
        requires_corroboration=requires_corroboration,
    )


def should_research(inference: Inference, confidence_floor: float = 0.65) -> bool:
    """Return True when the reasoner's confidence is too low to answer.

    The runtime uses this to escalate from reasoning → deep research
    rather than producing a confident-sounding answer it cannot
    actually support.
    """

    if inference.requires_corroboration:
        return True
    return inference.confidence < confidence_floor


@dataclass
class Reasoner:
    """Bundle deduce + induce + research-trigger on one object."""

    confidence_floor: float = 0.65

    def deduce(self, rule: Rule, premises: Sequence[Premise], strict: bool = True) -> Inference:
        return deduce(rule, premises, strict=strict)

    def induce(
        self,
        observations: Sequence[Premise],
        proposed_generalization: str,
        minimum_observations: int = 3,
        corroboration_floor: Optional[float] = None,
    ) -> Inference:
        floor = corroboration_floor if corroboration_floor is not None else self.confidence_floor
        return induce(
            observations,
            proposed_generalization,
            minimum_observations=minimum_observations,
            corroboration_floor=floor,
        )

    def should_research(self, inference: Inference) -> bool:
        return should_research(inference, confidence_floor=self.confidence_floor)
