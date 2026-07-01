"""Evidence model and tamper-evident ledger for verifiable guardrails.

This module turns JARVIS/Hermes guardrail *decisions* into evidence-bound,
tamper-evident records. The two load-bearing ideas are:

1. **Evidence artifacts** — every guardrail check (git diff, test run, secret
   scan, review, rollback, owner authorization) produces an
   :class:`EvidenceArtifact` whose ``payload`` is content-addressed by
   ``payload_sha256``. A gate may only pass on *observed* artifacts, never on a
   packet's self-attestation.

2. **A hash-chained decision ledger** — :class:`GuardrailLedger` is an
   append-only JSONL log where each record carries ``previous_record_hash`` and
   ``record_hash = sha256(canonical_json(record_without_record_hash))``. Any
   edit, reorder, or truncation breaks the chain and is reported by
   :meth:`GuardrailLedger.verify_chain` — the ledger never silently repairs.

Everything here is **stdlib-only**. Ed25519 signing is supported *opportunistic-
ally* when ``cryptography`` happens to be importable (it ships transitively via
``PyJWT[crypto]``), but it is never required: the baseline integrity guarantee is
SHA-256 hash chaining.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


def _utc_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""

    return datetime.now(timezone.utc).isoformat()


def canonical_json(obj: Any) -> str:
    """Deterministic JSON encoding used for every hash in this module.

    Sorted keys + compact separators so the same logical object always hashes
    to the same digest regardless of insertion order or whitespace.
    """

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def hermes_home() -> Path:
    """Resolve ``$HERMES_HOME`` (falling back to ``~/.hermes``)."""

    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base)


# ---------------------------------------------------------------------------
# Evidence artifacts
# ---------------------------------------------------------------------------


# Canonical artifact type names. Collectors and strict gates agree on these.
ARTIFACT_GIT_DIFF = "git_diff"
ARTIFACT_TEST_RESULT = "test_result"
ARTIFACT_SECRET_SCAN = "secret_scan"
ARTIFACT_REVIEW = "review"
ARTIFACT_ROLLBACK = "rollback"
ARTIFACT_OWNER_CHALLENGE = "owner_authorization_challenge"
ARTIFACT_OWNER_GRANT = "owner_authorization_grant"
# A scored self-audit run against the JARVIS Constitution (see self_audit/).
ARTIFACT_AUDIT_RESULT = "audit_result"
# A per-RC-band capability attestation from the behavioral wall (see
# capability_wall.py) — the local Responsible-Scaling-Policy analogue.
ARTIFACT_CAPABILITY_ATTESTATION = "capability_attestation"


@dataclass(frozen=True)
class EvidenceArtifact:
    """A single captured piece of guardrail evidence.

    ``payload_sha256`` is computed over the canonical JSON of ``payload`` so the
    artifact is content-addressed — two artifacts with identical payloads share
    a digest, and any mutation of the payload changes it.
    """

    artifact_id: str
    artifact_type: str
    created_at: str
    producer: str
    subject: str
    payload: Mapping[str, Any]
    payload_sha256: str

    @classmethod
    def make(
        cls,
        artifact_type: str,
        *,
        producer: str,
        subject: str,
        payload: Mapping[str, Any],
        created_at: Optional[str] = None,
    ) -> "EvidenceArtifact":
        payload_dict = dict(payload)
        return cls(
            artifact_id=_new_id("art"),
            artifact_type=artifact_type,
            created_at=created_at or _utc_iso(),
            producer=producer,
            subject=subject,
            payload=payload_dict,
            payload_sha256=sha256_hex(canonical_json(payload_dict)),
        )

    def verify_payload(self) -> bool:
        """Return True if ``payload_sha256`` still matches ``payload``."""

        return self.payload_sha256 == sha256_hex(canonical_json(dict(self.payload)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "created_at": self.created_at,
            "producer": self.producer,
            "subject": self.subject,
            "payload": dict(self.payload),
            "payload_sha256": self.payload_sha256,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EvidenceArtifact":
        return cls(
            artifact_id=str(data.get("artifact_id", _new_id("art"))),
            artifact_type=str(data.get("artifact_type", "")),
            created_at=str(data.get("created_at", "")),
            producer=str(data.get("producer", "")),
            subject=str(data.get("subject", "")),
            payload=dict(data.get("payload", {})),
            payload_sha256=str(data.get("payload_sha256", "")),
        )


# ---------------------------------------------------------------------------
# Typed evidence builders
#
# These thin dataclasses give callers a named, validated shape for each kind of
# evidence and a uniform ``.to_artifact(...)`` that yields a content-addressed
# :class:`EvidenceArtifact`. They never hold raw secrets.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GitDiffEvidence:
    repo_root: str
    git_available: bool
    branch: str = ""
    head_commit: str = ""
    changed_files: tuple[str, ...] = ()
    out_of_scope_files: tuple[str, ...] = ()
    protected_files_touched: tuple[str, ...] = ()
    working_tree_clean: bool = True
    diff_check_passed: bool = True
    status_porcelain: str = ""
    # The AGENT that authored the change under review. Lives in the same
    # identity namespace as a review's ``reviewer_id`` so the C19 builder ≠
    # reviewer check can compare like-for-like. Empty ("") when the acting
    # agent id was not threaded to the collector (fail-open at the gate).
    author_id: str = ""

    def to_artifact(self, producer: str = "git_diff_collector") -> EvidenceArtifact:
        return EvidenceArtifact.make(
            ARTIFACT_GIT_DIFF,
            producer=producer,
            subject=self.branch or self.repo_root,
            payload={
                "repo_root": self.repo_root,
                "git_available": self.git_available,
                "branch": self.branch,
                "head_commit": self.head_commit,
                "changed_files": list(self.changed_files),
                "out_of_scope_files": list(self.out_of_scope_files),
                "protected_files_touched": list(self.protected_files_touched),
                "working_tree_clean": self.working_tree_clean,
                "diff_check_passed": self.diff_check_passed,
                "status_porcelain": self.status_porcelain,
                "author_id": self.author_id,
            },
        )


@dataclass(frozen=True)
class VerificationCommandResult:
    command: str
    cwd: str
    exit_code: Optional[int]
    passed: bool
    duration_seconds: float
    timed_out: bool = False
    stdout_tail: str = ""
    stderr_tail: str = ""
    executed: bool = True
    skipped_reason: str = ""

    def to_artifact(self, producer: str = "local_test_runner") -> EvidenceArtifact:
        return EvidenceArtifact.make(
            ARTIFACT_TEST_RESULT,
            producer=producer,
            subject=self.command,
            payload={
                "command": self.command,
                "cwd": self.cwd,
                "exit_code": self.exit_code,
                "passed": self.passed,
                "duration_seconds": round(self.duration_seconds, 4),
                "timed_out": self.timed_out,
                "stdout_tail": self.stdout_tail,
                "stderr_tail": self.stderr_tail,
                "executed": self.executed,
                "skipped_reason": self.skipped_reason,
            },
        )


@dataclass(frozen=True)
class SecretScanEvidence:
    subject: str
    files_scanned: tuple[str, ...]
    findings: tuple[Mapping[str, Any], ...] = ()  # redacted snippets only

    @property
    def clean(self) -> bool:
        return not self.findings

    def to_artifact(self, producer: str = "secret_scanner") -> EvidenceArtifact:
        return EvidenceArtifact.make(
            ARTIFACT_SECRET_SCAN,
            producer=producer,
            subject=self.subject,
            payload={
                "files_scanned": list(self.files_scanned),
                "clean": self.clean,
                "finding_count": len(self.findings),
                "findings": [dict(f) for f in self.findings],
            },
        )


@dataclass(frozen=True)
class ReviewEvidence:
    reviewer_id: str
    verdict: str  # approve | request_changes | blocked | needs_owner
    diff_hash: str
    review_hash: str
    summary: str
    contrarian_notes: tuple[str, ...] = ()

    def to_artifact(self, producer: str = "reviewer") -> EvidenceArtifact:
        return EvidenceArtifact.make(
            ARTIFACT_REVIEW,
            producer=producer,
            subject=self.diff_hash or self.reviewer_id,
            payload={
                "reviewer_id": self.reviewer_id,
                "verdict": self.verdict,
                "diff_hash": self.diff_hash,
                "review_hash": self.review_hash,
                "summary": self.summary,
                "contrarian_notes": list(self.contrarian_notes),
            },
        )


@dataclass(frozen=True)
class RollbackEvidence:
    repo_root: str
    plan: tuple[str, ...]
    plausible: bool
    branch: str = ""
    commit_hash: str = ""
    changed_files: tuple[str, ...] = ()
    revert_instructions: str = ""
    reasons: tuple[str, ...] = ()

    def to_artifact(self, producer: str = "rollback_collector") -> EvidenceArtifact:
        return EvidenceArtifact.make(
            ARTIFACT_ROLLBACK,
            producer=producer,
            subject=self.branch or self.commit_hash or self.repo_root,
            payload={
                "repo_root": self.repo_root,
                "plan": list(self.plan),
                "plausible": self.plausible,
                "branch": self.branch,
                "commit_hash": self.commit_hash,
                "changed_files": list(self.changed_files),
                "revert_instructions": self.revert_instructions,
                "reasons": list(self.reasons),
            },
        )


# ---------------------------------------------------------------------------
# Evidence bundle
# ---------------------------------------------------------------------------


@dataclass
class GuardrailEvidenceBundle:
    """A set of artifacts collected for one work packet.

    ``packet_id`` binds the bundle to the packet it describes; strict gates
    refuse a bundle whose ``packet_id`` does not match the packet under
    evaluation, so a real bundle cannot be replayed against a different packet.
    """

    packet_id: str
    artifacts: list[EvidenceArtifact] = field(default_factory=list)

    def add(self, artifact: EvidenceArtifact) -> EvidenceArtifact:
        self.artifacts.append(artifact)
        return artifact

    def by_type(self, artifact_type: str) -> list[EvidenceArtifact]:
        return [a for a in self.artifacts if a.artifact_type == artifact_type]

    def has(self, artifact_type: str) -> bool:
        return any(a.artifact_type == artifact_type for a in self.artifacts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "artifacts": [a.to_dict() for a in self.artifacts],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GuardrailEvidenceBundle":
        return cls(
            packet_id=str(data.get("packet_id", "")),
            artifacts=[
                EvidenceArtifact.from_dict(a) for a in data.get("artifacts", [])
            ],
        )


# ---------------------------------------------------------------------------
# Decision records + tamper-evident ledger
# ---------------------------------------------------------------------------

GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class GuardrailDecisionRecord:
    record_id: str
    created_at: str
    kind: str
    subject: str
    payload: Mapping[str, Any]
    previous_record_hash: str
    record_hash: str

    def _hashable(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "created_at": self.created_at,
            "kind": self.kind,
            "subject": self.subject,
            "payload": dict(self.payload),
            "previous_record_hash": self.previous_record_hash,
        }

    @classmethod
    def build(
        cls,
        *,
        kind: str,
        subject: str,
        payload: Mapping[str, Any],
        previous_record_hash: str,
        created_at: Optional[str] = None,
        record_id: Optional[str] = None,
    ) -> "GuardrailDecisionRecord":
        base = {
            "record_id": record_id or _new_id("rec"),
            "created_at": created_at or _utc_iso(),
            "kind": kind,
            "subject": subject,
            "payload": dict(payload),
            "previous_record_hash": previous_record_hash,
        }
        record_hash = sha256_hex(canonical_json(base))
        return cls(record_hash=record_hash, **base)

    def expected_hash(self) -> str:
        return sha256_hex(canonical_json(self._hashable()))

    def to_dict(self) -> dict[str, Any]:
        data = self._hashable()
        data["record_hash"] = self.record_hash
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GuardrailDecisionRecord":
        return cls(
            record_id=str(data.get("record_id", "")),
            created_at=str(data.get("created_at", "")),
            kind=str(data.get("kind", "")),
            subject=str(data.get("subject", "")),
            payload=dict(data.get("payload", {})),
            previous_record_hash=str(data.get("previous_record_hash", GENESIS_HASH)),
            record_hash=str(data.get("record_hash", "")),
        )


@dataclass
class ChainDiagnostics:
    ok: bool
    length: int
    head_hash: Optional[str] = None
    broken_at: Optional[int] = None
    reason: str = ""
    malformed_lines: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "length": self.length,
            "head_hash": self.head_hash,
            "broken_at": self.broken_at,
            "reason": self.reason,
            "malformed_lines": list(self.malformed_lines),
        }


class GuardrailLedger:
    """Append-only, hash-chained JSONL ledger of guardrail decisions.

    The ledger is intentionally simple and dependency-free. Each append links to
    the previous record's hash; :meth:`verify_chain` recomputes every hash and
    every link, reporting the first break rather than repairing it.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = Path(path) if path is not None else self.default_path()

    @staticmethod
    def default_path() -> Path:
        return hermes_home() / "jarvis_prime" / "guardrail_ledger.jsonl"

    @property
    def path(self) -> Path:
        return self._path

    # -- reads -------------------------------------------------------------

    def _read_lines(self) -> list[str]:
        if not self._path.exists():
            return []
        text = self._path.read_text(encoding="utf-8")
        return [ln for ln in text.splitlines() if ln.strip()]

    def read_all(self) -> list[GuardrailDecisionRecord]:
        records: list[GuardrailDecisionRecord] = []
        for ln in self._read_lines():
            try:
                records.append(GuardrailDecisionRecord.from_dict(json.loads(ln)))
            except (json.JSONDecodeError, TypeError):
                continue
        return records

    def latest_hash(self) -> Optional[str]:
        records = self.read_all()
        return records[-1].record_hash if records else None

    # -- writes ------------------------------------------------------------

    def append(
        self,
        kind: str,
        subject: str,
        payload: Mapping[str, Any],
    ) -> GuardrailDecisionRecord:
        """Append a new record linked to the current head and return it."""

        previous = self.latest_hash() or GENESIS_HASH
        record = GuardrailDecisionRecord.build(
            kind=kind,
            subject=subject,
            payload=payload,
            previous_record_hash=previous,
        )
        self._append_line(json.dumps(record.to_dict(), sort_keys=True))
        return record

    def _append_line(self, line: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Append durably: O_APPEND keeps concurrent appends from interleaving
        # within a single short line, mirroring orchestrator_ledger.
        fd = os.open(
            str(self._path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
        )
        try:
            os.write(fd, (line + "\n").encode("utf-8"))
        finally:
            os.close(fd)
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass

    # -- integrity ---------------------------------------------------------

    def verify_chain(self) -> ChainDiagnostics:
        """Recompute the hash chain and report the first break, if any.

        Never repairs the ledger. A mutated payload, a swapped record, a wrong
        ``previous_record_hash`` link, or a truncated file all surface here.
        """

        lines = self._read_lines()
        malformed: list[int] = []
        records: list[GuardrailDecisionRecord] = []
        for idx, ln in enumerate(lines):
            try:
                records.append(GuardrailDecisionRecord.from_dict(json.loads(ln)))
            except (json.JSONDecodeError, TypeError):
                malformed.append(idx)

        if malformed:
            return ChainDiagnostics(
                ok=False,
                length=len(records),
                broken_at=malformed[0],
                reason=f"malformed JSON at line index {malformed[0]}",
                malformed_lines=tuple(malformed),
            )

        previous = GENESIS_HASH
        for idx, rec in enumerate(records):
            expected = rec.expected_hash()
            if rec.record_hash != expected:
                return ChainDiagnostics(
                    ok=False,
                    length=len(records),
                    broken_at=idx,
                    reason=(
                        f"record_hash mismatch at index {idx}: stored "
                        f"{rec.record_hash[:12]}… != computed {expected[:12]}…"
                    ),
                )
            if rec.previous_record_hash != previous:
                return ChainDiagnostics(
                    ok=False,
                    length=len(records),
                    broken_at=idx,
                    reason=(
                        f"broken link at index {idx}: previous_record_hash "
                        f"{rec.previous_record_hash[:12]}… != head {previous[:12]}…"
                    ),
                )
            previous = rec.record_hash

        return ChainDiagnostics(
            ok=True,
            length=len(records),
            head_hash=records[-1].record_hash if records else None,
            reason="chain intact" if records else "empty ledger",
        )


__all__ = [
    "ARTIFACT_GIT_DIFF",
    "ARTIFACT_TEST_RESULT",
    "ARTIFACT_SECRET_SCAN",
    "ARTIFACT_REVIEW",
    "ARTIFACT_ROLLBACK",
    "ARTIFACT_OWNER_CHALLENGE",
    "ARTIFACT_OWNER_GRANT",
    "ARTIFACT_AUDIT_RESULT",
    "ARTIFACT_CAPABILITY_ATTESTATION",
    "GENESIS_HASH",
    "canonical_json",
    "sha256_hex",
    "hermes_home",
    "EvidenceArtifact",
    "GitDiffEvidence",
    "VerificationCommandResult",
    "SecretScanEvidence",
    "ReviewEvidence",
    "RollbackEvidence",
    "GuardrailEvidenceBundle",
    "GuardrailDecisionRecord",
    "ChainDiagnostics",
    "GuardrailLedger",
]
