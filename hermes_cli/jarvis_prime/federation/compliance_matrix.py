"""Compliance evidence matrix + exportable evidence package (Vol VI Part 4).

MUSE is already a compliance artifact: the hash-chained ledger, the eight
verification gates, the owner-approval gate, and the constitution self-audit
map almost one-to-one onto EU AI Act high-risk obligations (Art. 9/11/12/14/15),
SOC 2 common criteria, and ISO 27001 Annex A controls. ``CONTROL_MAPPINGS``
encodes that mapping; :func:`generate_evidence_package` builds a
content-addressed evidence package **from the live ledger** — the
``verify_chain()`` result embedded verbatim, grant counts and record-kind
histograms computed from actual records, the sovereignty report inlined.

This supplies the *evidence*, not the certificate: conformity assessment and
external audit remain human, third-party steps (see the spec doc's caveats).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hermes_cli.jarvis_prime import constitution
from hermes_cli.jarvis_prime.guardrail_evidence import (
    ARTIFACT_OWNER_GRANT,
    GuardrailLedger,
    canonical_json,
    sha256_hex,
)

from . import KIND_COMPLIANCE_EXPORT, KIND_QUORUM_GRANT
from .attestation import FederationRegistry
from .sovereignty import compute_sovereignty_index

FRAMEWORKS = ("eu_ai_act", "soc2", "iso27001")


@dataclass(frozen=True)
class ControlMapping:
    framework: str
    control_id: str
    control_title: str
    muse_mechanism: str
    evidence_kinds: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "framework": self.framework,
            "control_id": self.control_id,
            "control_title": self.control_title,
            "muse_mechanism": self.muse_mechanism,
            "evidence_kinds": list(self.evidence_kinds),
        }


CONTROL_MAPPINGS: tuple[ControlMapping, ...] = (
    # --- EU AI Act (high-risk obligations, Annex III systems) ---
    ControlMapping(
        "eu_ai_act",
        "Art9",
        "Risk management system",
        "Eight verification gates + capability wall (RC0-RC4) + behavioral self-audit",
        ("gate_summary", "capability_attestation", "audit_result"),
    ),
    ControlMapping(
        "eu_ai_act",
        "Art11",
        "Technical documentation (Annex IV)",
        "Constitution v" + constitution.version() + " + work packets + spec docs as living documentation",
        ("constitution_amendment_decision", "work_packet"),
    ),
    ControlMapping(
        "eu_ai_act",
        "Art12",
        "Record-keeping / logging integrated into core design",
        "Hash-chained tamper-evident GuardrailLedger with verify_chain() (native, not bolted on)",
        ("ledger_chain_diagnostics",),
    ),
    ControlMapping(
        "eu_ai_act",
        "Art14",
        "Human oversight (understand, override, stop)",
        "Owner-approval gate (exact phrase, nonce-bound) + quorum authorization + kill switch + rollback gate",
        ("owner_authorization_grant", "quorum_grant", "rollback"),
    ),
    ControlMapping(
        "eu_ai_act",
        "Art15",
        "Accuracy, robustness, cybersecurity",
        "Executable verifiers (held-out cases) + secret scans + capability attestations",
        ("test_result", "secret_scan", "capability_attestation"),
    ),
    # --- SOC 2 (common criteria) ---
    ControlMapping(
        "soc2",
        "CC4.1",
        "Monitoring of controls",
        "Constitution self-audit + sovereignty index + ledger kind histogram",
        ("sovereignty_report", "audit_result"),
    ),
    ControlMapping(
        "soc2",
        "CC6.1",
        "Logical access controls",
        "Owner-gated action set + contributor trust ladder (B0-B3) + quorum policies",
        ("owner_authorization_grant", "contributor_band_change"),
    ),
    ControlMapping(
        "soc2",
        "CC7.2",
        "Anomaly detection / immutable audit trail",
        "Append-only hash-chained ledger; verify_chain() detects mutation, reorder, truncation",
        ("ledger_chain_diagnostics", "federation_divergence"),
    ),
    ControlMapping(
        "soc2",
        "CC8.1",
        "Change management",
        "Amendment engine (non-amendable core) + owner-gated proposals + rollback gate",
        ("constitution_amendment_decision", "rollback"),
    ),
    # --- ISO 27001 Annex A ---
    ControlMapping(
        "iso27001",
        "A.5.35",
        "Independent review of information security",
        "Cross-node attestation + Merkle-anchored leaderboards (trustless third-party verification)",
        ("federation_peer_attestation", "forge_leaderboard_anchor"),
    ),
    ControlMapping(
        "iso27001",
        "A.8.15",
        "Logging",
        "GuardrailLedger: every gate decision, grant, duel, and amendment is appended",
        ("ledger_chain_diagnostics",),
    ),
    ControlMapping(
        "iso27001",
        "A.8.16",
        "Monitoring activities",
        "Sovereignty index + divergence detection + intake decisions",
        ("sovereignty_report", "federation_divergence", "forge_intake_decision"),
    ),
    ControlMapping(
        "iso27001",
        "A.8.32",
        "Change management",
        "Amendment engine + owner approval + quorum authorization",
        ("constitution_amendment_decision", "quorum_grant"),
    ),
)


def mappings_for(framework: str) -> tuple[ControlMapping, ...]:
    if framework == "all":
        return CONTROL_MAPPINGS
    if framework not in FRAMEWORKS:
        raise ValueError(f"unknown framework {framework!r}; expected one of {FRAMEWORKS} or 'all'")
    return tuple(m for m in CONTROL_MAPPINGS if m.framework == framework)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EvidencePackage:
    created_at: str
    framework: str
    constitution_version: str
    chain_diagnostics: dict[str, Any]
    owner_grant_count: int
    quorum_grant_count: int
    ledger_kind_histogram: dict[str, int]
    sovereignty: dict[str, Any]
    controls: list[dict[str, Any]] = field(default_factory=list)
    package_sha256: str = ""

    def body(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "framework": self.framework,
            "constitution_version": self.constitution_version,
            "chain_diagnostics": self.chain_diagnostics,
            "owner_grant_count": self.owner_grant_count,
            "quorum_grant_count": self.quorum_grant_count,
            "ledger_kind_histogram": self.ledger_kind_histogram,
            "sovereignty": self.sovereignty,
            "controls": self.controls,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.body(), "package_sha256": self.package_sha256}

    def seal(self) -> "EvidencePackage":
        self.package_sha256 = sha256_hex(canonical_json(self.body()))
        return self

    def verify(self) -> bool:
        return self.package_sha256 == sha256_hex(canonical_json(self.body()))

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        return path


def generate_evidence_package(
    framework: str = "all",
    *,
    ledger: Optional[GuardrailLedger] = None,
    registry: Optional[FederationRegistry] = None,
    record: bool = True,
) -> EvidencePackage:
    """Build a content-addressed evidence package from the live ledger."""

    active_ledger = ledger or GuardrailLedger()
    controls = [m.to_dict() for m in mappings_for(framework)]
    diag = active_ledger.verify_chain()

    histogram: dict[str, int] = {}
    owner_grants = 0
    quorum_grants = 0
    for rec in active_ledger.read_all():
        histogram[rec.kind] = histogram.get(rec.kind, 0) + 1
        if rec.kind == KIND_QUORUM_GRANT:
            quorum_grants += 1
        if rec.kind == ARTIFACT_OWNER_GRANT or rec.kind == "owner_grant":
            owner_grants += 1
        payload_type = rec.payload.get("artifact_type") if isinstance(rec.payload, dict) else None
        if payload_type == ARTIFACT_OWNER_GRANT:
            owner_grants += 1

    sovereignty = compute_sovereignty_index(ledger=active_ledger, registry=registry)
    package = EvidencePackage(
        created_at=_utc_iso(),
        framework=framework,
        constitution_version=constitution.version(),
        chain_diagnostics=diag.to_dict(),
        owner_grant_count=owner_grants,
        quorum_grant_count=quorum_grants,
        ledger_kind_histogram=histogram,
        sovereignty=sovereignty.to_dict(),
        controls=controls,
    ).seal()

    if record:
        active_ledger.append(
            KIND_COMPLIANCE_EXPORT,
            framework,
            {
                "package_sha256": package.package_sha256,
                "controls": len(controls),
                "chain_ok": diag.ok,
            },
        )
    return package


__all__ = [
    "FRAMEWORKS",
    "ControlMapping",
    "CONTROL_MAPPINGS",
    "mappings_for",
    "EvidencePackage",
    "generate_evidence_package",
]
