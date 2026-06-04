"""Grounding coverage metric.

Measures how much of a generated answer is *supported* by the retrieved
context — a proxy for faithfulness / groundedness. An answer claim
(sentence) counts as grounded when its token overlap with at least one
context block exceeds a threshold.

These helpers are also reused by :mod:`evaluation.hallucination_proxy`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Sequence, Set

__all__ = [
    "GroundingResult",
    "grounding_coverage",
    "split_claims",
    "token_overlap",
]

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_STOPWORDS = frozenset(
    "a an the and or but of to in on at by with from is are was were be this that it as "
    "for not no into over under their his her its they we you i he she them".split()
)


def _tokenize(text: str) -> Set[str]:
    return {
        tok for tok in _WORD_RE.findall(text.lower())
        if tok not in _STOPWORDS and len(tok) > 1
    }


def split_claims(text: str) -> List[str]:
    """Split an answer into claim-sized sentences."""
    text = (text or "").strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]


def token_overlap(claim: str, context: str) -> float:
    """Jaccard-style content-word overlap of ``claim`` against ``context``.

    Uses the claim's token set as the denominator (recall of claim tokens in
    the context), which better reflects "is this claim supported".
    """
    claim_tokens = _tokenize(claim)
    if not claim_tokens:
        return 0.0
    context_tokens = _tokenize(context)
    if not context_tokens:
        return 0.0
    shared = claim_tokens & context_tokens
    return len(shared) / float(len(claim_tokens))


@dataclass(slots=True)
class GroundingResult:
    """Outcome of a grounding-coverage evaluation."""

    coverage: float
    total_claims: int
    grounded_claims: int
    supported: List[str] = field(default_factory=list)
    unsupported: List[str] = field(default_factory=list)


def grounding_coverage(
    answer: str, contexts: Sequence[str], *, threshold: float = 0.5
) -> GroundingResult:
    """Compute the fraction of answer claims supported by the contexts.

    Parameters
    ----------
    answer:
        The generated answer text.
    contexts:
        The retrieved context blocks the answer should be grounded in.
    threshold:
        Minimum claim-token overlap with a single context to count as grounded.
    """
    claims = split_claims(answer)
    if not claims:
        return GroundingResult(coverage=0.0, total_claims=0, grounded_claims=0)
    supported: List[str] = []
    unsupported: List[str] = []
    for claim in claims:
        best = max((token_overlap(claim, ctx) for ctx in contexts), default=0.0)
        if best >= threshold:
            supported.append(claim)
        else:
            unsupported.append(claim)
    grounded = len(supported)
    return GroundingResult(
        coverage=grounded / float(len(claims)),
        total_claims=len(claims),
        grounded_claims=grounded,
        supported=supported,
        unsupported=unsupported,
    )
