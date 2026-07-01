"""Challenge Contract — a pure, opt-in detector for MUSE's contrarian duty.

The Constitution and persona forbid MUSE from behaving as a yes-man: it "does
not automatically agree; challenges weak ideas plainly and strengthens rough
ones" (clause ``C2``), "behaves as a trusted partner/advisor, not a yes-man"
(clause ``C4``), and "challenges the idea, not the person" (clause ``C31``).
The Critic Mode rules in ``docs/jarvis-prime-operating-system.md`` spell out the
concrete shapes that challenge can take — name the strongest objection, give a
better version of the idea, narrow scope, push bigger, and say what not to do
yet.

This module lands the *typed contract* for that duty plus a **pure detector**
that measures whether an already-generated response satisfies it. For any
**non-trivial** request (a decision, plan, build, or strategy call), MUSE should
produce at least one challenge element drawn from six named categories:

======================  ===================================================
category                intent
======================  ===================================================
``STRONGER_VERSION``    a stronger / bigger version of the idea
``NAMED_RISK``          a named risk, objection, or failure mode
``SCOPE_REDUCTION``     a scope reduction (narrow / cut / defer part)
``COUNTERPROPOSAL``     a concrete alternative approach
``EVIDENCE_GAP``        a missing-evidence / unverified-assumption flag
``DEFER``               a "do not do this yet" hold
======================  ===================================================

**Trivial** requests (greetings, acknowledgements, simple factual lookups) are
*exempt* — challenging them would be noise, not partnership — so they are
auto-satisfied.

Design constraints (all enforced here):

- **Pure & deterministic & offline.** :func:`evaluate_challenge_contract` and
  :func:`classify_request_triviality` perform no model call, no I/O, and no
  randomness — they only read the text handed to them and return a structured
  result. Identical input ⇒ identical output.
- **Additive & always-inspection (no enforcement gate).** This module changes
  no default behavior on its own. It exposes **pure inspection** only —
  :func:`evaluate_challenge_contract` and :func:`classify_request_triviality` —
  and is wired *nowhere* on the hot response path. There is deliberately **no**
  ``challenge_contract_enabled`` flag: the detector is a signal source, not a
  gate, so the only consumer (the offline self-audit footer scorer in
  :mod:`hermes_cli.jarvis_prime.self_audit.live_scorer`) simply calls the
  detector whenever the *footer itself* is enabled
  (``display.self_audit_footer.enabled`` / ``MUSE_SELF_AUDIT_FOOTER``). See the
  "MUSE feature flags" section of ``docs/jarvis_architecture/MUSE_PRIME_VNEXT.md``
  for the full flag registry.
- **Boundary-aware detection.** Category markers are matched with word/phrase
  boundaries (see :func:`_compile_markers`) so a short marker never
  false-positives inside an unrelated word (``risk`` in ``brisk``, ``cut`` in
  ``executed``).

The detector is inspectable infra: it is wired *nowhere* on the hot response
path by default, so the default runtime output is byte-for-byte unchanged. A
caller may consult it to decide whether to regenerate; that decision is the
caller's, not this module's.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ChallengeElement(Enum):
    """The six challenge-element categories a non-trivial reply may satisfy.

    A reply satisfies the Challenge Contract when it contains at least one of
    these. The categories mirror the Critic / Strategy mode rules in
    ``docs/jarvis-prime-operating-system.md`` and Constitution clauses
    ``C2``/``C4``/``C31``.
    """

    STRONGER_VERSION = "stronger_version"
    NAMED_RISK = "named_risk"
    SCOPE_REDUCTION = "scope_reduction"
    COUNTERPROPOSAL = "counterproposal"
    EVIDENCE_GAP = "evidence_gap"
    DEFER = "defer"


class RequestTriviality(Enum):
    """Whether a request is trivial (contract-exempt) or non-trivial (bound)."""

    TRIVIAL = "trivial"
    NON_TRIVIAL = "non_trivial"


# Per-category detection markers. Case-insensitive whole-word / whole-phrase
# signals (matched with word boundaries, see ``_compile_markers``). Kept small
# and high-precision so a marker only fires when the reply genuinely carries
# that flavour of challenge.
_STRONGER_VERSION_MARKERS: tuple[str, ...] = (
    "stronger version",
    "bigger version",
    "better version",
    "go bigger",
    "think bigger",
    "push bigger",
    "more ambitious",
    "raise the ambition",
    "aim higher",
    "the stronger play",
    "the bolder move",
    "you could go further",
    "take it further",
)

_NAMED_RISK_MARKERS: tuple[str, ...] = (
    # Polarity-bearing phrase forms only — a bare "risk" also matches the
    # yes-man reply "no risk, ship it", so require the word to sit inside a
    # phrase that actually names a risk (see F1 / the negation+agreement guard
    # in ``evaluate_challenge_contract``).
    "the risk is",
    "the risk here",
    "a risk is",
    "risk of",
    "real risk",
    "the objection",
    "strongest objection",
    "failure mode",
    "fails if",
    "breaks if",
    "downside",
    "the danger",
    "fatal flaw",
    "blind spot",
    "weakness",
    "this could backfire",
    "the concern is",
    "watch out for",
    "the trap",
)

_SCOPE_REDUCTION_MARKERS: tuple[str, ...] = (
    "narrow the scope",
    "narrow scope",
    "reduce scope",
    "cut scope",
    "smaller scope",
    "trim it down",
    "cut this down",
    "descope",
    "drop the",
    "leave out",
    "smaller first step",
    "start smaller",
    "ship less",
    "do less",
)

_COUNTERPROPOSAL_MARKERS: tuple[str, ...] = (
    "counterproposal",
    "counter-proposal",
    # A bare "instead" fires on agreement noise; require the polarity-bearing
    # forms that introduce a concrete alternative — a leading "instead," (comma
    # redirect), "instead of X", or "instead, I'd…".
    "instead,",
    "instead, i'd",
    "instead i'd",
    "instead, i would",
    "instead of",
    "a better approach",
    "an alternative",
    "the alternative",
    "i'd propose",
    "id propose",
    "rather than",
    "what if you",
    "consider doing",
    "a different path",
    "another option",
)

_EVIDENCE_GAP_MARKERS: tuple[str, ...] = (
    "no evidence",
    "unverified",
    "unproven",
    "assumption",
    # A bare "assumes" can appear in agreement ("everyone assumes it's great");
    # require the polarity-bearing forms that flag an unverified assumption.
    "assumes that",
    "this assumes",
    "you're assuming",
    "youre assuming",
    "untested",
    "not validated",
    "need data",
    "we don't know",
    "we dont know",
    "missing evidence",
    "evidence gap",
    "no proof",
    "unsubstantiated",
    "citation needed",
)

_DEFER_MARKERS: tuple[str, ...] = (
    "do not do this yet",
    "don't do this yet",
    "dont do this yet",
    # A bare "not yet" reads as agreement in "no downside, not yet a problem";
    # require the hold-bearing phrase forms.
    "not yet — ",
    "not yet -",
    "don't ship yet",
    "dont ship yet",
    "do not ship yet",
    "hold off",
    "wait until",
    "defer this",
    "premature",
    "too early",
    "should not do yet",
    "shouldn't do yet",
    "not the time",
    "park this",
)

_ELEMENT_MARKERS: dict[ChallengeElement, tuple[str, ...]] = {
    ChallengeElement.STRONGER_VERSION: _STRONGER_VERSION_MARKERS,
    ChallengeElement.NAMED_RISK: _NAMED_RISK_MARKERS,
    ChallengeElement.SCOPE_REDUCTION: _SCOPE_REDUCTION_MARKERS,
    ChallengeElement.COUNTERPROPOSAL: _COUNTERPROPOSAL_MARKERS,
    ChallengeElement.EVIDENCE_GAP: _EVIDENCE_GAP_MARKERS,
    ChallengeElement.DEFER: _DEFER_MARKERS,
}


# Triviality signals. A request is trivial when it is a greeting / ack / thanks
# or a simple factual lookup. These markers upweight "trivial"; the decision
# markers below upweight "non-trivial". Matched with word boundaries.
_TRIVIAL_MARKERS: tuple[str, ...] = (
    "hi",
    "hey",
    "hello",
    "yo",
    "thanks",
    "thank you",
    "thx",
    "ok",
    "okay",
    "got it",
    "sounds good",
    "good morning",
    "good night",
    "cool",
    "nice",
    "what time",
    "what is the date",
    "what's the date",
    "how do you spell",
    "when did",
    "how far",
)

# Short-lookup verbs. These read as a trivial factual lookup ("define REST",
# "who is the CEO") ONLY when the whole request is short. Behind a longer
# request they head a substantive ask ("define the architecture for…") and must
# NOT force trivial (F2), so they are matched only inside the ``<=6 words``
# branch of :func:`classify_request_triviality`.
_LOOKUP_MARKERS: tuple[str, ...] = (
    "define",
    "what does",
    "what's",
    "whats",
    "who is",
    "who's",
    "whos",
)

# Non-trivial signals — a decision, plan, build, or strategy call. These are
# the requests the Challenge Contract binds.
_NON_TRIVIAL_MARKERS: tuple[str, ...] = (
    "should i",
    "should we",
    "decide",
    "decision",
    "plan",
    "strategy",
    "strategize",
    "build",
    "implement",
    "design",
    "architect",
    "refactor",
    "launch",
    "ship",
    "roadmap",
    "prioritize",
    "invest",
    "hire",
    "pricing",
    "positioning",
    "trade-off",
    "tradeoff",
    "which approach",
    "approach",
    "best way to",
    "how should",
    "worth it",
    "go big",
    "pivot",
    "migrate",
    "migration",
    "rewrite",
    "scale",
    # F2: substantive design / decision stems so a long "define the architecture
    # for..." reads as non-trivial rather than a bare lookup. These are the
    # whole-word forms of the ``architect`` / ``migrat`` / ``rollout`` /
    # ``approach`` / ``strateg`` / ``design`` stems.
    "architecture",
    "architectural",
    "rollout",
    "roll out",
    "strategic",
)


@dataclass(frozen=True)
class ChallengeViolation:
    """The structured "missing challenge" violation.

    Emitted when a non-trivial request's reply contains no challenge element.
    ``code`` is a stable machine identifier; ``message`` is a human-readable
    one-liner; ``expected`` lists the category names any one of which would
    have satisfied the contract.
    """

    code: str
    message: str
    expected: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "expected": list(self.expected),
        }


@dataclass(frozen=True)
class ChallengeContractResult:
    """The structured result of inspecting a reply against the contract.

    ``satisfied`` is True when the request was trivial (exempt) or the reply
    carried at least one challenge element. ``found`` lists the categories
    detected (empty for a trivial/exempt reply). ``exempt`` records whether the
    request was treated as trivial. ``violation`` is populated only when the
    contract is *not* satisfied.
    """

    satisfied: bool
    exempt: bool
    found: tuple[str, ...] = field(default_factory=tuple)
    violation: Optional[ChallengeViolation] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "satisfied": self.satisfied,
            "exempt": self.exempt,
            "found": list(self.found),
            "violation": self.violation.to_dict() if self.violation else None,
        }


# Apostrophe variants that must all fold to the straight ASCII apostrophe so a
# curly ``don't`` in polished output still matches an ASCII ``don't`` marker
# (F4). Covers U+2019 (right single quote), U+2018 (left), U+02BC (modifier
# letter apostrophe).
_APOSTROPHES = "’‘ʼ"
_APOSTROPHE_RE = re.compile("[" + _APOSTROPHES + "]")


def _normalize_apostrophes(text: str) -> str:
    """Fold curly / modifier apostrophes to a straight ASCII apostrophe."""
    return _APOSTROPHE_RE.sub("'", text or "")


def _compile_markers(markers: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    """Compile each marker into a word-boundary-aware, case-insensitive pattern.

    Plain substring matching false-positives short markers inside unrelated
    words (``risk`` in ``brisk``, ``cut`` in ``executed``, ``defer`` in
    ``deference``). Anchoring each marker with ``\\b`` on both sides makes a
    marker only count as a whole word / phrase. Multi-word markers still match
    across a normal space because ``re.escape`` preserves the literal space and
    the boundaries land on the outer edges of the phrase. Markers that end in a
    non-word character (an apostrophe form like ``don't``) fall back to an
    inner boundary so the pattern still anchors cleanly.
    """
    compiled: list[re.Pattern[str]] = []
    for marker in markers:
        stripped = _normalize_apostrophes(marker.strip())
        if not stripped:
            continue
        left = r"\b" if stripped[0].isalnum() else ""
        right = r"\b" if stripped[-1].isalnum() else ""
        compiled.append(
            re.compile(left + re.escape(stripped) + right, re.IGNORECASE)
        )
    return tuple(compiled)


_ELEMENT_PATTERNS: dict[ChallengeElement, tuple[re.Pattern[str], ...]] = {
    element: _compile_markers(markers)
    for element, markers in _ELEMENT_MARKERS.items()
}
_TRIVIAL_PATTERNS: tuple[re.Pattern[str], ...] = _compile_markers(_TRIVIAL_MARKERS)
_LOOKUP_PATTERNS: tuple[re.Pattern[str], ...] = _compile_markers(_LOOKUP_MARKERS)
_NON_TRIVIAL_PATTERNS: tuple[re.Pattern[str], ...] = _compile_markers(
    _NON_TRIVIAL_MARKERS
)


def _count_matches(text: str, patterns: tuple[re.Pattern[str], ...]) -> int:
    return sum(1 for pattern in patterns if pattern.search(text))


# Agreement / yes-man cues. A reply that carries one of these — and whose only
# "challenge" markers are negated (``no risk``) — is pure agreement, not a
# challenge (see F1). Matched with word/phrase boundaries.
_AGREEMENT_CUES: tuple[str, ...] = (
    "ship it",
    "go for it",
    "looks perfect",
    "looks great",
    "lgtm",
    "no notes",
    "no downside",
    "no risk",
    "no concerns",
    "no objection",
    "fully agree",
    "totally agree",
    "sounds perfect",
    "no changes needed",
    "great idea",
    "love it",
    "perfect as is",
)
_AGREEMENT_PATTERNS: tuple[re.Pattern[str], ...] = _compile_markers(_AGREEMENT_CUES)

# A short single-token marker preceded by a negation ("no", "not", "without",
# "zero") reads as agreement ("no risk", "without any downside"), not a
# challenge. This pattern captures ``<negation> [filler] <marker>`` so the
# match can be discounted.
_NEGATION_PREFIX = re.compile(
    r"\b(?:no|not|without|zero|little|hardly any|barely any)\b"
    r"(?:\s+\w+){0,2}\s+$",
    re.IGNORECASE,
)


def _is_negated_match(text: str, match: re.Match[str]) -> bool:
    """Return True when the marker at ``match`` is negated (``no <marker>``).

    Looks at the short window of words immediately before the marker; a
    negation cue there ("no risk", "not a real downside") flips the marker's
    polarity so it should NOT count as a challenge.
    """
    prefix = text[: match.start()]
    # Only inspect the tail so an earlier, unrelated "no" doesn't over-suppress.
    tail = prefix[-40:]
    return bool(_NEGATION_PREFIX.search(tail))


def _element_challenges(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    """True when ``text`` contains a genuine (non-negated) marker for a category.

    Reuses the file's word-boundary patterns but discards any single match that
    is negated by a preceding ``no``/``not``/``without`` cue. If every match of
    every marker is negated, the category does not count — this is the F1
    yes-man guard ("no risk, ship it" must not read as a named risk).
    """
    for pattern in patterns:
        for match in pattern.finditer(text):
            if not _is_negated_match(text, match):
                return True
    return False


def classify_request_triviality(
    text: str,
    *,
    effort_class: Any = None,
) -> RequestTriviality:
    """Classify a request as trivial (contract-exempt) or non-trivial.

    Pure, deterministic, offline: no model call, no I/O. A request is
    **trivial** — and therefore exempt from the Challenge Contract — when it is
    a greeting, acknowledgement, or simple factual lookup. It is **non-trivial**
    when it asks for a decision, plan, build, or strategy call.

    Heuristic (deterministic):

    - Empty / whitespace-only text → trivial (nothing to challenge).
    - Any non-trivial decision/plan/build/strategy marker present → non-trivial.
    - Otherwise, if a trivial greeting/ack/lookup marker is present and no
      non-trivial marker is → trivial.
    - A short question with no non-trivial marker → trivial (a simple lookup).
    - Everything else defaults to non-trivial, so the contract errs toward
      *asking* MUSE to challenge rather than letting a real request slip through
      exempt.

    ``effort_class`` is an optional hint: an
    :class:`~hermes_cli.jarvis_prime.effort_class.EffortClass` (or its ``"E0"``
    string). ``E0`` (direct answer, no council) nudges toward trivial when the
    text itself carries no non-trivial marker; anything ``E1`` and up is a real
    routed request and never downgraded to trivial by the effort hint. The hint
    never *overrides* an explicit non-trivial marker.
    """
    stripped = _normalize_apostrophes((text or "").strip())
    if not stripped:
        return RequestTriviality.TRIVIAL

    non_trivial_hits = _count_matches(stripped, _NON_TRIVIAL_PATTERNS)
    if non_trivial_hits:
        return RequestTriviality.NON_TRIVIAL

    trivial_hits = _count_matches(stripped, _TRIVIAL_PATTERNS)
    if trivial_hits:
        return RequestTriviality.TRIVIAL

    is_short = len(stripped.split()) <= 6

    # Short-lookup verbs (``define`` / ``who is`` / ``what does`` / ``what's``)
    # only read as trivial when the whole request is short (F2). Behind a long
    # request they head a substantive design/decision ask ("define the
    # architecture for…") and must NOT force trivial.
    if is_short and _count_matches(stripped, _LOOKUP_PATTERNS):
        return RequestTriviality.TRIVIAL

    # Effort hint: E0 (direct answer) with no non-trivial marker → trivial.
    rank = _effort_rank(effort_class)
    if rank is not None and rank == 0:
        return RequestTriviality.TRIVIAL

    # A short prompt with no decision/plan/build marker reads as a simple
    # lookup; use a conservative word-count threshold.
    if is_short:
        return RequestTriviality.TRIVIAL

    # Default: treat as non-trivial so a real request is never silently exempt.
    return RequestTriviality.NON_TRIVIAL


def _effort_rank(effort: Any) -> Optional[int]:
    """Extract an integer effort rank from an EffortClass, ``"E<n>"``, or None."""
    if effort is None:
        return None
    rank = getattr(effort, "rank", None)
    if rank is not None:
        try:
            return int(rank)
        except (TypeError, ValueError):
            return None
    text = str(effort).strip().upper()
    if text.startswith("E") and text[1:].isdigit():
        return int(text[1:])
    return None


def evaluate_challenge_contract(
    response_text: str,
    *,
    request_is_trivial: bool = False,
) -> ChallengeContractResult:
    """Inspect an already-generated ``response_text`` against the contract.

    Pure, deterministic, offline: no model call, no I/O. Returns a
    :class:`ChallengeContractResult`.

    - When ``request_is_trivial`` is True the request is **exempt**: the result
      is auto-satisfied with no violation, regardless of the reply's content.
    - Otherwise the reply satisfies the contract when it contains at least one
      of the six :class:`ChallengeElement` categories (boundary-aware marker
      detection — no plain-substring false positives). ``found`` lists every
      category detected.
    - A non-trivial reply carrying **no** challenge element fails the contract
      and carries a ``missing_challenge`` :class:`ChallengeViolation` naming the
      categories any one of which would have satisfied it.

    Detection changes nothing on its own; a caller decides what to do with a
    violation.
    """
    if request_is_trivial:
        return ChallengeContractResult(satisfied=True, exempt=True, found=())

    stripped = _normalize_apostrophes((response_text or "").strip())
    found: list[str] = []
    if stripped:
        for element in ChallengeElement:
            patterns = _ELEMENT_PATTERNS[element]
            if _element_challenges(stripped, patterns):
                found.append(element.value)

    if found:
        return ChallengeContractResult(
            satisfied=True,
            exempt=False,
            found=tuple(found),
        )

    violation = ChallengeViolation(
        code="missing_challenge",
        message=(
            "Non-trivial request answered with no challenge element — MUSE "
            "must offer at least one of: a stronger version, a named risk, a "
            "scope reduction, a counterproposal, an evidence gap, or a "
            "'do not do this yet'."
        ),
        expected=tuple(element.value for element in ChallengeElement),
    )
    return ChallengeContractResult(
        satisfied=False,
        exempt=False,
        found=(),
        violation=violation,
    )


__all__ = [
    "ChallengeElement",
    "RequestTriviality",
    "ChallengeViolation",
    "ChallengeContractResult",
    "classify_request_triviality",
    "evaluate_challenge_contract",
]
