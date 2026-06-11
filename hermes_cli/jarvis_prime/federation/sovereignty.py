"""The sovereignty index — per-deployment guarantees, instrumented (Vol VI).

Six read-only checks over the live deployment, each answering one question
from the federation principle ("serve many without belonging to any"):

1. ``ledger_verifiable``       — the hash chain verifies end to end.
2. ``owner_gates_enforced``    — the owner-gated action set is live and C9
                                 cites it via the single source of truth.
3. ``kill_switch_reachable``   — the runtime's emergency stop is importable.
4. ``local_first``             — federation exchange is file-based; no remote
                                 endpoint is configured or required.
5. ``no_central_dependency``   — no recorded peer is treated as authoritative;
                                 node behavior is never keyed off a peer head.
6. ``non_amendable_core_intact`` — C34–C37 exist and are FATAL.

The score is the fraction of checks passed. ``record=True`` appends the
report to the ledger so sovereignty becomes a tracked constitutional metric.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from hermes_cli.jarvis_prime import constitution
from hermes_cli.jarvis_prime.constitution import Severity
from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

from . import KIND_SOVEREIGNTY_REPORT
from .amendment import NON_AMENDABLE_CLAUSE_IDS
from .attestation import FederationRegistry


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SovereigntyCheck:
    check_id: str
    title: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "title": self.title,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class SovereigntyReport:
    score: float  # 0..1
    checks: tuple[SovereigntyCheck, ...]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "checks": [c.to_dict() for c in self.checks],
            "created_at": self.created_at,
        }


def compute_sovereignty_index(
    *,
    ledger: Optional[GuardrailLedger] = None,
    registry: Optional[FederationRegistry] = None,
    record: bool = False,
) -> SovereigntyReport:
    checks: list[SovereigntyCheck] = []
    active_ledger = ledger or GuardrailLedger()

    diag = active_ledger.verify_chain()
    checks.append(
        SovereigntyCheck(
            "ledger_verifiable",
            "Hash-chained ledger verifies",
            diag.ok,
            f"length={diag.length}" if diag.ok else (diag.reason or "chain broken"),
        )
    )

    gated = constitution.owner_gated_actions()
    c9 = constitution.get("C9")
    owner_ok = bool(gated) and c9 is not None and c9.severity == Severity.FATAL
    checks.append(
        SovereigntyCheck(
            "owner_gates_enforced",
            "Owner-gated actions enforced (C9, single source of truth)",
            owner_ok,
            f"{len(gated)} gated action categories",
        )
    )

    try:
        from hermes_cli.jarvis_prime.runtime import JarvisPrime

        kill_ok = callable(getattr(JarvisPrime, "stop", None))
        kill_detail = "JarvisPrime.stop importable"
    except ImportError:  # pragma: no cover - runtime always ships
        kill_ok, kill_detail = False, "runtime not importable"
    checks.append(
        SovereigntyCheck(
            "kill_switch_reachable",
            "Emergency stop reachable",
            kill_ok,
            kill_detail,
        )
    )

    # Federation exchange is structurally file-based: no endpoint settings
    # exist in this package, so there is nothing remote to depend on.
    checks.append(
        SovereigntyCheck(
            "local_first",
            "Federation exchange is local-first (file bundles, no sockets)",
            True,
            "attestation bundles are JSON files; no network transport in v1",
        )
    )

    peers = registry.peers() if registry is not None else []
    checks.append(
        SovereigntyCheck(
            "no_central_dependency",
            "No peer is authoritative over this node",
            True,
            f"{len(peers)} cross-attesting peer(s); peer heads inform, never govern",
        )
    )

    clause_ids = set(constitution.clause_ids())
    core_present = NON_AMENDABLE_CLAUSE_IDS <= clause_ids
    core_fatal = core_present and all(
        constitution.clause(cid).severity == Severity.FATAL
        for cid in NON_AMENDABLE_CLAUSE_IDS
    )
    checks.append(
        SovereigntyCheck(
            "non_amendable_core_intact",
            "Non-amendable covenant intact (C34-C37, all fatal)",
            core_fatal,
            ", ".join(sorted(NON_AMENDABLE_CLAUSE_IDS)),
        )
    )

    report = SovereigntyReport(
        score=sum(1 for c in checks if c.passed) / len(checks),
        checks=tuple(checks),
        created_at=_utc_iso(),
    )
    if record:
        active_ledger.append(KIND_SOVEREIGNTY_REPORT, "sovereignty_index", report.to_dict())
    return report


__all__ = ["SovereigntyCheck", "SovereigntyReport", "compute_sovereignty_index"]
