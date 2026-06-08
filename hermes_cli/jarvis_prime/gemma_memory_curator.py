"""Gemma 4 memory-curator lane for MUSE.

Deterministic capture (:mod:`hermes_cli.jarvis_prime.memory_capture`) is and
stays the **safety baseline**. This module lets a *local* Gemma model *enhance*
memory capture — proposing cleaner titles, normalized summaries, namespaces,
tags, contradiction candidates and freshness hints — **without** ever weakening
the gates:

* Every Gemma suggestion is written **SESSION / PROPOSED** only (via the same
  ``capture_to_tree`` path), so it can never become durable memory directly.
* Gemma output is **low-trust** (``SourceTrust.COMMUNITY``) and capped below the
  durable-confidence floor, so a model's own words can't self-promote.
* Gemma never resolves contradictions — it only flags a *candidate*; the owner
  resolves.
* Model "thinking"/scratchpad blocks are stripped *before* anything is
  extracted, written, persisted, logged, or scored.

The module is stdlib-only at import time. The model call is fully injectable
(``runner``): with no runner the curator is an inert no-op, so normal tests need
no model, no Ollama, and no network.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from hermes_cli.jarvis_prime.memory_capture import MemoryCandidate, capture_to_tree
from hermes_cli.jarvis_prime.memory_tree import (
    MemoryNamespace,
    MemoryTreeStore,
    MemoryWriteResult,
    SourceTrust,
)

# A callable that takes a prompt and returns the model's raw text. Injectable so
# tests never touch a real model. ``None`` ⇒ the curator is a no-op.
GemmaRunner = Callable[[str], str]

# Gemma-originated memory is low-trust and capped well below the durable floor
# (0.6) so it can never self-promote.
_MAX_GEMMA_CONFIDENCE = 0.45

# Hard cap on proposals accepted from a single turn — keeps the curator
# high-precision and bounds the blast radius of a misbehaving model.
_MAX_PROPOSALS = 6

_VALID_NAMESPACES = frozenset(n.value for n in MemoryNamespace)
_DEFAULT_NAMESPACE = MemoryNamespace.GENERAL.value

# Thought / scratchpad block patterns. Stripped before extraction or write.
_THOUGHT_BLOCK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?is)<think>.*?</think>"),
    re.compile(r"(?is)<thinking>.*?</thinking>"),
    re.compile(r"(?is)<scratchpad>.*?</scratchpad>"),
    re.compile(r"(?is)<reasoning>.*?</reasoning>"),
    re.compile(r"(?is)\[think(?:ing)?\].*?\[/think(?:ing)?\]"),
    re.compile(r"(?is)```th(?:ink|ought)\b.*?```"),
)
# Leading "Reasoning:/Thought:/Chain of thought:" prefaces up to a blank line or
# an explicit answer marker.
_THOUGHT_PREFACE = re.compile(
    r"(?im)^\s*(?:reasoning|thought|thoughts|chain[ -]of[ -]thought|"
    r"let me think[^\n]*|scratchpad)\s*:.*?(?:\n\s*\n|\Z)"
)


def strip_gemma_thought_blocks(text: str) -> str:
    """Remove model thinking / scratchpad blocks, returning the answer text.

    Idempotent and defensive: anything that isn't a recognised thought block is
    left untouched. Run this on *every* Gemma output before it influences memory,
    persistence, logs, scorecards, or guardrail evidence.
    """
    if not text:
        return ""
    out = text
    for pat in _THOUGHT_BLOCK_PATTERNS:
        out = pat.sub(" ", out)
    out = _THOUGHT_PREFACE.sub("", out)
    # Collapse the whitespace the removals leave behind.
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


@dataclass(frozen=True)
class GemmaCuratorProposal:
    """A proposed memory improvement from the Gemma curator (advisory)."""

    title: str
    summary: str
    namespace: str = _DEFAULT_NAMESPACE
    tags: tuple[str, ...] = field(default_factory=tuple)
    contradiction_candidate: Optional[str] = None
    freshness_due: Optional[str] = None
    source_note: Optional[str] = None
    confidence: float = 0.4

    def normalized(self) -> "GemmaCuratorProposal":
        """Sanitize text fields and clamp trust to the low-trust ceiling."""
        ns = self.namespace if self.namespace in _VALID_NAMESPACES else _DEFAULT_NAMESPACE
        return GemmaCuratorProposal(
            title=strip_gemma_thought_blocks(self.title)[:80],
            summary=strip_gemma_thought_blocks(self.summary),
            namespace=ns,
            tags=tuple(t for t in self.tags if t),
            contradiction_candidate=(
                strip_gemma_thought_blocks(self.contradiction_candidate)
                if self.contradiction_candidate
                else None
            ),
            freshness_due=self.freshness_due,
            source_note=(
                strip_gemma_thought_blocks(self.source_note)
                if self.source_note
                else None
            ),
            confidence=max(0.0, min(_MAX_GEMMA_CONFIDENCE, float(self.confidence))),
        )

    def to_candidate(self, *, source_uri: Optional[str] = None) -> MemoryCandidate:
        """Convert to a low-trust, session/proposed MemoryCandidate.

        ``owner_originated=False`` and ``SourceTrust.COMMUNITY`` guarantee the
        suggestion stays below the durable floor — it is a *proposal*, not a fact.
        """
        norm = self.normalized()
        body = norm.summary or norm.title
        if norm.source_note:
            body = f"{body}\n\n[gemma-curator] {norm.source_note}"
        tags = ("gemma-curator", "proposed", *norm.tags)
        if norm.contradiction_candidate:
            tags = (*tags, "contradiction-candidate")
        return MemoryCandidate(
            kind="research_finding",  # non-durable-worthy kind; owner must approve
            namespace=norm.namespace,
            title=norm.title or "gemma curator note",
            text=body,
            confidence=norm.confidence,
            source_trust=SourceTrust.COMMUNITY,
            owner_originated=False,
            source_uri=source_uri,
            tags=tags,
        )


def _default_parser(raw: str) -> list[GemmaCuratorProposal]:
    """Parse a model's JSON proposal list. Tolerant: bad output ⇒ no proposals."""
    text = strip_gemma_thought_blocks(raw)
    # Find the first JSON array/object in the text.
    match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return []
    if isinstance(data, dict):
        data = data.get("proposals", [data])
    if not isinstance(data, list):
        return []
    out: list[GemmaCuratorProposal] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        summary = str(item.get("summary", "")).strip()
        if not (title or summary):
            continue
        tags = item.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        out.append(
            GemmaCuratorProposal(
                title=title or summary[:60],
                summary=summary,
                namespace=str(item.get("namespace", _DEFAULT_NAMESPACE)),
                tags=tuple(str(t) for t in tags),
                contradiction_candidate=(
                    str(item["contradiction_candidate"])
                    if item.get("contradiction_candidate")
                    else None
                ),
                freshness_due=(
                    str(item["freshness_due"]) if item.get("freshness_due") else None
                ),
                source_note=(
                    str(item["source_note"]) if item.get("source_note") else None
                ),
                confidence=float(item.get("confidence", 0.4) or 0.4),
            )
        )
    return out[:_MAX_PROPOSALS]


