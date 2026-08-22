"""Memory Tree — a provenance-first, contradiction-aware memory store.

Clean-room and stdlib-only. :class:`MemoryTreeStore` is a durable JSONL store
behind the ``hermes memory-tree`` CLI; it complements (never replaces) the
built-in session memory.

Design rules enforced here:

* Memory **cites sources**; it never becomes the source of truth.
* New facts **never silently overwrite** old facts — conflicting durable
  facts create a :class:`ContradictionReport` and both records become
  contested until an operator resolves them.
* Secrets, raw credentials, private keys, session cookies, and
  chain-of-thought are **rejected** before they can be written.
* Durable writes require provenance and a confidence floor unless the
  operator explicitly approved the write.
* No network calls. Persistence is local JSONL with atomic writes and
  owner-only file permissions where the platform supports it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional


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
# Enumerations
# ---------------------------------------------------------------------------


class MemoryLayer(str, Enum):
    WORKING = "working"
    SESSION = "session"
    DURABLE = "durable"


class SourceTrust(str, Enum):
    OPERATOR = "operator"  # the operator stated it directly
    PRIMARY = "primary"  # primary source / official spec
    OFFICIAL_DOC = "official_doc"
    REPUTABLE = "reputable"
    COMMUNITY = "community"
    UNVERIFIED = "unverified"

    @property
    def weight(self) -> float:
        return {
            "operator": 1.0,
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
    OPERATOR_APPROVED = "operator_approved"
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


@dataclass
class MemoryNode:
    """A durable/session/working memory node with full provenance."""

    id: str
    namespace: str
    layer: MemoryLayer
    title: str
    summary: str = ""
    text: str = ""
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

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "namespace": self.namespace,
            "layer": self.layer.value,
            "title": self.title,
            "summary": self.summary,
            "text": self.text,
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
# The store
# ---------------------------------------------------------------------------


def _default_tree_path() -> Path:
    """Default Memory Tree location, honoring ``HERMES_HOME`` like the rest of
    the stack (``memory.py``, ``raw_event_log.py``).

    Defaults to ``~/.hermes`` when unset so production behavior is unchanged,
    but tests / Termux / an embedding host can relocate the whole store by setting
    ``HERMES_HOME`` (otherwise the Tree leaks across the real home dir and
    isn't test-isolated).
    """

    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "prime" / "memory_tree.jsonl"


@dataclass
class MemoryTreeStore:
    """A durable, provenance-first, contradiction-aware memory tree."""

    path: Optional[Path] = None
    policy: MemoryWritePolicy = field(default_factory=MemoryWritePolicy)
    nodes: dict[str, MemoryNode] = field(default_factory=dict)
    contradictions: dict[str, ContradictionReport] = field(default_factory=dict)
    load_diagnostics: list[str] = field(default_factory=list)

    # -- write --------------------------------------------------------------

    def write(
        self,
        text: str,
        *,
        namespace: str,
        title: str,
        layer: MemoryLayer = MemoryLayer.SESSION,
        summary: str = "",
        source_uri: Optional[str] = None,
        source_trust: SourceTrust = SourceTrust.UNVERIFIED,
        confidence: float = 0.5,
        sensitivity: SensitivityClass = SensitivityClass.INTERNAL,
        approval_state: ApprovalState = ApprovalState.PROPOSED,
        freshness_due: Optional[str] = None,
        subject: Optional[str] = None,
        tags: Iterable[str] = (),
        operator_approved: bool = False,
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
            approved = (
                operator_approved
                or approval_state == ApprovalState.OPERATOR_APPROVED
            )
            if not source_uri and not approved:
                return MemoryWriteResult(
                    ok=False,
                    reasons=("durable facts require provenance or operator approval",),
                )
            if confidence < self.policy.durable_confidence_floor and not approved:
                return MemoryWriteResult(
                    ok=False,
                    reasons=(
                        f"durable confidence {confidence:.2f} below floor "
                        f"{self.policy.durable_confidence_floor:.2f} "
                        f"(operator approval required)",
                    ),
                )

        node = MemoryNode(
            id=stable_memory_id(namespace, title, text or summary),
            namespace=namespace,
            layer=effective_layer,
            title=title.strip() or "Untitled",
            summary=summary.strip() or _first_sentence(text),
            text=text,
            source_uri=source_uri,
            source_trust=source_trust,
            confidence=max(0.0, min(1.0, confidence)),
            sensitivity=sensitivity,
            approval_state=(
                ApprovalState.OPERATOR_APPROVED
                if operator_approved
                else approval_state
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

        # 4. Re-writes of a fact we already hold carry their lineage forward.
        #
        # The id is derived from (namespace, title, canonical text), so an
        # existing id means the *same* fact is being written again. The record
        # is refreshed, but its contradiction state, supersession and any
        # operator approval must survive: without this a second identical
        # `memory-tree write` would resurrect a node an operator had already
        # superseded and re-contest the winner.
        existing = self.nodes.get(node.id)
        if existing is not None:
            node.created_at = existing.created_at
            node.contradiction_status = existing.contradiction_status
            node.supersedes = existing.supersedes
            node.superseded_by = existing.superseded_by
            if existing.approval_state == ApprovalState.OPERATOR_APPROVED:
                node.approval_state = ApprovalState.OPERATOR_APPROVED

        # 5. Contradiction detection (durable layer, same subject, both
        #    confident). Only for a fact that is newly durable — a repeat write
        #    of a fact already held durably was contested (or not) when it was
        #    first written, and re-running detection would only duplicate the
        #    existing report.
        contradiction = None
        if effective_layer == MemoryLayer.DURABLE and (
            existing is None or existing.layer != MemoryLayer.DURABLE
        ):
            contradiction = self._detect_contradiction(node)

        self.nodes[node.id] = node

        if persist:
            self.save()

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
                    # Order-independent pair key: whichever of the two facts is
                    # written second, the pair gets one report, never two.
                    node.namespace,
                    node.subject or "",
                    "".join(sorted((other.id, node.id))),
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
        winner.approval_state = ApprovalState.OPERATOR_APPROVED
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

    # -- read / search ------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        namespaces: Optional[Iterable[str]] = None,
        layers: Optional[Iterable[MemoryLayer]] = None,
        include_contested: bool = False,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        q_terms = _terms(query)
        ns_filter = set(namespaces) if namespaces else None
        layer_filter = set(layers) if layers else None
        results: list[MemorySearchResult] = []

        for node in self.nodes.values():
            if not node.active:
                continue
            if node.contested and not include_contested:
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
            if overlap == 0 and q_terms:
                continue

            score = self._score(node, overlap, len(q_terms))
            results.append(
                MemorySearchResult(
                    node=node, score=score, matched_terms=tuple(sorted(matched))
                )
            )

        results.sort(key=lambda r: (r.score, r.node.updated_at), reverse=True)
        return results[:limit]

    def _score(self, node: MemoryNode, overlap: int, q_size: int) -> float:
        term_score = (overlap / q_size) if q_size else 0.5
        layer_bonus = {"durable": 0.3, "session": 0.15, "working": 0.05}[
            node.layer.value
        ]
        approval_bonus = (
            0.15 if node.approval_state == ApprovalState.OPERATOR_APPROVED else 0.0
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

    def get(self, node_id: str) -> Optional[MemoryNode]:
        return self.nodes.get(node_id)

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

    def export_markdown(self, namespace: Optional[str] = None) -> str:
        grouped: dict[str, list[MemoryNode]] = {}
        for node in self.nodes.values():
            if namespace and node.namespace != namespace:
                continue
            grouped.setdefault(node.namespace, []).append(node)
        lines = ["# Memory Tree", ""]
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
                if node.source_uri:
                    lines.append(f"  - source: {node.source_uri}")
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
                "sources": [node.source_uri] if node.source_uri else [],
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
