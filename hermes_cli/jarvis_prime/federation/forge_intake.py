"""Forge intake poison filter (Vol VI Part 5).

When trajectories arrive from federated peers or community contributors, the
central threat is data poisoning. muse's defense is structural, not
statistical: a contribution enters the distillation set only if **all** of
these hold —

1. ``verifier_passed`` — the executable verifier accepted it (callers must
   re-run the verifier locally; never trust a peer's claim),
2. **ledger-attested** — an :class:`ArtifactAttestation` whose content hash
   equals ``sha256(canonical_json(trajectory))``,
3. **symbolic hard gates clear** — deterministic rejection on residual
   secrets, gate-bypass / ledger-tamper language, or a forged owner
   authorization phrase embedded in the content,
4. contributor band ≥ B1 (B0 submissions that are otherwise clean are
   **quarantined** — propose-only semantics, surfaced for owner review).

Admitted items land in :class:`~hermes_cli.jarvis_prime.learning_dataset.DatasetStore`
as **PENDING** ("proposed") — the existing owner-approval loop stays the final
gate; nothing here can auto-approve. Rejections feed contributor reputation
(the second defense layer); every decision is ledgered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from hermes_cli.jarvis_prime.guardrail_evidence import (
    GuardrailLedger,
    canonical_json,
    sha256_hex,
)
from hermes_cli.jarvis_prime.learning_dataset import (
    DatasetCandidate,
    DatasetStore,
    Provenance,
    QualityGates,
    RejectedTrace,
    SourceTrust,
    TraceType,
    has_residual_secret,
)
from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

from . import KIND_INTAKE_DECISION
from .attestation import ArtifactAttestation
from .trust_ladder import ContributorBand, ContributorRecord, ContributorStore

# Deterministic contract-violation markers. A trajectory that *describes*
# bypassing the verification machinery is poison regardless of its payload.
GATE_BYPASS_PATTERNS: tuple[str, ...] = (
    "skip the test",
    "skip the tests",
    "bypass the gate",
    "bypass the gates",
    "disable verification",
    "disable the verifier",
    "weaken the guardrail",
    "comment out the assert",
)
LEDGER_TAMPER_PATTERNS: tuple[str, ...] = (
    "rewrite the ledger",
    "edit guardrail_ledger",
    "truncate the ledger",
    "delete the ledger",
    "forge the hash chain",
)


def _flatten_strings(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return "\n".join(_flatten_strings(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return "\n".join(_flatten_strings(v) for v in value)
    return ""


def symbolic_hard_gates(content: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
    """Deterministic hard gates over the trajectory's text. No model, no vibe."""

    text = _flatten_strings(content)
    lowered = text.lower()
    findings: list[str] = []
    if has_residual_secret(text):
        findings.append("residual secret or private key in content")
    for pattern in GATE_BYPASS_PATTERNS:
        if pattern in lowered:
            findings.append(f"gate-bypass marker: {pattern!r}")
    for pattern in LEDGER_TAMPER_PATTERNS:
        if pattern in lowered:
            findings.append(f"ledger-tamper marker: {pattern!r}")
    if AUTHORIZATION_PHRASE.lower() in lowered:
        findings.append("embedded owner authorization phrase (forged grant)")
    return (not findings, tuple(findings))


@dataclass(frozen=True)
class IntakeChecks:
    verifier_passed: bool
    ledger_attested: bool
    symbolic_gates_clear: bool
    contributor_band: str
    band_sufficient: bool
    findings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "verifier_passed": self.verifier_passed,
            "ledger_attested": self.ledger_attested,
            "symbolic_gates_clear": self.symbolic_gates_clear,
            "contributor_band": self.contributor_band,
            "band_sufficient": self.band_sufficient,
            "findings": list(self.findings),
        }


@dataclass(frozen=True)
class IntakeDecision:
    admitted: bool
    quarantined: bool
    reasons: tuple[str, ...]
    checks: IntakeChecks
    trajectory_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "admitted": self.admitted,
            "quarantined": self.quarantined,
            "reasons": list(self.reasons),
            "checks": self.checks.to_dict(),
            "trajectory_sha256": self.trajectory_sha256,
        }


