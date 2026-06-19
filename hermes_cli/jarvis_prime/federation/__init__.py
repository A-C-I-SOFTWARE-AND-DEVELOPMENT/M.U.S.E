"""muse federation & scaling-governance layer (muse Unbound Volume VI).

Sovereign muse nodes cross-attest by content hash — never by central control.
This package implements the Volume VI scaling layer on top of the existing
single-instance primitives (``guardrail_evidence``, ``owner_auth``,
``constitution``):

- ``identity`` / ``attestation`` — node identity, signed ledger-head
  attestations, file-based cross-attestation bundles, split-brain detection.
- ``quorum_auth`` — M-of-N threshold authorization generalizing the single
  owner phrase (1-of-1 stays byte-identical to today's flow).
- ``amendment`` — the structural asset-lock: non-amendable core clauses plus
  scale-graded amendment processes.
- ``trust_ladder`` / ``forge_intake`` — contributor bands B0–B3 and the
  poison filter in front of the distillation set.
- ``scaling`` / ``sovereignty`` / ``compliance_matrix`` — the resource-
  conditional decision tree with kill criteria, the per-deployment
  sovereignty index, and the compliance evidence matrix.

Everything is stdlib-first, local-first (exchange is JSON files, no sockets),
and additive: existing registries and ledger semantics are untouched. New
ledger record *kinds* and artifact *types* are plain strings declared here so
``guardrail_evidence.py`` never changes.
"""

from __future__ import annotations

from pathlib import Path

from hermes_cli.jarvis_prime.guardrail_evidence import hermes_home

# Evidence artifact types (extends the guardrail_evidence vocabulary).
ARTIFACT_NODE_ATTESTATION = "node_attestation"
ARTIFACT_QUORUM_GRANT = "quorum_authorization_grant"

# Ledger record kinds appended by this package.
KIND_PEER_ATTESTATION = "federation_peer_attestation"
KIND_DIVERGENCE = "federation_divergence"
KIND_AMENDMENT_DECISION = "constitution_amendment_decision"
KIND_QUORUM_GRANT = "quorum_grant"
KIND_BAND_CHANGE = "contributor_band_change"
KIND_INTAKE_DECISION = "forge_intake_decision"
KIND_SCALE_RECOMMENDATION = "scale_recommendation"
KIND_SOVEREIGNTY_REPORT = "sovereignty_report"
KIND_COMPLIANCE_EXPORT = "compliance_evidence_export"


class FederationError(RuntimeError):
    """A federation invariant was violated (broken chain, divergence, …)."""


def federation_dir() -> Path:
    """Per-node federation state directory (created on demand)."""

    path = hermes_home() / "jarvis_prime" / "federation"
    path.mkdir(parents=True, exist_ok=True)
    return path


__all__ = [
    "ARTIFACT_NODE_ATTESTATION",
    "ARTIFACT_QUORUM_GRANT",
    "KIND_PEER_ATTESTATION",
    "KIND_DIVERGENCE",
    "KIND_AMENDMENT_DECISION",
    "KIND_QUORUM_GRANT",
    "KIND_BAND_CHANGE",
    "KIND_INTAKE_DECISION",
    "KIND_SCALE_RECOMMENDATION",
    "KIND_SOVEREIGNTY_REPORT",
    "KIND_COMPLIANCE_EXPORT",
    "FederationError",
    "federation_dir",
]