def _build_prompt(
    turn_text: str,
    deterministic_candidates: Iterable[MemoryCandidate],
    context_pack: Optional[str],
) -> str:
    det = "\n".join(f"- {c.kind}: {c.title}" for c in deterministic_candidates)
    ctx = f"\n\nKnown context:\n{context_pack}" if context_pack else ""
    return (
        "You are a memory curator. Propose at most 6 durable-worthy memory "
        "improvements as a JSON array. Each item: {title, summary, namespace, "
        "tags, contradiction_candidate, freshness_due, source_note, confidence}. "
        "Do NOT include secrets or chain-of-thought. Return JSON only.\n\n"
        f"Turn:\n{turn_text}\n\nDeterministic candidates:\n{det or '(none)'}{ctx}"
    )


def curate(
    turn_text: str,
    *,
    source_uri: Optional[str] = None,
    deterministic_candidates: Iterable[MemoryCandidate] = (),
    context_pack: Optional[str] = None,
    runner: Optional[GemmaRunner] = None,
    parser: Callable[[str], list[GemmaCuratorProposal]] = _default_parser,
) -> list[GemmaCuratorProposal]:
    """Ask a local Gemma model for memory improvements (proposals only).

    With ``runner=None`` this is a no-op (returns ``[]``) — so it is safe and
    inert by default and in tests. The runner's output is sanitized of thought
    blocks before parsing, and every proposal is normalized (trust clamped,
    namespace validated). Never raises.
    """
    if runner is None:
        return []
    try:
        prompt = _build_prompt(turn_text, deterministic_candidates, context_pack)
        raw = runner(prompt)
        proposals = parser(raw or "")
    except Exception:  # pragma: no cover - curation never breaks a turn
        return []
    return [p.normalized() for p in proposals][:_MAX_PROPOSALS]


def capture_curator_proposals(
    store: MemoryTreeStore,
    proposals: Iterable[GemmaCuratorProposal],
    *,
    source_uri: Optional[str] = None,
) -> list[MemoryWriteResult]:
    """Write curator proposals as SESSION / PROPOSED nodes (owner-gated durable).

    Reuses ``capture_to_tree`` so the secret / chain-of-thought / sensitivity
    write policy applies. Rejections are returned, never raised.
    """
    candidates = [p.to_candidate(source_uri=source_uri) for p in proposals]
    return capture_to_tree(store, candidates)


__all__ = [
    "GemmaRunner",
    "GemmaCuratorProposal",
    "strip_gemma_thought_blocks",
    "curate",
    "capture_curator_proposals",
]
