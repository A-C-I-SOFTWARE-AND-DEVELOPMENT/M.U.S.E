"""Post-turn memory candidate capture for the live JARVIS loop.

After a completed turn, JARVIS should *notice* durable-worthy facts without
silently committing them. This module turns a (user, assistant) exchange into
typed :class:`MemoryCandidate` objects using deterministic, stdlib-only cue
heuristics — the same style as ``gateway/cockpit/agent.py::_maybe_remember``.

Candidate taxonomy
------------------

MUSE categorizes every memory candidate into one of six **recommended, named**
kinds (the vNext taxonomy). These are the canonical values every new caller and
surface should use:

* ``durable_preference`` → ``jarvis/personal``     (stable user preferences)
* ``project_direction``  → ``jarvis/decisions``    (durable-worthy; strategy/decisions)
* ``workflow_lesson``    → ``jarvis/operations``   (lessons from procedures/failures)
* ``repo_convention``    → ``jarvis/code_practice``(durable-worthy; recurring conventions)
* ``temporary_context``  → ``jarvis/general``      (session-scoped continuity, never durable)
* ``do_not_store``       → ``jarvis/general``       (must NOT be stored — rejected at write)

Backward compatibility
-----------------------

The taxonomy previously used a different set of names. Those legacy names are
still accepted everywhere a ``kind`` is taken, and map onto the canonical set
via :data:`KIND_ALIASES` so no persisted data or existing caller breaks:

* ``user_preference``   → ``durable_preference``
* ``project_decision``  → ``project_direction``
* ``failed_assumption`` → ``workflow_lesson``
* ``architecture_fact`` and ``verified_code_fix`` and ``research_finding``
  remain valid kinds in their own right (durable-worthiness unchanged); they
  have no direct rename because they are finer-grained than the six.

Safety invariants (enforced by ``MemoryTreeStore.write`` downstream, mirrored
here so capture stays honest):

* Candidates are written **session-layer, PROPOSED** — never auto-durable.
  Promotion to durable is owner-gated (``promote_to_durable``).
* Owner/user text is trusted (:class:`SourceTrust.OWNER`); assistant/tool text
  is low-trust so a model's own words can't self-promote to durable memory.
* Secret-like and chain-of-thought content is rejected at write time. The
  ``do_not_store`` kind is a *named* categorization of exactly that reject
  policy: a candidate may be surfaced/classified as ``do_not_store``, but the
  underlying reject-at-write enforcement in ``MemoryTreeStore.write`` is
  unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

from hermes_cli.jarvis_prime.memory_tree import (
    ApprovalState,
    MemoryLayer,
    MemoryNamespace,
    MemorySource,
    MemoryTreeStore,
    MemoryWriteResult,
    SourceTrust,
    canonicalize_text,
)

# --------------------------------------------------------------------------
# Canonical taxonomy (vNext recommended six kinds)
# --------------------------------------------------------------------------
# These are the first-class, recommended names. Every new caller/surface should
# categorize candidates using one of these.
DURABLE_PREFERENCE = "durable_preference"
PROJECT_DIRECTION = "project_direction"
WORKFLOW_LESSON = "workflow_lesson"
REPO_CONVENTION = "repo_convention"
TEMPORARY_CONTEXT = "temporary_context"
DO_NOT_STORE = "do_not_store"

# The recommended six, in taxonomy order.
CANDIDATE_KINDS = frozenset(
    {
        DURABLE_PREFERENCE,
        PROJECT_DIRECTION,
        WORKFLOW_LESSON,
        REPO_CONVENTION,
        TEMPORARY_CONTEXT,
        DO_NOT_STORE,
    }
)

# Legacy kind names -> canonical name. Kept so no persisted data or existing
# caller breaks; ``canonical_kind`` resolves through this map. Names not present
# here (e.g. ``architecture_fact``) are already canonical in their own right.
KIND_ALIASES: dict[str, str] = {
    "user_preference": DURABLE_PREFERENCE,
    "project_decision": PROJECT_DIRECTION,
    "failed_assumption": WORKFLOW_LESSON,
}

# Every kind value this module recognizes as valid (canonical six + legacy
# aliases + the finer-grained legacy kinds that remain valid on their own).
_LEGACY_STANDALONE_KINDS = frozenset(
    {"architecture_fact", "verified_code_fix", "research_finding"}
)
VALID_KINDS = frozenset(
    CANDIDATE_KINDS | set(KIND_ALIASES) | _LEGACY_STANDALONE_KINDS
)


def canonical_kind(kind: str) -> str:
    """Resolve a (possibly legacy) kind name to its canonical value.

    Legacy names in :data:`KIND_ALIASES` map onto the recommended six; all
    other recognized names are returned unchanged. Unknown names are returned
    as-is (callers may still choose to accept free-form kinds).
    """

    return KIND_ALIASES.get(kind, kind)


def is_valid_kind(kind: str) -> bool:
    """True if ``kind`` (canonical or legacy) is a recognized candidate kind."""

    return kind in VALID_KINDS


# Candidate kinds that are worth promoting to durable memory once the owner
# approves them (the rest stay session-scoped continuity aids). Includes both
# canonical and legacy names so callers using either resolve the same way.
DURABLE_WORTHY = frozenset(
    {
        # canonical
        PROJECT_DIRECTION,
        REPO_CONVENTION,
        # legacy standalone kinds that remain durable-worthy
        "architecture_fact",
        "verified_code_fix",
        # legacy aliases (kept so ``kind in DURABLE_WORTHY`` still holds for
        # any caller that never migrated off the old names)
        "project_decision",
    }
)

# kind -> namespace. Covers the canonical six, the legacy aliases (so existing
# persisted candidates route identically), and the finer-grained legacy kinds.
_KIND_NAMESPACE: dict[str, str] = {
    # canonical six
    DURABLE_PREFERENCE: MemoryNamespace.PERSONAL.value,
    PROJECT_DIRECTION: MemoryNamespace.DECISION.value,
    WORKFLOW_LESSON: MemoryNamespace.OPERATIONS.value,
    REPO_CONVENTION: MemoryNamespace.CODE_PRACTICE.value,
    TEMPORARY_CONTEXT: MemoryNamespace.GENERAL.value,
    DO_NOT_STORE: MemoryNamespace.GENERAL.value,
    # legacy aliases (identical routing to the pre-rename behavior)
    "user_preference": MemoryNamespace.PERSONAL.value,
    "project_decision": MemoryNamespace.DECISION.value,
    "failed_assumption": MemoryNamespace.OPERATIONS.value,
    # finer-grained legacy kinds that remain valid on their own
    "architecture_fact": MemoryNamespace.ARCHITECTURE.value,
    "verified_code_fix": MemoryNamespace.CODE_PRACTICE.value,
    "research_finding": MemoryNamespace.RESEARCH.value,
}

# Ordered cue table. First match wins per sentence so a sentence yields at most
# one candidate. Patterns are deliberately conservative — capture should be
# high-precision (few, confident candidates) rather than high-recall.
_CUES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "user_preference",
        re.compile(
            r"(?i)\b(i prefer|i'd prefer|i like|i want|i'd like|please always|"
            r"from now on|going forward|my name is|call me|remember that i|"
            r"i always|i never)\b"
        ),
    ),
    (
        "verified_code_fix",
        re.compile(
            r"(?i)\b(the fix was|fixed by|root cause was|the bug was|"
            r"resolved by|patched|the tests now pass|tests pass after)\b"
        ),
    ),
    (
        "project_decision",
        re.compile(
            r"(?i)\b(we decided|we've decided|let's go with|we'll use|"
            r"we will use|we chose|decision:|we're going with|"
            r"we are going with|we standardi[sz]e on|we agreed)\b"
        ),
    ),
    (
        "architecture_fact",
        re.compile(
            r"(?i)\b(the architecture|the system uses|is the backend|"
            r"is the canonical|is built on|is implemented in|lives in|"
            r"the data flow|the entry point is)\b"
        ),
    ),
    (
        "research_finding",
        re.compile(
            r"(?i)\b(i found that|research shows|according to|the docs say|"
            r"the documentation says|turns out|it turns out|evidence shows)\b"
        ),
    ),
    (
        "failed_assumption",
        re.compile(
            r"(?i)\b(i was wrong|that assumption was wrong|"
            r"that didn't work|that did not work|doesn't actually|"
            r"does not actually|turned out not to|incorrect assumption|"
            r"my mistake)\b"
        ),
    ),
    # New (additive) cue for the recommended ``repo_convention`` kind. Placed
    # LAST so it only fires on sentences no earlier cue claimed — the existing
    # cues keep their exact precedence and every legacy candidate is byte-for-
    # byte unchanged.
    (
        REPO_CONVENTION,
        re.compile(
            r"(?i)\b(the convention is|our convention|by convention|"
            r"the coding standard|the style guide says|"
            r"we always name|files should live in|"
            r"tests? (?:live|belong) (?:next to|under)|"
            r"the repo convention|the repo standard)\b"
        ),
    ),
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class MemoryCandidate:
    """A typed, provenance-bearing memory candidate extracted from a turn."""

    kind: str
    namespace: str
    title: str
    text: str
    confidence: float
    source_trust: SourceTrust
    owner_originated: bool
    source_uri: Optional[str] = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def durable_worthy(self) -> bool:
        return self.kind in DURABLE_WORTHY

    @property
    def canonical_kind(self) -> str:
        """The recommended-taxonomy name for this candidate's ``kind``.

        Legacy kind names resolve onto the recommended six; finer-grained
        legacy kinds are returned unchanged. Surfaces (cockpit, CLI, Android
        inbox) should display this so every candidate shows one of the named
        kinds without the underlying stored ``kind`` value changing.
        """

        return canonical_kind(self.kind)

    @property
    def is_do_not_store(self) -> bool:
        """True when this candidate is categorized as ``do_not_store``.

        This is a *named categorization only*. The reject-at-write enforcement
        lives in ``MemoryTreeStore.write`` (secret / chain-of-thought / secret
        sensitivity) and is unchanged; a ``do_not_store`` candidate simply
        makes that policy explicit and surfaceable in a proposal.
        """

        return self.kind == DO_NOT_STORE


def _sentences(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _title_for(kind: str, sentence: str) -> str:
    head = canonicalize_text(sentence)
    # A short, stable title: kind + the first few words of the claim.
    words = head.split()
    snippet = " ".join(words[:8])
    return f"{kind.replace('_', ' ')}: {snippet}"[:80]


def _scan(
    text: str,
    *,
    owner: bool,
    source_uri: Optional[str],
) -> list[MemoryCandidate]:
    trust = SourceTrust.OWNER if owner else SourceTrust.COMMUNITY
    # Owner statements are more trustworthy but still below the durable floor
    # (0.6) unless the owner later approves — keeps capture honest.
    base_conf = 0.55 if owner else 0.45
    out: list[MemoryCandidate] = []
    seen: set[str] = set()
    for sentence in _sentences(text):
        for kind, pattern in _CUES:
            if not pattern.search(sentence):
                continue
            key = canonicalize_text(sentence).lower()
            if key in seen:
                break
            seen.add(key)
            ns = _KIND_NAMESPACE[kind]
            out.append(
                MemoryCandidate(
                    kind=kind,
                    namespace=ns,
                    title=_title_for(kind, sentence),
                    text=sentence,
                    confidence=base_conf,
                    source_trust=trust,
                    owner_originated=owner,
                    source_uri=source_uri,
                    tags=("captured", kind),
                )
            )
            break  # one candidate per sentence
    return out


def extract_candidates(
    user_text: str,
    assistant_text: str = "",
    *,
    source_uri: Optional[str] = None,
) -> list[MemoryCandidate]:
    """Extract typed memory candidates from one completed turn.

    User text is trusted (owner-originated); assistant text is low-trust so a
    model's own phrasing cannot self-promote. Deterministic and bounded.
    """

    candidates = _scan(user_text, owner=True, source_uri=source_uri)
    candidates += _scan(assistant_text, owner=False, source_uri=source_uri)
    return candidates


def capture_to_tree(
    store: MemoryTreeStore,
    candidates: Iterable[MemoryCandidate],
) -> list[MemoryWriteResult]:
    """Write candidates to the Tree as SESSION / PROPOSED nodes.

    Each write passes through ``MemoryTreeStore.write`` so the secret /
    chain-of-thought / emotion policy applies. Rejections are returned (with
    ``ok=False``) rather than raised — capture never breaks a turn.

    A candidate categorized as :data:`DO_NOT_STORE` is rejected here without
    ever calling ``store.write`` — it is never persisted. This makes the named
    ``do_not_store`` kind honor the same reject-at-write contract that the
    store's secret / chain-of-thought policy already enforces.
    """

    results: list[MemoryWriteResult] = []
    for cand in candidates:
        if cand.kind == DO_NOT_STORE:
            # Named do_not_store categorization: never write, always reject.
            results.append(
                MemoryWriteResult(
                    ok=False, reasons=("do_not_store: candidate must not be stored",)
                )
            )
            continue
        sources = (
            (MemorySource(uri=cand.source_uri, trust=cand.source_trust),)
            if cand.source_uri
            else ()
        )
        result = store.write(
            cand.text,
            namespace=cand.namespace,
            title=cand.title,
            layer=MemoryLayer.SESSION,
            confidence=cand.confidence,
            source_trust=cand.source_trust,
            sources=sources,
            approval_state=ApprovalState.PROPOSED,
            tags=cand.tags,
        )
        results.append(result)
    return results


__all__ = [
    "MemoryCandidate",
    "DURABLE_WORTHY",
    "extract_candidates",
    "capture_to_tree",
    # Canonical taxonomy (recommended six kinds)
    "CANDIDATE_KINDS",
    "DURABLE_PREFERENCE",
    "PROJECT_DIRECTION",
    "WORKFLOW_LESSON",
    "REPO_CONVENTION",
    "TEMPORARY_CONTEXT",
    "DO_NOT_STORE",
    # Backward-compat helpers
    "KIND_ALIASES",
    "VALID_KINDS",
    "canonical_kind",
    "is_valid_kind",
]
