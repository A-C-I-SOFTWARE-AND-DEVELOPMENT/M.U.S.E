"""JARVIS Learning Dataset Pipeline.

Turns validated, source-backed JARVIS work into a high-quality dataset for
future fine-tuning, preference training, skill creation, and model
evaluation — **without ever storing secrets or raw chain-of-thought**.

Design constraints (non-negotiable):

* Only *validated* traces are stored. ``DatasetStore.add_candidate`` runs
  every filter and refuses (raises :class:`RejectedTrace`) anything that
  leaks a secret/private key, carries raw chain-of-thought that cannot be
  stripped, is a failed patch not labeled as a negative example, fails the
  required quality gates for its type, or looks like unlicensed bulk-scraped
  content.
* Every stored example carries **provenance + quality labels**.
* The **owner** approves/rejects candidates before they are eligible for
  export (``PENDING`` → ``APPROVED``/``REJECTED``).

This module *consumes* existing trajectory capture
(:func:`agent.trajectory.save_trajectory` output, the trajectory
compressor) and the Research Vault — it does **not** re-implement
trajectory recording. Filters reuse :mod:`agent.redact`. Quality labels are
derived from the real JARVIS verification gates
(:func:`hermes_cli.jarvis_prime.gates.run_gate_summary`).

Clean-room, stdlib-only, local JSONL persistence with atomic writes and
``0o600`` perms — mirrors :class:`hermes_cli.jarvis_prime.research_vault.ResearchVault`.
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
from typing import Any, Iterable, Mapping, Optional

from agent.redact import redact_sensitive_text
from agent.trajectory import has_incomplete_scratchpad
from hermes_cli.jarvis_prime.memory_tree import MemorySource, SourceTrust


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TraceType(str, Enum):
    CODING_TASK = "coding_task_trace"
    RESEARCH_ANSWER = "research_answer_trace"
    EVIDENCE_VERIFICATION = "evidence_verification_trace"
    MOBILE_ACTION = "mobile_action_trace"
    WORKER_REVIEW = "worker_review_trace"
    FAILED_ATTEMPT = "failed_attempt_trace"
    USER_APPROVED_SKILL = "user_approved_skill_trace"


class CandidateStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPORTED = "exported"


#: Label applied to a failed patch / failed attempt so it can be retained as
#: a negative training example rather than silently discarded.
NEGATIVE_EXAMPLE = "negative_example"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class RejectedTrace(ValueError):
    """A candidate failed a hard filter and must not be stored."""


# ---------------------------------------------------------------------------
# Chain-of-thought stripping
# ---------------------------------------------------------------------------

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_SCRATCHPAD_RE = re.compile(
    r"<REASONING_SCRATCHPAD>.*?</REASONING_SCRATCHPAD>", re.DOTALL
)


def strip_chain_of_thought(text: str) -> str:
    """Remove ``<think>…</think>`` / ``<REASONING_SCRATCHPAD>…</…>`` blocks.

    Raises :class:`RejectedTrace` when an *unclosed* scratchpad remains — we
    never store a trace whose private reasoning cannot be cleanly removed.
    """

    if not text:
        return text
    cleaned = _THINK_RE.sub("", text)
    cleaned = _SCRATCHPAD_RE.sub("", cleaned)
    if has_incomplete_scratchpad(cleaned) or "<think>" in cleaned.lower():
        raise RejectedTrace(
            "raw chain-of-thought present and cannot be stripped cleanly"
        )
    # Collapse the blank lines left behind by removed blocks.
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def scrub_record(text: str) -> str:
    """Force-redact secrets/keys/tokens/PII from a block of text."""

    if not text:
        return text
    return redact_sensitive_text(text, force=True)


# Residual-secret guard: a private-key header surviving redaction means the
# record is unsafe to store. ``redact_sensitive_text`` replaces these with a
# bracketed placeholder, so any *raw* header here is a leak.
_RESIDUAL_SECRET_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"\bsk-[A-Za-z0-9]{16,}\b|"
    r"\bghp_[A-Za-z0-9]{20,}\b|"
    r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"
)


def has_residual_secret(text: str) -> bool:
    """True if a recognizable raw secret survived redaction."""

    return bool(text) and bool(_RESIDUAL_SECRET_RE.search(text))


def looks_like_bulk_scraped(provenance: "Provenance", content: Mapping[str, Any]) -> bool:
    """Heuristic flag for unlicensed bulk-scraped content.

    A large blob with no citation and an untrusted/unknown source is treated
    as unlicensed bulk content and refused. Conservative by design — false
    positives are safer than storing scraped corpora.
    """

    body = json.dumps(content, ensure_ascii=False)
    if len(body) < 20_000:
        return False
    if provenance.citations:
        return False
    return provenance.trust in (SourceTrust.UNVERIFIED, SourceTrust.COMMUNITY)


# ---------------------------------------------------------------------------
# Provenance + quality
# ---------------------------------------------------------------------------


@dataclass
class Provenance:
    """Where a trace came from — required on every stored example."""

    source_kind: str  # trajectory | research_vault | ledger | job | memory | manual
    source_uri: str = ""
    job_id: Optional[str] = None
    citations: tuple[str, ...] = ()
    trust: SourceTrust = SourceTrust.UNVERIFIED

    def to_dict(self) -> dict[str, object]:
        return {
            "source_kind": self.source_kind,
            "source_uri": self.source_uri,
            "job_id": self.job_id,
            "citations": list(self.citations),
            "trust": self.trust.value,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Provenance":
        return cls(
            source_kind=str(d.get("source_kind", "manual")),
            source_uri=str(d.get("source_uri", "")),
            job_id=d.get("job_id"),
            citations=tuple(d.get("citations", []) or []),
            trust=SourceTrust(d.get("trust", SourceTrust.UNVERIFIED.value)),
        )

    def as_memory_source(self) -> MemorySource:
        """Bridge to a Memory Tree provenance pointer."""

        return MemorySource(uri=self.source_uri, trust=self.trust, excerpt="")


@dataclass
class QualityGates:
    """The quality labels every example carries.

    Mirrors the JARVIS verification gates: tests passed, citations verified,
    owner approved, reviewer passed, rollback available.
    """

    tests_passed: bool = False
    citations_verified: bool = False
    owner_approved: bool = False
    reviewer_passed: bool = False
    rollback_available: bool = False

    @staticmethod
    def required_for(trace_type: TraceType) -> tuple[str, ...]:
        if trace_type == TraceType.CODING_TASK:
            return ("tests_passed", "reviewer_passed", "rollback_available")
        if trace_type in (TraceType.RESEARCH_ANSWER, TraceType.EVIDENCE_VERIFICATION):
            return ("citations_verified",)
        if trace_type == TraceType.WORKER_REVIEW:
            return ("reviewer_passed",)
        if trace_type == TraceType.USER_APPROVED_SKILL:
            return ("owner_approved", "reviewer_passed")
        if trace_type == TraceType.MOBILE_ACTION:
            return ("owner_approved",)
        # FAILED_ATTEMPT has no positive gate requirement (it's a negative).
        return ()

    def passed(self, trace_type: TraceType) -> bool:
        return all(getattr(self, g) for g in self.required_for(trace_type))

    def to_dict(self) -> dict[str, object]:
        return {
            "tests_passed": self.tests_passed,
            "citations_verified": self.citations_verified,
            "owner_approved": self.owner_approved,
            "reviewer_passed": self.reviewer_passed,
            "rollback_available": self.rollback_available,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "QualityGates":
        return cls(
            tests_passed=bool(d.get("tests_passed", False)),
            citations_verified=bool(d.get("citations_verified", False)),
            owner_approved=bool(d.get("owner_approved", False)),
            reviewer_passed=bool(d.get("reviewer_passed", False)),
            rollback_available=bool(d.get("rollback_available", False)),
        )

    @classmethod
    def from_gate_summary(
        cls, packet: Mapping[str, Any], *, citations_verified: bool = False
    ) -> "QualityGates":
        """Derive quality labels from the real JARVIS verification gates.

        Reuses :func:`hermes_cli.jarvis_prime.gates.run_gate_summary` rather
        than re-implementing gate logic.
        """

        from hermes_cli.jarvis_prime.gates import GateOutcome, run_gate_summary

        summary = run_gate_summary(packet)
        by_name = {r.name: r.outcome for r in summary.results}

        def ok(name: str) -> bool:
            return by_name.get(name) == GateOutcome.PASS

        return cls(
            tests_passed=ok("test"),
            citations_verified=citations_verified,
            owner_approved=ok("owner_approval"),
            reviewer_passed=ok("review"),
            rollback_available=ok("rollback"),
        )


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------


@dataclass
class DatasetCandidate:
    id: str
    trace_type: TraceType
    content: dict[str, Any]
    provenance: Provenance
    quality: QualityGates
    status: CandidateStatus = CandidateStatus.PENDING
    labels: tuple[str, ...] = ()
    task_key: str = ""  # groups a positive with its negative sibling
    created_at: str = field(default_factory=_now_iso)
    resolved_at: Optional[str] = None
    owner_decision_note: Optional[str] = None

    @property
    def is_negative(self) -> bool:
        return NEGATIVE_EXAMPLE in self.labels

    def approve(self, note: str = "") -> None:
        self.status = CandidateStatus.APPROVED
        self.resolved_at = _now_iso()
        self.owner_decision_note = note or "approved"

    def reject(self, note: str = "") -> None:
        self.status = CandidateStatus.REJECTED
        self.resolved_at = _now_iso()
        self.owner_decision_note = note or "rejected"

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "trace_type": self.trace_type.value,
            "content": self.content,
            "provenance": self.provenance.to_dict(),
            "quality": self.quality.to_dict(),
            "status": self.status.value,
            "labels": list(self.labels),
            "task_key": self.task_key,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "owner_decision_note": self.owner_decision_note,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "DatasetCandidate":
        return cls(
            id=str(d["id"]),
            trace_type=TraceType(d["trace_type"]),
            content=dict(d.get("content", {}) or {}),
            provenance=Provenance.from_dict(d.get("provenance", {}) or {}),
            quality=QualityGates.from_dict(d.get("quality", {}) or {}),
            status=CandidateStatus(d.get("status", CandidateStatus.PENDING.value)),
            labels=tuple(d.get("labels", []) or []),
            task_key=str(d.get("task_key", "") or ""),
            created_at=str(d.get("created_at", "") or _now_iso()),
            resolved_at=d.get("resolved_at"),
            owner_decision_note=d.get("owner_decision_note"),
        )

    def audit_card(self) -> dict[str, object]:
        return {
            "id": self.id,
            "trace_type": self.trace_type.value,
            "status": self.status.value,
            "labels": list(self.labels),
            "quality": self.quality.to_dict(),
            "provenance": {
                "source_kind": self.provenance.source_kind,
                "source_uri": self.provenance.source_uri,
                "citations": list(self.provenance.citations),
            },
            "created_at": self.created_at,
        }


def _scrub_content(content: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively redact + strip CoT from every string in ``content``."""

    def _walk(value: Any) -> Any:
        if isinstance(value, str):
            return scrub_record(strip_chain_of_thought(value))
        if isinstance(value, Mapping):
            return {k: _walk(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_walk(v) for v in value]
        return value

    return {k: _walk(v) for k, v in content.items()}


def _candidate_id(trace_type: TraceType, content: Mapping[str, Any], created_at: str) -> str:
    # Non-cryptographic content-addressed id (dedup + stable key only), so the
    # hash choice is not a security control. Use SHA-256 with
    # ``usedforsecurity=False`` to keep static analysers honest.
    body = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(
        f"{trace_type.value}|{body}|{created_at}".encode(),
        usedforsecurity=False,
    ).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

def default_dataset_path() -> Path:
    """Profile-aware default store path.

    Resolves under :func:`hermes_constants.get_hermes_home` so each profile
    (and any ``HERMES_HOME`` override) gets its own learning dataset — per
    the AGENTS.md rule never to hardcode ``Path.home() / ".hermes"`` for
    persistent state.
    """

    from hermes_constants import get_hermes_home

    return get_hermes_home() / "jarvis_prime" / "learning_dataset.jsonl"


@dataclass
class DatasetStore:
    path: Optional[Path] = None
    candidates: dict[str, DatasetCandidate] = field(default_factory=dict)
    load_diagnostics: list[str] = field(default_factory=list)

    # -- validation + ingest ------------------------------------------------

    def add_candidate(
        self,
        trace_type: TraceType,
        content: Mapping[str, Any],
        provenance: Provenance,
        quality: QualityGates,
        *,
        labels: Iterable[str] = (),
        task_key: str = "",
        persist: bool = True,
    ) -> DatasetCandidate:
        """Validate and store a candidate, or raise :class:`RejectedTrace`.

        Stored candidates start ``PENDING`` — owner approval is a separate
        step (:meth:`approve`).
        """

        labels = tuple(labels)

        # 1. Scrub secrets + strip raw chain-of-thought (may raise).
        clean = _scrub_content(content)

        # 2. Residual-secret guard.
        flat = json.dumps(clean, ensure_ascii=False)
        if has_residual_secret(flat):
            raise RejectedTrace("residual secret/private key survived redaction")

        # 3. Failed patch must be explicitly labeled as a negative example.
        is_negative = NEGATIVE_EXAMPLE in labels
        if trace_type == TraceType.FAILED_ATTEMPT and not is_negative:
            raise RejectedTrace(
                "failed_attempt_trace must be labeled 'negative_example'"
            )

        # 4. Quality gates required for positive (non-negative) examples.
        if not is_negative and not quality.passed(trace_type):
            missing = [
                g for g in QualityGates.required_for(trace_type)
                if not getattr(quality, g)
            ]
            raise RejectedTrace(
                f"required quality gates not met for {trace_type.value}: "
                f"{', '.join(missing)}"
            )

        # 5. Unlicensed bulk-scraped content.
        if looks_like_bulk_scraped(provenance, clean):
            raise RejectedTrace("unlicensed bulk-scraped content refused")

        # 6. Reward-hacking / shortcut guard (Constitution C27). Never store a
        #    *positive* trace that reached its result via a reward hack or a
        #    destructive workaround — such traces generalize to misalignment
        #    (arXiv 2511.18397). Negative examples are exempt: demonstrating
        #    what NOT to do is the whole point of a negative example.
        if not is_negative:
            from hermes_cli.jarvis_prime.behavioral_risk import reward_hacking_evidence

            shortcut = reward_hacking_evidence(flat)
            if shortcut:
                raise RejectedTrace(
                    "reward-hacking / shortcut markers in positive trace: "
                    + ", ".join(sorted(set(shortcut))[:5])
                )

        created_at = _now_iso()
        cand = DatasetCandidate(
            id=_candidate_id(trace_type, clean, created_at),
            trace_type=trace_type,
            content=clean,
            provenance=provenance,
            quality=quality,
            labels=labels,
            task_key=task_key,
            created_at=created_at,
        )
        self.candidates[cand.id] = cand
        if persist:
            self.save()
        return cand

    # -- queue ops ----------------------------------------------------------

    def get(self, candidate_id: str) -> Optional[DatasetCandidate]:
        return self.candidates.get(candidate_id)

    def pending(self) -> list[DatasetCandidate]:
        return self.entries(status=CandidateStatus.PENDING)

    def entries(
        self,
        *,
        trace_type: Optional[TraceType] = None,
        status: Optional[CandidateStatus] = None,
    ) -> list[DatasetCandidate]:
        items = list(self.candidates.values())
        if trace_type:
            items = [c for c in items if c.trace_type == trace_type]
        if status:
            items = [c for c in items if c.status == status]
        return sorted(items, key=lambda c: c.created_at)

    def approve(self, candidate_id: str, note: str = "") -> DatasetCandidate:
        cand = self.candidates.get(candidate_id)
        if cand is None:
            raise KeyError(candidate_id)
        cand.approve(note)
        self.save()
        return cand

    def reject(self, candidate_id: str, note: str = "") -> DatasetCandidate:
        cand = self.candidates.get(candidate_id)
        if cand is None:
            raise KeyError(candidate_id)
        cand.reject(note)
        self.save()
        return cand

    def export_audit_cards(self) -> list[dict]:
        return [c.audit_card() for c in self.entries()]

    # -- exports (only APPROVED, plus labeled negatives) --------------------

    def _exportable(
        self, *, trace_type: Optional[TraceType] = None
    ) -> list[DatasetCandidate]:
        out = []
        for c in self.entries(status=CandidateStatus.APPROVED, trace_type=trace_type):
            if c.is_negative or c.quality.passed(c.trace_type):
                out.append(c)
        return out

    def export_jsonl(self, out_path: Path | str) -> int:
        records = self._exportable()
        lines = [
            json.dumps(
                {
                    "trace_type": c.trace_type.value,
                    "content": c.content,
                    "labels": list(c.labels),
                    "quality": c.quality.to_dict(),
                    "provenance": c.provenance.to_dict(),
                },
                ensure_ascii=False,
            )
            for c in records
        ]
        _write_text(Path(out_path), "\n".join(lines) + ("\n" if lines else ""))
        return len(records)

    def export_preference_pairs(self, out_path: Path | str) -> int:
        """Pair an approved positive with a negative sibling on the same task_key."""

        positives: dict[str, DatasetCandidate] = {}
        negatives: dict[str, DatasetCandidate] = {}
        for c in self.entries(status=CandidateStatus.APPROVED):
            if not c.task_key:
                continue
            if c.is_negative:
                negatives.setdefault(c.task_key, c)
            elif c.quality.passed(c.trace_type):
                positives.setdefault(c.task_key, c)

        pairs = []
        for key, pos in positives.items():
            neg = negatives.get(key)
            if neg is None:
                continue
            pairs.append(
                {
                    "task_key": key,
                    "chosen": pos.content,
                    "rejected": neg.content,
                    "provenance": pos.provenance.to_dict(),
                }
            )
        _write_text(
            Path(out_path),
            "\n".join(json.dumps(p, ensure_ascii=False) for p in pairs)
            + ("\n" if pairs else ""),
        )
        return len(pairs)

    def export_eval_cases(self, out_path: Path | str) -> int:
        """Eval cases from research/evidence traces (carry citations)."""

        records = [
            c
            for c in self._exportable()
            if c.trace_type
            in (TraceType.RESEARCH_ANSWER, TraceType.EVIDENCE_VERIFICATION)
        ]
        cases = [
            {
                "id": c.id,
                "prompt": c.content.get("question") or c.content.get("prompt", ""),
                "reference": c.content.get("answer") or c.content.get("reference", ""),
                "citations": list(c.provenance.citations),
                "quality": c.quality.to_dict(),
            }
            for c in records
        ]
        _write_text(
            Path(out_path),
            "\n".join(json.dumps(x, ensure_ascii=False) for x in cases)
            + ("\n" if cases else ""),
        )
        return len(cases)

    def export_skill_candidates(self, out_path: Path | str) -> int:
        records = [
            c
            for c in self._exportable(trace_type=TraceType.USER_APPROVED_SKILL)
        ]
        skills = [
            {
                "id": c.id,
                "skill_name": c.content.get("skill_name", ""),
                "rationale": c.content.get("rationale", ""),
                "body": c.content.get("body", ""),
                "provenance": c.provenance.to_dict(),
            }
            for c in records
        ]
        _write_text(
            Path(out_path),
            "\n".join(json.dumps(x, ensure_ascii=False) for x in skills)
            + ("\n" if skills else ""),
        )
        return len(skills)

    # -- persistence (mirrors ResearchVault) --------------------------------

    def _resolve_path(self) -> Path:
        return Path(self.path) if self.path else default_dataset_path()

    def save(self) -> Path:
        target = self._resolve_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = "".join(
            json.dumps(c.to_dict(), sort_keys=True, ensure_ascii=False) + "\n"
            for c in self.candidates.values()
        )
        _write_text(target, payload)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
        return target

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "DatasetStore":
        store = cls(path=path)
        target = store._resolve_path()
        if not target.exists():
            return store
        with open(target, "r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, 1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    cand = DatasetCandidate.from_dict(json.loads(raw))
                    store.candidates[cand.id] = cand
                except (json.JSONDecodeError, KeyError, ValueError) as exc:
                    store.load_diagnostics.append(f"line {lineno}: {exc}")
        return store


def _write_text(target: Path, content: str) -> None:
    """Atomic write with restrictive perms on the temp file."""

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".ldset-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