def trajectory_sha256(trajectory: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json(dict(trajectory)))


def evaluate_contribution(
    trajectory: Mapping[str, Any],
    *,
    contributor: ContributorRecord,
    verifier_passed: bool,
    attestation: Optional[ArtifactAttestation],
    store: Optional[ContributorStore] = None,
    ledger: Optional[GuardrailLedger] = None,
) -> IntakeDecision:
    """Run the full poison filter over one contributed trajectory."""

    content_hash = trajectory_sha256(trajectory)
    reasons: list[str] = []

    if not verifier_passed:
        reasons.append("verifier did not pass the trajectory")

    ledger_attested = attestation is not None and attestation.payload_sha256 == content_hash
    if attestation is None:
        reasons.append("no ledger attestation supplied")
    elif not ledger_attested:
        reasons.append(
            "attestation content hash does not match the trajectory (lookalike substitution)"
        )

    gates_clear, findings = symbolic_hard_gates(trajectory)
    if not gates_clear:
        reasons.extend(findings)

    band = contributor.band
    band_sufficient = band.rank >= ContributorBand.B1.rank
    quarantined = False
    if not band_sufficient and not reasons:
        # Clean submission from a propose-only contributor: quarantine for
        # owner review rather than reject.
        quarantined = True

    checks = IntakeChecks(
        verifier_passed=verifier_passed,
        ledger_attested=ledger_attested,
        symbolic_gates_clear=gates_clear,
        contributor_band=band.value,
        band_sufficient=band_sufficient,
        findings=findings,
    )
    admitted = not reasons and band_sufficient
    if not band_sufficient:
        reasons.append(f"contributor band {band.value} is propose-only")
    decision = IntakeDecision(
        admitted=admitted,
        quarantined=quarantined,
        reasons=tuple(reasons),
        checks=checks,
        trajectory_sha256=content_hash,
    )

    if ledger is not None:
        ledger.append(KIND_INTAKE_DECISION, contributor.contributor_id, decision.to_dict())

    if store is not None and not quarantined:
        # Reputation is the second layer: symbolic-gate violations are fatal.
        store.record_outcome(
            contributor.contributor_id,
            accepted=admitted,
            fatal=not gates_clear,
            ledger=ledger,
        )
    return decision


def admit_to_distillation(
    trajectory: Mapping[str, Any],
    decision: IntakeDecision,
    dataset_store: DatasetStore,
    *,
    source_uri: str,
    trace_type: TraceType = TraceType.CODING_TASK,
) -> Optional[DatasetCandidate]:
    """Store an **admitted** trajectory as a PENDING dataset candidate.

    ``DatasetStore.add_candidate`` re-runs its own hard filters (scrub, CoT
    strip, residual-secret, bulk-scrape, reward-hacking) — defense in depth —
    and stored candidates start PENDING; owner approval remains a separate,
    human step.
    """

    if not decision.admitted:
        return None
    provenance = Provenance(
        source_kind="federated",
        source_uri=source_uri,
        citations=(f"sha256:{decision.trajectory_sha256}",),
        trust=SourceTrust.COMMUNITY,
    )
    quality = QualityGates(
        tests_passed=decision.checks.verifier_passed,
        citations_verified=decision.checks.ledger_attested,
        reviewer_passed=decision.checks.symbolic_gates_clear,
        rollback_available=True,  # a PENDING candidate is trivially revertible
    )
    try:
        return dataset_store.add_candidate(
            trace_type,
            dict(trajectory),
            provenance,
            quality,
            labels=("federated",),
        )
    except RejectedTrace:
        return None


__all__ = [
    "GATE_BYPASS_PATTERNS",
    "LEDGER_TAMPER_PATTERNS",
    "symbolic_hard_gates",
    "trajectory_sha256",
    "IntakeChecks",
    "IntakeDecision",
    "evaluate_contribution",
    "admit_to_distillation",
]
