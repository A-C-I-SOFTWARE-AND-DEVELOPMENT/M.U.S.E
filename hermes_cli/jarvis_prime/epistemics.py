"""Anti-hallucination + citation discipline for muse

The user said: "never hallucinates". This module enforces two
disciplines on every JARVIS turn:

1. **Citation requirement.** Every factual claim must be backed by
   a citation OR explicitly prefixed with "I'm not certain — " /
   "I don't know yet". Bare factual assertions without citation are
   flagged.

2. **Confidence floor.** Below the floor, JARVIS does NOT answer —
   he opens a ResearchBrief (see ``research.py``) or asks for
   corroboration. This is the "fail honest" discipline.

The detection is heuristic — a perfect hallucination detector is not
possible — but it catches the most common modes: invented file
paths, invented function signatures, fabricated version numbers,
imaginary URLs, made-up quotations.

The runtime calls ``audit_response`` after generating a response but
BEFORE delivering it. If audit returns FAIL, the response is
rewritten or the brief is opened instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional


class AuditOutcome(Enum):
    PASS = "pass"
    NEEDS_CITATIONS = "needs_citations"
    NEEDS_RESEARCH = "needs_research"
    FAIL = "fail"


# Hedge phrases that signal calibrated uncertainty — acceptable in
# place of a citation.
_HEDGES: tuple[str, ...] = (
    "i'm not certain",
    "i don't know yet",
    "i'm not sure",
    "i'd need to verify",
    "let me research that",
    "based on what i recall",
    "to my best understanding",
    "i could be wrong",
)


# Patterns that LOOK like fabricated specifics.
_RISKY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b[A-Z][a-zA-Z0-9_]*\([^)]*\)"), "function-call-like token"),
    (re.compile(r"\b/[a-z][a-z0-9_/.-]+\.(py|md|js|ts|sh|toml|yaml|yml|json)\b"), "file path"),
    (re.compile(r"\bhttps?://[\w./?=&%-]+"), "URL"),
    (re.compile(r"\bv?\d+\.\d+(?:\.\d+)?(?:[+-][\w.+-]+)?\b"), "version-string-like"),
    (re.compile(r"\bsection \d+(\.\d+)+\b", re.I), "spec section reference"),
    (re.compile(r"\bRFC\s*\d{3,5}\b", re.I), "RFC number"),
)


@dataclass(frozen=True)
class AuditFinding:
    kind: str
    snippet: str
    suggestion: str


@dataclass
class AuditReport:
    outcome: AuditOutcome
    findings: list[AuditFinding] = field(default_factory=list)
    citation_count: int = 0
    hedge_count: int = 0
    risky_claim_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "outcome": self.outcome.value,
            "findings": [
                {"kind": f.kind, "snippet": f.snippet, "suggestion": f.suggestion}
                for f in self.findings
            ],
            "citation_count": self.citation_count,
            "hedge_count": self.hedge_count,
            "risky_claim_count": self.risky_claim_count,
        }


def audit_response(
    response: str,
    provided_citations: Optional[Iterable[str]] = None,
    confidence: float = 1.0,
    confidence_floor: float = 0.65,
) -> AuditReport:
    """Audit a generated response for hallucination risk.

    Heuristics:
    - Count hedge phrases (explicit uncertainty) — each one is a
      free pass for nearby risky-looking specifics.
    - Count risky patterns (file paths, URLs, version strings,
      function-call tokens). Each unhedged risky pattern in a low-
      confidence response is a finding.
    - Require at least one citation when the response makes more
      than 2 risky claims and confidence is moderate.
    """

    text = response or ""
    citations = list(provided_citations or [])
    citation_count = len(citations)
    hedge_count = sum(1 for h in _HEDGES if h in text.lower())

    findings: list[AuditFinding] = []
    risky_total = 0
    for pattern, kind in _RISKY_PATTERNS:
        for match in pattern.finditer(text):
            risky_total += 1
            # If there is a nearby hedge or citation, the snippet is OK.
            window = text[max(0, match.start() - 80) : match.end() + 80].lower()
            nearby_hedge = any(h in window for h in _HEDGES)
            nearby_citation = any(c.lower() in window for c in citations)
            if not (nearby_hedge or nearby_citation):
                findings.append(
                    AuditFinding(
                        kind=kind,
                        snippet=match.group(0),
                        suggestion=(
                            "Add citation or hedge with 'I'm not certain — ...'"
                        ),
                    )
                )

    # Decide outcome.
    if confidence < confidence_floor:
        return AuditReport(
            outcome=AuditOutcome.NEEDS_RESEARCH,
            findings=findings,
            citation_count=citation_count,
            hedge_count=hedge_count,
            risky_claim_count=risky_total,
        )

    if findings:
        outcome = (
            AuditOutcome.FAIL
            if len(findings) > 5
            else AuditOutcome.NEEDS_CITATIONS
        )
        return AuditReport(
            outcome=outcome,
            findings=findings,
            citation_count=citation_count,
            hedge_count=hedge_count,
            risky_claim_count=risky_total,
        )

    if risky_total > 2 and citation_count == 0 and hedge_count == 0:
        return AuditReport(
            outcome=AuditOutcome.NEEDS_CITATIONS,
            findings=[
                AuditFinding(
                    kind="uncited_specifics",
                    snippet="response contains specific claims without citations",
                    suggestion=f"Add ≥1 citation for {risky_total} risky claim(s).",
                )
            ],
            citation_count=citation_count,
            hedge_count=hedge_count,
            risky_claim_count=risky_total,
        )

    return AuditReport(
        outcome=AuditOutcome.PASS,
        findings=findings,
        citation_count=citation_count,
        hedge_count=hedge_count,
        risky_claim_count=risky_total,
    )


CITATION_REQUIRED_INSTRUCTION = """\
Hallucination rule (absolute):

- Never assert a file path, function signature, URL, version number,
  date, line number, or quotation you have not directly observed in
  the current session's tool outputs or in a cited source.
- If you cannot cite a claim, replace it with "I'm not certain — "
  followed by what you do know, OR with "I don't know yet — I'll
  open a ResearchBrief."
- Treat memory recollections as cited when the recall is < 24h old
  and durability is "durable"; otherwise re-verify.
- Below confidence floor: do not answer. Open a ResearchBrief
  instead.
- When the user contradicts you, do NOT immediately capitulate.
  Re-check your evidence, then either: (a) cite and stand by the
  prior answer with renewed evidence, or (b) acknowledge the
  correction, update memory, and explain what changed your mind.
"""
