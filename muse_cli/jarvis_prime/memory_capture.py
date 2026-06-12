"""Post-turn memory candidate capture for the live JARVIS loop.

After a completed turn, JARVIS should *notice* durable-worthy facts without
silently committing them. This module turns a (user, assistant) exchange into
typed :class:`MemoryCandidate` objects using deterministic, stdlib-only cue
heuristics — the same style as ``gateway/cockpit/agent.py::_maybe_remember``.

Six candidate kinds are recognised (per the JARVIS memory rules):

* ``user_preference``     → ``jarvis/personal``
* ``project_decision``    → ``jarvis/decisions``     (durable-worthy)
* ``architecture_fact``   → ``jarvis/architecture``  (durable-worthy)
* ``verified_code_fix``   → ``jarvis/code_practice`` (durable-worthy)
* ``research_finding``    → ``jarvis/research``
* ``failed_assumption``   → ``jarvis/operations``

Safety invariants (enforced by ``MemoryTreeStore.write`` downstream, mirrored
here so capture stays honest):

* Candidates are written **session-layer, PROPOSED** — never auto-durable.
  Promotion to durable is owner-gated (``promote_to_durable``).
* Owner/user text is trusted (:class:`SourceTrust.OWNER`); assistant/tool text
  is low-trust so a model's own words can't self-promote to durable memory.
* Secret-like and chain-of-thought content is rejected at write time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

from muse_cli.jarvis_prime.memory_tree import (
    ApprovalState,
    MemoryLayer,
    MemoryNamespace,
    MemorySource,
    MemoryTreeStore,
    MemoryWriteResult,
    SourceTrust,
    canonicalize_text,
)

# Candidate kinds that are worth promoting to durable memory once the owner
# approves them (the rest stay session-scoped continuity aids).
DURABLE_WORTHY = frozenset(
    {"project_decision", "architecture_fact", "verified_code_fix"}
)

# kind -> (namespace, default confidence, durable-worthy)
_KIND_NAMESPACE: dict[str, str] = {
    "user_preference": MemoryNamespace.PERSONAL.value,
    "project_decision": MemoryNamespace.DECISION.value,
    "architecture_fact": MemoryNamespace.ARCHITECTURE.value,
    "verified_code_fix": MemoryNamespace.CODE_PRACTICE.value,
    "research_finding": MemoryNamespace.RESEARCH.value,
    "failed_assumption": MemoryNamespace.OPERATIONS.value,
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
    """

    results: list[MemoryWriteResult] = []
    for cand in candidates:
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
]
