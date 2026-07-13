"""JARVIS Memory OS — Memory Tree (clean-room, stdlib-only).

This module ships two layers that coexist:

* The original lightweight :class:`MemoryTree` / :class:`MemoryChunk` — a
  stateless, in-memory grouping of source-backed notes used by the
  ``memory-tree`` CLI lane. Kept byte-compatible so existing callers and
  tests do not change.

* The production :class:`MemoryTreeStore` — a durable, provenance-first,
  contradiction-aware Memory Tree implementing the JARVIS Memory OS
  cognition plane. It complements (never replaces) ``memory.MemoryStore``.

Design rules enforced here (see
``docs/jarvis-prime-operating-system.md`` § Memory rules):

* Memory **cites sources**; it never becomes the source of truth.
* New facts **never silently overwrite** old facts — conflicts create a
  :class:`ContradictionReport` and both records become contested.
* Secrets, raw credentials, private keys, session cookies, and
  chain-of-thought are **rejected** before they can be written.
* Durable writes require provenance and a confidence floor unless the
  owner explicitly approved the decision.
* No network calls. Persistence is local JSONL with atomic writes and
  owner-only permissions where the platform supports it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Optional


# ---------------------------------------------------------------------------
# Small deterministic helpers (public API)
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """Cheap, deterministic token estimate (~4 chars/token)."""

    if not text:
        return 0
    # Count word-ish units plus a length component; deterministic and
    # good enough for budget packing without a tokenizer dependency.
    chars = len(text)
    return max(1, (chars + 3) // 4)


def canonicalize_text(text: str) -> str:
    """Collapse whitespace for stable hashing / contradiction keys."""

    return " ".join((text or "").split()).strip()


def stable_memory_id(namespace: str, title: str, text: str) -> str:
    """Deterministic 16-hex id derived from namespace + title + text."""

    raw = f"{namespace}|{title}|{canonicalize_text(text)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _terms(text: str) -> set[str]:
    return {term for term in re.split(r"\W+", (text or "").lower()) if len(term) > 2}


# ---------------------------------------------------------------------------
# Legacy lightweight tree (kept for the `memory-tree` CLI lane + old tests)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemoryChunk:
    """A source-backed chunk of text. Also used as a chunk ref by nodes."""

    namespace: str
    title: str
    text: str
    source_uri: str = "manual"
    confidence: float = 0.5
    tags: tuple[str, ...] = ()
    created_at: str = field(default_factory=_now_iso)

    @property
    def id(self) -> str:
        raw = f"{self.namespace}|{self.title}|{self.source_uri}|{self.text}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "namespace": self.namespace,
            "title": self.title,
            "text": self.text,
            "source_uri": self.source_uri,
            "confidence": self.confidence,
            "tags": list(self.tags),
            "created_at": self.created_at,
        }


@dataclass
class MemoryTree:
    """Lightweight, stateless grouping of source-backed notes."""

    chunks: list[MemoryChunk] = field(default_factory=list)

    def add(
        self,
        text: str,
        *,
        namespace: str,
        title: str,
        source_uri: str = "manual",
        confidence: float = 0.5,
        tags: tuple[str, ...] = (),
    ) -> MemoryChunk | None:
        cleaned = " ".join(text.split())
        if not cleaned:
            return None
        chunk = MemoryChunk(
            namespace=namespace,
            title=title.strip() or "Untitled",
            text=cleaned,
            source_uri=source_uri,
            confidence=max(0.0, min(1.0, confidence)),
            tags=tags,
        )
        self.chunks.append(chunk)
        return chunk

    def search(
        self, query: str, *, namespace: str | None = None, limit: int = 5
    ) -> list[MemoryChunk]:
        query_terms = _terms(query)
        scored: list[tuple[int, MemoryChunk]] = []
        for chunk in self.chunks:
            if namespace and chunk.namespace != namespace:
                continue
            haystack = _terms(" ".join((chunk.title, chunk.text, " ".join(chunk.tags))))
            score = len(query_terms & haystack)
            if score:
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:limit]]

    def outline(self) -> str:
        grouped: dict[str, list[MemoryChunk]] = {}
        for chunk in self.chunks:
            grouped.setdefault(chunk.namespace, []).append(chunk)
        lines: list[str] = []
        for namespace in sorted(grouped):
            lines.append(f"- {namespace}")
            for chunk in grouped[namespace]:
                lines.append(f"  - {chunk.title} ({chunk.source_uri})")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Enumerations for the production store
# ---------------------------------------------------------------------------


class MemoryNamespace(str, Enum):
    """Canonical vault buckets. Free-form namespaces are still allowed."""

    ARCHITECTURE = "jarvis/architecture"
    DECISION = "jarvis/decisions"
    RESEARCH = "jarvis/research"
    SKILL = "jarvis/skills"
    CODE_PRACTICE = "jarvis/code_practice"
    OPERATIONS = "jarvis/operations"
    PERSONAL = "jarvis/personal"
    GENERAL = "jarvis/general"


class MemoryLayer(str, Enum):
    WORKING = "working"
    SESSION = "session"
    DURABLE = "durable"


class SourceTrust(str, Enum):
    OWNER = "owner"  # the owner stated it directly
    PRIMARY = "primary"  # primary source / official spec
    OFFICIAL_DOC = "official_doc"
    REPUTABLE = "reputable"
    COMMUNITY = "community"
    UNVERIFIED = "unverified"

    @property
    def weight(self) -> float:
        return {
            "owner": 1.0,
            "primary": 0.95,
            "official_doc": 0.85,
            "reputable": 0.65,
            "community": 0.4,
            "unverified": 0.2,
        }[self.value]


class SensitivityClass(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    SECRET = "secret"  # never stored — rejected by write policy


class ApprovalState(str, Enum):
    PROPOSED = "proposed"
    OWNER_APPROVED = "owner_approved"
    AUTO = "auto"
    REJECTED = "rejected"


class ContradictionStatus(str, Enum):
    NONE = "none"
    CONTESTED = "contested"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemorySource:
    """Provenance pointer for a memory node."""

    uri: str  # URL or repo path
    trust: SourceTrust = SourceTrust.UNVERIFIED
    excerpt: str = ""  # the cited line(s) — never the whole doc
    line_ref: Optional[str] = None
    retrieved_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, object]:
        return {
            "uri": self.uri,
            "trust": self.trust.value,
            "excerpt": self.excerpt,
            "line_ref": self.line_ref,
            "retrieved_at": self.retrieved_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MemorySource":
        return cls(
            uri=d.get("uri", ""),
            trust=SourceTrust(d.get("trust", "unverified")),
            excerpt=d.get("excerpt", ""),
            line_ref=d.get("line_ref"),
            retrieved_at=d.get("retrieved_at", _now_iso()),
        )


@dataclass
class MemoryNode:
    """A durable/session/working memory node with full provenance."""

    id: str
    namespace: str
    layer: MemoryLayer
    title: str
    summary: str = ""
    text: str = ""
    chunk_refs: tuple[str, ...] = ()
    sources: tuple[MemorySource, ...] = ()
    source_uri: Optional[str] = None
    source_trust: SourceTrust = SourceTrust.UNVERIFIED
    confidence: float = 0.5
    sensitivity: SensitivityClass = SensitivityClass.INTERNAL
    approval_state: ApprovalState = ApprovalState.PROPOSED
    freshness_due: Optional[str] = None
    contradiction_status: ContradictionStatus = ContradictionStatus.NONE
    subject: Optional[str] = None  # contradiction-grouping key
    supersedes: tuple[str, ...] = ()
    superseded_by: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    tags: tuple[str, ...] = ()

    @property
    def contested(self) -> bool:
        return self.contradiction_status == ContradictionStatus.CONTESTED

    @property
    def active(self) -> bool:
        return (
            self.superseded_by is None and self.approval_state != ApprovalState.REJECTED
        )

    @property
    def awaiting_review(self) -> bool:
        """Captured but not yet cleared for live recall.

        ``observe_turn`` writes captured facts as **session/working-layer,
        PROPOSED** candidates that await the owner's approval (typically on
        mobile). Until the owner accepts or rejects them they must not feed
        back into the prompt as plain context, or an unreviewed — possibly
        assistant-originated — "memory" could steer later responses.

        Durable nodes are *not* awaiting review: the durable write gate
        already required provenance (or owner approval) plus the confidence
        floor before they could be committed. Owner-approved / auto nodes are
        likewise cleared.
        """

        if self.approval_state != ApprovalState.PROPOSED:
            return False
        return self.layer != MemoryLayer.DURABLE

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "namespace": self.namespace,
            "layer": self.layer.value,
            "title": self.title,
            "summary": self.summary,
            "text": self.text,
            "chunk_refs": list(self.chunk_refs),
            "sources": [s.to_dict() for s in self.sources],
            "source_uri": self.source_uri,
            "source_trust": self.source_trust.value,
            "confidence": self.confidence,
            "sensitivity": self.sensitivity.value,
            "approval_state": self.approval_state.value,
            "freshness_due": self.freshness_due,
            "contradiction_status": self.contradiction_status.value,
            "subject": self.subject,
            "supersedes": list(self.supersedes),
            "superseded_by": self.superseded_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryNode":
        return cls(
            id=d["id"],
            namespace=d["namespace"],
            layer=MemoryLayer(d.get("layer", "session")),
            title=d.get("title", ""),
            summary=d.get("summary", ""),
            text=d.get("text", ""),
            chunk_refs=tuple(d.get("chunk_refs", []) or []),
            sources=tuple(
                MemorySource.from_dict(s) for s in d.get("sources", []) or []
            ),
            source_uri=d.get("source_uri"),
            source_trust=SourceTrust(d.get("source_trust", "unverified")),
            confidence=float(d.get("confidence", 0.5)),
            sensitivity=SensitivityClass(d.get("sensitivity", "internal")),
            approval_state=ApprovalState(d.get("approval_state", "proposed")),
            freshness_due=d.get("freshness_due"),
            contradiction_status=ContradictionStatus(
                d.get("contradiction_status", "none")
            ),
            subject=d.get("subject"),
            supersedes=tuple(d.get("supersedes", []) or []),
            superseded_by=d.get("superseded_by"),
            created_at=d.get("created_at", _now_iso()),
            updated_at=d.get("updated_at", _now_iso()),
            tags=tuple(d.get("tags", []) or []),
        )

    def has_provenance(self) -> bool:
        return bool(self.source_uri) or bool(self.sources)


@dataclass
class ContradictionReport:
    id: str
    namespace: str
    subject: str
    node_a_id: str
    node_b_id: str
    reason: str
    status: ContradictionStatus = ContradictionStatus.CONTESTED
    winner_id: Optional[str] = None
    resolution_note: str = ""
    created_at: str = field(default_factory=_now_iso)
    resolved_at: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "namespace": self.namespace,
            "subject": self.subject,
            "node_a_id": self.node_a_id,
            "node_b_id": self.node_b_id,
            "reason": self.reason,
            "status": self.status.value,
            "winner_id": self.winner_id,
            "resolution_note": self.resolution_note,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ContradictionReport":
        return cls(
            id=d["id"],
            namespace=d.get("namespace", ""),
            subject=d.get("subject", ""),
            node_a_id=d["node_a_id"],
            node_b_id=d["node_b_id"],
            reason=d.get("reason", ""),
            status=ContradictionStatus(d.get("status", "contested")),
            winner_id=d.get("winner_id"),
            resolution_note=d.get("resolution_note", ""),
            created_at=d.get("created_at", _now_iso()),
            resolved_at=d.get("resolved_at"),
        )


@dataclass(frozen=True)
class MemorySearchResult:
    node: MemoryNode
    score: float
    matched_terms: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "node": self.node.to_dict(),
            "score": round(self.score, 4),
            "matched_terms": list(self.matched_terms),
        }


@dataclass
class ContextPack:
    """An ordered, token-bounded bundle of memory for a prompt."""

    query: str
    token_budget: int
    sections: list[dict] = field(default_factory=list)
    used_tokens: int = 0
    excluded_contested: int = 0
    excluded_proposed: int = 0

    def add_section(self, node: MemoryNode, tokens: int) -> None:
        self.sections.append({
            "id": node.id,
            "namespace": node.namespace,
            "title": node.title,
            "summary": node.summary or node.text,
            "sources": [s.uri for s in node.sources]
            + ([node.source_uri] if node.source_uri else []),
            "confidence": node.confidence,
            "trust": node.source_trust.value,
            "approval_state": node.approval_state.value,
            "tokens": tokens,
        })
        self.used_tokens += tokens

    def render(self) -> str:
        lines = [
            f"CONTEXT PACK — query: {self.query}",
            f"budget: {self.used_tokens}/{self.token_budget} tokens",
        ]
        if not self.sections:
            lines.append("(no matching memory)")
        for i, sec in enumerate(self.sections, 1):
            lines.append("")
            lines.append(
                f"{i}. [{sec['namespace']}] {sec['title']} "
                f"(conf={sec['confidence']:.2f}, trust={sec['trust']})"
            )
            lines.append(f"   {sec['summary']}")
            srcs = [s for s in sec["sources"] if s]
            if srcs:
                lines.append("   sources: " + ", ".join(srcs))
        if self.excluded_contested:
            lines.append("")
            lines.append(f"(excluded {self.excluded_contested} contested node(s))")
        if self.excluded_proposed:
            lines.append("")
            lines.append(
                f"(excluded {self.excluded_proposed} unapproved node(s) "
                "pending owner review)"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "token_budget": self.token_budget,
            "used_tokens": self.used_tokens,
            "excluded_contested": self.excluded_contested,
            "excluded_proposed": self.excluded_proposed,
            "sections": self.sections,
        }


# ---------------------------------------------------------------------------
# Write policy
# ---------------------------------------------------------------------------


# Patterns that indicate secret-like material we must never store.
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # AWS access key id
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),  # OpenAI-style secret
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),  # GitHub tokens
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),  # Slack tokens
    re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*\S{6,}"),
    re.compile(r"(?i)\bsession(_id|id|-cookie)?\b\s*[:=]\s*\S{8,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._-]{16,}"),
)

# Markers that indicate chain-of-thought / internal reasoning dumps.
_COT_PATTERNS = (
    re.compile(r"(?i)\bchain[ -]of[ -]thought\b"),
    re.compile(r"(?i)\blet me think step by step\b"),
    re.compile(r"(?i)\bmy (internal )?reasoning (is|was|process)\b"),
    re.compile(r"(?i)\bthinking out loud\b"),
)

# Heuristic markers for transient emotional state (downgraded, not stored durably).
_EMOTION_PATTERNS = (
    re.compile(r"(?i)\b(i feel|i'm feeling|i am feeling|right now i feel)\b"),
    re.compile(
        r"(?i)\b(frustrated|anxious|excited|stressed|tired|annoyed|overwhelmed) (today|right now|at the moment)\b"
    ),
)


@dataclass
class MemoryWritePolicy:
    """Validation gate applied before any node is committed."""

    durable_confidence_floor: float = 0.6
    contest_confidence_floor: float = 0.6

    def detect_secret(self, text: str) -> Optional[str]:
        for pat in _SECRET_PATTERNS:
            if pat.search(text or ""):
                return f"secret-like pattern matched ({pat.pattern[:32]}...)"
        return None

    def detect_chain_of_thought(self, text: str) -> Optional[str]:
        for pat in _COT_PATTERNS:
            if pat.search(text or ""):
                return "chain-of-thought content is not stored"
        return None

    def is_transient_emotion(self, text: str, tags: Iterable[str]) -> bool:
        tagset = {t.lower() for t in tags}
        if {"emotion", "mood", "feeling"} & tagset:
            return True
        return any(pat.search(text or "") for pat in _EMOTION_PATTERNS)


@dataclass(frozen=True)
class MemoryWriteResult:
    """Outcome of a write attempt (or dry-run validation)."""

    ok: bool
    node: Optional[MemoryNode] = None
    reasons: tuple[str, ...] = ()
    contradiction: Optional[ContradictionReport] = None
    effective_layer: Optional[MemoryLayer] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "node": self.node.to_dict() if self.node else None,
            "reasons": list(self.reasons),
            "contradiction": self.contradiction.to_dict()
            if self.contradiction
            else None,
            "effective_layer": self.effective_layer.value
            if self.effective_layer
            else None,
        }


# ---------------------------------------------------------------------------
# The production store
# ---------------------------------------------------------------------------


def _default_tree_path() -> Path:
    """Default Memory Tree location, honoring ``HERMES_HOME`` like the rest of
    the stack (``memory.py``, ``raw_event_log.py``).

    Defaults to ``~/.hermes`` when unset so production behavior is unchanged,
    but tests / Termux / the cockpit can relocate the whole store by setting
    ``HERMES_HOME`` (otherwise the Tree leaks across the real home dir and
    isn't test-isolated).
    """

    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "jarvis_prime" / "memory_tree.jsonl"


# Backwards-compatible module constant (evaluated at import time). Callers that
# need the live, ``HERMES_HOME``-aware path should use ``_default_tree_path()``
# (the store does so via ``_resolve_path``).
DEFAULT_MEMORY_TREE_PATH = _default_tree_path()


@dataclass
class MemoryTreeStore:
    """Durable, provenance-first, contradiction-aware Memory Tree."""

    path: Optional[Path] = None
    policy: MemoryWritePolicy = field(default_factory=MemoryWritePolicy)
    nodes: dict[str, MemoryNode] = field(default_factory=dict)
    contradictions: dict[str, ContradictionReport] = field(default_factory=dict)
    load_diagnostics: list[str] = field(default_factory=list)
    # Optional dense-embedding retrieval lane (default off). A positive weight
    # here — or the ``HERMES_MEMORY_TREE_EMBEDDINGS`` env flag — activates a
    # semantic similarity term blended into ``search`` / ``_score``. When 0 and
    # the env flag is unset, retrieval is byte-for-byte the pure term-overlap
    # behavior. See ``memory_tree_embeddings.py``.
    embedding_weight: float = 0.0

    # -- write --------------------------------------------------------------

    def write(
        self,
        text: str,
        *,
        namespace: str,
        title: str,
        layer: MemoryLayer = MemoryLayer.SESSION,
        summary: str = "",
        sources: Iterable[MemorySource] = (),
        source_uri: Optional[str] = None,
        source_trust: SourceTrust = SourceTrust.UNVERIFIED,
        confidence: float = 0.5,
        sensitivity: SensitivityClass = SensitivityClass.INTERNAL,
        approval_state: ApprovalState = ApprovalState.PROPOSED,
        freshness_due: Optional[str] = None,
        subject: Optional[str] = None,
        tags: Iterable[str] = (),
        owner_approved: bool = False,
        dry_run: bool = False,
        persist: bool = True,
    ) -> MemoryWriteResult:
        """Validate, then (unless dry-run) commit a node.

        Returns a :class:`MemoryWriteResult`. Rejections never raise — the
        caller inspects ``ok`` and ``reasons``.
        """

        text = (text or "").strip()
        tags = tuple(tags)
        reasons: list[str] = []

        if not text and not summary:
            return MemoryWriteResult(ok=False, reasons=("empty text",))

        # 1. Hard rejections (apply at every layer).
        secret = self.policy.detect_secret(text) or self.policy.detect_secret(summary)
        if secret:
            return MemoryWriteResult(ok=False, reasons=(secret,))
        cot = self.policy.detect_chain_of_thought(text)
        if cot:
            return MemoryWriteResult(ok=False, reasons=(cot,))
        if sensitivity == SensitivityClass.SECRET:
            return MemoryWriteResult(
                ok=False, reasons=("secret-class content is never stored",)
            )

        effective_layer = layer

        # 2. Transient emotion downgrade.
        if layer == MemoryLayer.DURABLE and self.policy.is_transient_emotion(
            text, tags
        ):
            effective_layer = MemoryLayer.SESSION
            reasons.append("downgraded transient emotional state to session layer")

        # 3. Durable-layer policy.
        if effective_layer == MemoryLayer.DURABLE:
            owner_decision = (
                owner_approved or approval_state == ApprovalState.OWNER_APPROVED
            )
            has_prov = bool(source_uri) or bool(tuple(sources))
            if not has_prov and not owner_decision:
                return MemoryWriteResult(
                    ok=False,
                    reasons=("durable facts require provenance or owner approval",),
                )
            if confidence < self.policy.durable_confidence_floor and not owner_decision:
                return MemoryWriteResult(
                    ok=False,
                    reasons=(
                        f"durable confidence {confidence:.2f} below floor "
                        f"{self.policy.durable_confidence_floor:.2f} (owner approval required)",
                    ),
                )

        node = MemoryNode(
            id=stable_memory_id(namespace, title, text or summary),
            namespace=namespace,
            layer=effective_layer,
            title=title.strip() or "Untitled",
            summary=summary.strip() or _first_sentence(text),
            text=text,
            sources=tuple(sources),
            source_uri=source_uri,
            source_trust=source_trust,
            confidence=max(0.0, min(1.0, confidence)),
            sensitivity=sensitivity,
            approval_state=(
                ApprovalState.OWNER_APPROVED if owner_approved else approval_state
            ),
            freshness_due=freshness_due,
            subject=canonicalize_text(subject) if subject else _subject_key(title),
            tags=tags,
        )

        if dry_run:
            return MemoryWriteResult(
                ok=True,
                node=node,
                reasons=tuple(reasons),
                effective_layer=effective_layer,
            )

        # 4. Contradiction detection (durable layer, same subject, both confident).
        contradiction = None
        if effective_layer == MemoryLayer.DURABLE:
            contradiction = self._detect_contradiction(node)

        # Never silently overwrite: if an id collides with a different text we
        # treat it as an update of the same fact (same id == same canonical
        # text by construction), so identical re-writes are idempotent.
        self.nodes[node.id] = node

        if persist:
            self.save()
            # Compute the node's embedding at ingest when the dense lane is on.
            # No-op (returns None) when embeddings are disabled, so the default
            # write path is unchanged. Never let embedding failures break a write.
            try:
                index = self._embeddings()
                if index is not None:
                    index.vector_for(node)
                    index.flush()
            except Exception:
                pass

        return MemoryWriteResult(
            ok=True,
            node=node,
            reasons=tuple(reasons),
            contradiction=contradiction,
            effective_layer=effective_layer,
        )

    def _detect_contradiction(self, node: MemoryNode) -> Optional[ContradictionReport]:
        floor = self.policy.contest_confidence_floor
        if node.confidence < floor:
            return None
        for other in list(self.nodes.values()):
            if other.id == node.id:
                continue
            if other.layer != MemoryLayer.DURABLE:
                continue
            if other.namespace != node.namespace:
                continue
            if (
                not other.active
                or other.contradiction_status == ContradictionStatus.SUPERSEDED
            ):
                continue
            if other.subject != node.subject:
                continue
            if other.confidence < floor:
                continue
            if canonicalize_text(other.text) == canonicalize_text(node.text):
                continue  # same fact, not a conflict
            # Conflicting high-confidence facts about the same subject.
            report = ContradictionReport(
                id=stable_memory_id(
                    node.namespace, node.subject or "", other.id + node.id
                ),
                namespace=node.namespace,
                subject=node.subject or node.title,
                node_a_id=other.id,
                node_b_id=node.id,
                reason="conflicting high-confidence facts on the same subject",
            )
            other.contradiction_status = ContradictionStatus.CONTESTED
            node.contradiction_status = ContradictionStatus.CONTESTED
            other.updated_at = _now_iso()
            self.contradictions[report.id] = report
            return report
        return None

    def resolve_contradiction(
        self, report_id: str, winner_id: str, note: str = ""
    ) -> ContradictionReport:
        """Record resolution: winner stays, loser is superseded."""

        report = self.contradictions[report_id]
        if winner_id not in (report.node_a_id, report.node_b_id):
            raise ValueError("winner_id must be one of the contested nodes")
        loser_id = (
            report.node_b_id if winner_id == report.node_a_id else report.node_a_id
        )

        winner = self.nodes[winner_id]
        loser = self.nodes[loser_id]

        winner.contradiction_status = ContradictionStatus.RESOLVED
        winner.approval_state = ApprovalState.OWNER_APPROVED
        winner.supersedes = tuple(dict.fromkeys((*winner.supersedes, loser_id)))
        winner.updated_at = _now_iso()

        loser.contradiction_status = ContradictionStatus.SUPERSEDED
        loser.superseded_by = winner_id
        loser.updated_at = _now_iso()

        report.status = ContradictionStatus.RESOLVED
        report.winner_id = winner_id
        report.resolution_note = note
        report.resolved_at = _now_iso()

        self.save()
        return report

    def open_contradictions(self) -> list[ContradictionReport]:
        return [
            r
            for r in self.contradictions.values()
            if r.status == ContradictionStatus.CONTESTED
        ]

    # -- proposed inbox / owner decisions -----------------------------------

    def proposed(
        self, *, namespaces: Optional[Iterable[str]] = None
    ) -> list[MemoryNode]:
        """Active nodes still awaiting an owner decision (the inbox).

        These are candidates captured from turns — recallable but clearly
        *proposed*, never silently durable. Sorted newest-first.
        """

        ns_filter = set(namespaces) if namespaces else None
        items = [
            node
            for node in self.nodes.values()
            if node.active
            and node.approval_state == ApprovalState.PROPOSED
            and (ns_filter is None or node.namespace in ns_filter)
        ]
        items.sort(key=lambda n: n.created_at, reverse=True)
        return items

    def set_approval(self, node_id: str, state: ApprovalState) -> MemoryNode:
        """Record an owner decision on a node's approval state and persist."""

        node = self.nodes[node_id]
        node.approval_state = state
        node.updated_at = _now_iso()
        self.save()
        return node

    def promote_to_durable(self, node_id: str) -> MemoryWriteResult:
        """Owner-approve a proposed node and lift it to the durable layer.

        Promotion re-runs the durable write policy and contradiction
        detection so an approval can **never silently overwrite** an existing
        durable fact — a conflict opens a :class:`ContradictionReport` and the
        result carries it (both nodes become contested) instead of clobbering.
        """

        node = self.nodes[node_id]
        node.approval_state = ApprovalState.OWNER_APPROVED
        node.layer = MemoryLayer.DURABLE
        node.updated_at = _now_iso()
        # Owner approval satisfies the provenance/confidence floor by policy.
        contradiction = self._detect_contradiction(node)
        self.save()
        return MemoryWriteResult(
            ok=True,
            node=node,
            contradiction=contradiction,
            effective_layer=MemoryLayer.DURABLE,
        )

    def supersede(
        self, loser_id: str, winner_id: str, note: str = ""
    ) -> MemoryNode:
        """Manually supersede ``loser_id`` with ``winner_id``.

        Mirrors the contradiction-resolution bookkeeping (loser
        ``SUPERSEDED`` + ``superseded_by``, winner records ``supersedes``)
        without requiring a pre-existing :class:`ContradictionReport`. Never
        deletes the loser — supersession is reversible-by-audit, not a wipe.
        """

        if loser_id == winner_id:
            raise ValueError("a node cannot supersede itself")
        winner = self.nodes[winner_id]
        loser = self.nodes[loser_id]
        winner.supersedes = tuple(dict.fromkeys((*winner.supersedes, loser_id)))
        winner.updated_at = _now_iso()
        loser.contradiction_status = ContradictionStatus.SUPERSEDED
        loser.superseded_by = winner_id
        loser.updated_at = _now_iso()
        if note:
            loser.summary = (loser.summary + f" (superseded: {note})").strip()
        self.save()
        return loser

    def due_for_review(self, within_days: int = 0) -> list[MemoryNode]:
        """Active nodes whose freshness review is overdue or due within N days.

        ``within_days=0`` returns only already-overdue nodes. Sorted by the
        soonest ``freshness_due`` first so the owner triages the stalest data.
        """

        horizon = datetime.now(timezone.utc) + timedelta(days=max(0, within_days))
        due: list[MemoryNode] = []
        for node in self.nodes.values():
            if not node.active or not node.freshness_due:
                continue
            try:
                when = datetime.fromisoformat(node.freshness_due)
            except ValueError:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when <= horizon:
                due.append(node)
        due.sort(key=lambda n: n.freshness_due or "")
        return due

    # -- read / search ------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        namespaces: Optional[Iterable[str]] = None,
        layers: Optional[Iterable[MemoryLayer]] = None,
        include_contested: bool = False,
        include_pending: bool = True,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        q_terms = _terms(query)
        ns_filter = set(namespaces) if namespaces else None
        layer_filter = set(layers) if layers else None
        results: list[MemorySearchResult] = []

        # Dense-embedding lane (opt-in, default off). When active, the query is
        # embedded once and semantic-only candidates (no lexical overlap) are
        # kept so similarity can surface them; the score blends the cosine term.
        emb_index = self._embeddings()
        emb_query_vec = None
        emb_active = False
        if emb_index is not None:
            emb_query_vec = emb_index.embed_query(query)
            emb_active = emb_query_vec is not None

        for node in self.nodes.values():
            if not node.active:
                continue
            if node.contested and not include_contested:
                continue
            # Live recall must never surface candidates still pending the
            # owner's review gate (see ``MemoryNode.awaiting_review``). Audit
            # and CLI callers leave ``include_pending=True`` so they can still
            # inspect unreviewed captures.
            if not include_pending and node.awaiting_review:
                continue
            if ns_filter and node.namespace not in ns_filter:
                continue
            if layer_filter and node.layer not in layer_filter:
                continue

            hay = _terms(
                " ".join((node.title, node.summary, node.text, " ".join(node.tags)))
            )
            matched = q_terms & hay
            overlap = len(matched)
            # Off path is byte-identical: drop zero-overlap candidates. When the
            # dense lane is active, keep them so semantic matches can rank.
            if overlap == 0 and q_terms and not emb_active:
                continue

            emb_sim = None
            if emb_active:
                emb_sim = emb_index.similarity(emb_query_vec, node)

            score = self._score(node, overlap, len(q_terms), emb_sim=emb_sim)
            results.append(
                MemorySearchResult(
                    node=node, score=score, matched_terms=tuple(sorted(matched))
                )
            )

        # Persist any node vectors computed lazily during this search, once.
        if emb_active:
            try:
                emb_index.flush()
            except Exception:
                pass

        results.sort(key=lambda r: (r.score, r.node.updated_at), reverse=True)
        return results[:limit]

    def _score(
        self,
        node: MemoryNode,
        overlap: int,
        q_size: int,
        emb_sim: Optional[float] = None,
    ) -> float:
        term_score = (overlap / q_size) if q_size else 0.5
        layer_bonus = {"durable": 0.3, "session": 0.15, "working": 0.05}[
            node.layer.value
        ]
        approval_bonus = (
            0.15 if node.approval_state == ApprovalState.OWNER_APPROVED else 0.0
        )
        freshness_penalty = 0.2 if self._is_stale(node) else 0.0
        base = (
            term_score * 1.0
            + node.source_trust.weight * 0.5
            + node.confidence * 0.4
            + layer_bonus
            + approval_bonus
            - freshness_penalty
        )
        # Dense-embedding term is purely additive and only contributes when the
        # lane is active (weight > 0 and a similarity was computed). When off,
        # ``emb_sim`` is None and the score is unchanged.
        emb_weight = getattr(self, "_emb_weight", 0.0)
        if emb_sim is not None and emb_weight > 0:
            base += emb_weight * emb_sim
        return base

    @staticmethod
    def _is_stale(node: MemoryNode) -> bool:
        if not node.freshness_due:
            return False
        try:
            due = datetime.fromisoformat(node.freshness_due)
        except ValueError:
            return False
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        return due < datetime.now(timezone.utc)

    def context_pack(
        self,
        query: str,
        token_budget: int,
        *,
        namespaces: Optional[Iterable[str]] = None,
        include_contested: bool = False,
    ) -> ContextPack:
        pack = ContextPack(query=query, token_budget=token_budget)
        hits = self.search(
            query,
            namespaces=namespaces,
            include_contested=include_contested,
            include_pending=False,
            limit=50,
        )
        # Account for contested exclusions for transparency.
        if not include_contested:
            pack.excluded_contested = sum(
                1 for n in self.nodes.values() if n.active and n.contested
            )
        # Candidates still awaiting the owner's review gate are excluded from
        # live recall; record the count so the gate is visible, not silent.
        pack.excluded_proposed = sum(
            1 for n in self.nodes.values() if n.active and n.awaiting_review
        )
        for hit in hits:
            node = hit.node
            body = node.summary or node.text
            src_text = " ".join(s.excerpt for s in node.sources if s.excerpt)
            cost = (
                estimate_tokens(node.title)
                + estimate_tokens(body)
                + estimate_tokens(src_text)
            )
            if pack.used_tokens + cost > token_budget:
                continue
            pack.add_section(node, cost)
        return pack

    def get(self, node_id: str) -> Optional[MemoryNode]:
        return self.nodes.get(node_id)

    # -- embeddings (optional dense retrieval lane) -------------------------

    def _embedding_sidecar_path(self) -> Path:
        p = self._resolve_path()
        return p.parent / (p.stem + ".emb.jsonl")

    def _embeddings(self) -> Optional[Any]:
        """Return an active embedding index, or ``None`` when the lane is off.

        Lazy + cached per store instance. Enablement is either the
        ``HERMES_MEMORY_TREE_EMBEDDINGS`` env flag or an explicit positive
        ``embedding_weight`` (e.g. wired from ``JarvisConfig``). Any failure
        (missing deps, backend unavailable) disables the lane silently so
        retrieval always falls back to the byte-identical lexical path.
        """

        if getattr(self, "_emb_ready", False):
            return getattr(self, "_emb_index", None)
        self._emb_ready = True
        self._emb_index = None
        self._emb_weight = 0.0
        try:
            from hermes_cli.jarvis_prime.memory_tree_embeddings import (
                build_index,
                resolve_embedding_config,
            )

            cfg = resolve_embedding_config()
            weight = (
                self.embedding_weight
                if self.embedding_weight > 0
                else float(cfg.get("weight", 0.0))
            )
            enabled = bool(cfg.get("enabled")) or self.embedding_weight > 0
            if not enabled or weight <= 0:
                return None
            # The store owns enablement; force the backend factory on.
            cfg.setdefault("embeddings", {})["enabled"] = True
            index = build_index(cfg, self._embedding_sidecar_path())
            if index is None:
                return None
            self._emb_index = index
            self._emb_weight = weight
        except Exception:
            self._emb_index = None
            self._emb_weight = 0.0
        return self._emb_index

    # -- persistence --------------------------------------------------------

    def _resolve_path(self) -> Path:
        return Path(self.path) if self.path else _default_tree_path()

    def save(self) -> Path:
        target = self._resolve_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        for node in self.nodes.values():
            rec = node.to_dict()
            rec["type"] = "node"
            lines.append(json.dumps(rec, sort_keys=True))
        for report in self.contradictions.values():
            rec = report.to_dict()
            rec["type"] = "contradiction"
            lines.append(json.dumps(rec, sort_keys=True))
        payload = "\n".join(lines) + ("\n" if lines else "")

        # Atomic write via temp file in the same directory.
        fd, tmp = tempfile.mkstemp(
            dir=str(target.parent), prefix=".memtree-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        # Best-effort owner-only permissions.
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
        return target

    @classmethod
    def load(
        cls, path: Optional[Path] = None, *, policy: Optional[MemoryWritePolicy] = None
    ) -> "MemoryTreeStore":
        store = cls(path=path, policy=policy or MemoryWritePolicy())
        target = store._resolve_path()
        if not target.exists():
            return store
        with open(target, "r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, 1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except json.JSONDecodeError as exc:
                    store.load_diagnostics.append(
                        f"line {lineno}: malformed JSON ({exc})"
                    )
                    continue
                kind = rec.get("type")
                try:
                    if kind == "contradiction":
                        report = ContradictionReport.from_dict(rec)
                        store.contradictions[report.id] = report
                    else:
                        node = MemoryNode.from_dict(rec)
                        store.nodes[node.id] = node
                except (KeyError, ValueError) as exc:
                    store.load_diagnostics.append(f"line {lineno}: bad record ({exc})")
        return store

    # -- exports ------------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "contradictions": [r.to_dict() for r in self.contradictions.values()],
        }

    @classmethod
    def from_dict(cls, d: dict, *, path: Optional[Path] = None) -> "MemoryTreeStore":
        store = cls(path=path)
        for rec in d.get("nodes", []):
            node = MemoryNode.from_dict(rec)
            store.nodes[node.id] = node
        for rec in d.get("contradictions", []):
            report = ContradictionReport.from_dict(rec)
            store.contradictions[report.id] = report
        return store

    def export_markdown(self, namespace: Optional[str] = None) -> str:
        grouped: dict[str, list[MemoryNode]] = {}
        for node in self.nodes.values():
            if namespace and node.namespace != namespace:
                continue
            grouped.setdefault(node.namespace, []).append(node)
        lines = ["# JARVIS Memory Tree", ""]
        for ns in sorted(grouped):
            lines.append(f"## {ns}")
            lines.append("")
            for node in sorted(grouped[ns], key=lambda n: n.title.lower()):
                status = []
                if node.contested:
                    status.append("CONTESTED")
                if node.superseded_by:
                    status.append("SUPERSEDED")
                flag = f" _({', '.join(status)})_" if status else ""
                lines.append(f"- **{node.title}**{flag} — {node.summary or node.text}")
                srcs = [s.uri for s in node.sources] + (
                    [node.source_uri] if node.source_uri else []
                )
                if srcs:
                    lines.append(f"  - sources: {', '.join(s for s in srcs if s)}")
                lines.append(
                    f"  - layer={node.layer.value} conf={node.confidence:.2f} "
                    f"trust={node.source_trust.value} approval={node.approval_state.value}"
                )
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def export_audit_cards(self, namespace: Optional[str] = None) -> list[dict]:
        cards = []
        for node in self.nodes.values():
            if namespace and node.namespace != namespace:
                continue
            cards.append({
                "id": node.id,
                "namespace": node.namespace,
                "title": node.title,
                "claim": node.summary or node.text,
                "sources": [s.uri for s in node.sources]
                + ([node.source_uri] if node.source_uri else []),
                "confidence": node.confidence,
                "trust": node.source_trust.value,
                "approval_state": node.approval_state.value,
                "contradiction_status": node.contradiction_status.value,
                "freshness_due": node.freshness_due,
                "created_at": node.created_at,
            })
        return cards

    def outline(self) -> str:
        grouped: dict[str, list[MemoryNode]] = {}
        for node in self.nodes.values():
            grouped.setdefault(node.namespace, []).append(node)
        lines: list[str] = []
        for ns in sorted(grouped):
            lines.append(f"- {ns}")
            for node in sorted(grouped[ns], key=lambda n: n.title.lower()):
                marker = " [contested]" if node.contested else ""
                lines.append(f"  - {node.title} ({node.layer.value}){marker}")
        return "\n".join(lines)


def _first_sentence(text: str) -> str:
    text = canonicalize_text(text)
    if not text:
        return ""
    m = re.search(r"(.+?[.!?])(\s|$)", text)
    return (m.group(1) if m else text)[:200]


def _subject_key(title: str) -> str:
    return canonicalize_text(title).lower()
