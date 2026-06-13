"""Cross-attestation between sovereign MUSE nodes (Vol VI Parts 1/3/6).

The federation principle: MUSE instances are **sovereign nodes, not branches
of a central brain**. Sharing happens by content-addressed cross-attestation —
a node exports a signed :class:`AttestationBundle` (its verified ledger head
plus any artifact attestations) as a JSON file; a peer imports it into its
:class:`FederationRegistry`, which detects divergence before recording.

Two deterministic divergence rules follow from the ledger's append-only
property (a given node has exactly one true head hash per chain length):

- **split_brain** — the same node attests two different head hashes at the
  same ledger length.
- **fork** — an incoming attestation contradicts already-recorded history.

A node never attests its own ledger unless ``verify_chain()`` passes, and a
divergent peer bundle is refused (recorded only as a ``KIND_DIVERGENCE``
ledger entry) — sovereign nodes never silently adopt a divergent peer state.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from hermes_cli.jarvis_prime import constitution
from hermes_cli.jarvis_prime.guardrail_evidence import (
    EvidenceArtifact,
    GuardrailLedger,
    canonical_json,
    sha256_hex,
)

from . import (
    KIND_DIVERGENCE,
    KIND_PEER_ATTESTATION,
    FederationError,
    federation_dir,
)
from .identity import NodeIdentity, sign_payload, verify_signature


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class LedgerHeadAttestation:
    """A node's claim about its own verified ledger head."""

    node_id: str
    ledger_head_hash: str
    ledger_length: int
    constitution_version: str
    created_at: str
    payload_sha256: str
    signature: Mapping[str, str]

    @classmethod
    def build(
        cls,
        *,
        node_id: str,
        ledger_head_hash: str,
        ledger_length: int,
        constitution_version: str,
        signature_dir: Optional[Path] = None,
    ) -> "LedgerHeadAttestation":
        payload = {
            "node_id": node_id,
            "ledger_head_hash": ledger_head_hash,
            "ledger_length": ledger_length,
            "constitution_version": constitution_version,
        }
        return cls(
            node_id=node_id,
            ledger_head_hash=ledger_head_hash,
            ledger_length=ledger_length,
            constitution_version=constitution_version,
            created_at=_utc_iso(),
            payload_sha256=sha256_hex(canonical_json(payload)),
            signature=sign_payload(payload, dir=signature_dir),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "ledger_head_hash": self.ledger_head_hash,
            "ledger_length": self.ledger_length,
            "constitution_version": self.constitution_version,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.payload(),
            "created_at": self.created_at,
            "payload_sha256": self.payload_sha256,
            "signature": dict(self.signature),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LedgerHeadAttestation":
        return cls(
            node_id=str(data["node_id"]),
            ledger_head_hash=str(data.get("ledger_head_hash", "")),
            ledger_length=int(data.get("ledger_length", 0)),
            constitution_version=str(data.get("constitution_version", "")),
            created_at=str(data.get("created_at", "")),
            payload_sha256=str(data.get("payload_sha256", "")),
            signature=dict(data.get("signature", {})),
        )


@dataclass(frozen=True)
class ArtifactAttestation:
    """A node's content-hash attestation of one evidence artifact."""

    node_id: str
    artifact_type: str
    subject: str
    payload_sha256: str
    created_at: str

    @classmethod
    def for_artifact(cls, node_id: str, artifact: EvidenceArtifact) -> "ArtifactAttestation":
        return cls(
            node_id=node_id,
            artifact_type=artifact.artifact_type,
            subject=artifact.subject,
            payload_sha256=artifact.payload_sha256,
            created_at=_utc_iso(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "artifact_type": self.artifact_type,
            "subject": self.subject,
            "payload_sha256": self.payload_sha256,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ArtifactAttestation":
        return cls(
            node_id=str(data.get("node_id", "")),
            artifact_type=str(data.get("artifact_type", "")),
            subject=str(data.get("subject", "")),
            payload_sha256=str(data.get("payload_sha256", "")),
            created_at=str(data.get("created_at", "")),
        )


@dataclass
class AttestationBundle:
    """The file-based exchange unit between sovereign nodes."""

    node: NodeIdentity
    head: LedgerHeadAttestation
    artifacts: tuple[ArtifactAttestation, ...]
    exported_at: str
    bundle_sha256: str

    @staticmethod
    def _digest(
        node: NodeIdentity,
        head: LedgerHeadAttestation,
        artifacts: Sequence[ArtifactAttestation],
        exported_at: str,
    ) -> str:
        body = {
            "node": node.to_dict(),
            "head": head.to_dict(),
            "artifacts": [a.to_dict() for a in artifacts],
            "exported_at": exported_at,
        }
        return sha256_hex(canonical_json(body))

    @classmethod
    def build(
        cls,
        node: NodeIdentity,
        head: LedgerHeadAttestation,
        artifacts: Sequence[ArtifactAttestation] = (),
    ) -> "AttestationBundle":
        exported_at = _utc_iso()
        return cls(
            node=node,
            head=head,
            artifacts=tuple(artifacts),
            exported_at=exported_at,
            bundle_sha256=cls._digest(node, head, artifacts, exported_at),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": self.node.to_dict(),
            "head": self.head.to_dict(),
            "artifacts": [a.to_dict() for a in self.artifacts],
            "exported_at": self.exported_at,
            "bundle_sha256": self.bundle_sha256,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AttestationBundle":
        node = NodeIdentity.from_dict(dict(data["node"]))
        head = LedgerHeadAttestation.from_dict(dict(data["head"]))
        artifacts = tuple(
            ArtifactAttestation.from_dict(a) for a in data.get("artifacts", [])
        )
        exported_at = str(data.get("exported_at", ""))
        claimed = str(data.get("bundle_sha256", ""))
        recomputed = cls._digest(node, head, artifacts, exported_at)
        if claimed != recomputed:
            raise FederationError(
                "attestation bundle content hash mismatch — refusing tampered bundle"
            )
        return cls(
            node=node,
            head=head,
            artifacts=artifacts,
            exported_at=exported_at,
            bundle_sha256=claimed,
        )

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        return path

    @classmethod
    def read(cls, path: Path) -> "AttestationBundle":
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FederationError(f"cannot read attestation bundle {path}: {exc}") from exc
        return cls.from_dict(data)


def attest_local(
    ledger: GuardrailLedger,
    identity: NodeIdentity,
    *,
    artifacts: Sequence[EvidenceArtifact] = (),
    signature_dir: Optional[Path] = None,
) -> AttestationBundle:
    """Attest this node's own ledger head. Refuses a broken chain."""

    diag = ledger.verify_chain()
    if not diag.ok:
        raise FederationError(
            f"refusing to attest a broken ledger chain: {diag.reason or 'verify_chain failed'}"
        )
    head = LedgerHeadAttestation.build(
        node_id=identity.node_id,
        ledger_head_hash=diag.head_hash or "",
        ledger_length=diag.length,
        constitution_version=constitution.version(),
        signature_dir=signature_dir,
    )
    attested = tuple(
        ArtifactAttestation.for_artifact(identity.node_id, artifact) for artifact in artifacts
    )
    return AttestationBundle.build(identity, head, attested)


# ---------------------------------------------------------------------------
# Peer registry + divergence detection
# ---------------------------------------------------------------------------


@dataclass
class PeerRecord:
    """What this node knows about one peer, from its attestations."""

    node_id: str
    display_name: str
    algo: str
    public_key_hex: str
    first_seen: str
    last_seen: str
    heads: dict[str, str] = field(default_factory=dict)  # str(length) -> head_hash
    signature_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "display_name": self.display_name,
            "algo": self.algo,
            "public_key_hex": self.public_key_hex,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "heads": dict(self.heads),
            "signature_verified": self.signature_verified,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PeerRecord":
        return cls(
            node_id=str(data["node_id"]),
            display_name=str(data.get("display_name", "")),
            algo=str(data.get("algo", "")),
            public_key_hex=str(data.get("public_key_hex", "")),
            first_seen=str(data.get("first_seen", "")),
            last_seen=str(data.get("last_seen", "")),
            heads={str(k): str(v) for k, v in dict(data.get("heads", {})).items()},
            signature_verified=bool(data.get("signature_verified", False)),
        )


@dataclass(frozen=True)
class DivergenceFinding:
    node_id: str
    ledger_length: int
    hashes: tuple[str, ...]
    kind: str  # split_brain | fork

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "ledger_length": self.ledger_length,
            "hashes": list(self.hashes),
            "kind": self.kind,
        }


class FederationRegistry:
    """JSON-file registry of cross-attesting peers (a NEW registry file)."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else self.default_path()
        self._peers: dict[str, PeerRecord] = {}
        self._load()

    @staticmethod
    def default_path() -> Path:
        return federation_dir() / "federation_peers.json"

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for entry in data.get("peers", []):
            try:
                record = PeerRecord.from_dict(entry)
            except (KeyError, TypeError):
                continue
            self._peers[record.node_id] = record

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = {"peers": [p.to_dict() for p in self._peers.values()]}
        self.path.write_text(
            json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        try:
            os.chmod(self.path, 0o600)
        except OSError:  # pragma: no cover
            pass

    def _identity_findings(self, bundle: AttestationBundle) -> list[str]:
        """Identity checks that must hold before a bundle is considered.

        1. An Ed25519 ``node_id`` is content-derived: it must equal
           ``"node_" + sha256(public_key_hex)[:16]`` — a bundle claiming a
           known node id with a different key fails this immediately.
        2. Key continuity (TOFU): once a peer is recorded, its ``algo`` and
           ``public_key_hex`` are pinned; any change is a forgery attempt.
        """

        node = bundle.node
        findings: list[str] = []
        if node.algo == "ed25519":
            if not node.public_key_hex:
                findings.append("ed25519 identity carries no public key")
            else:
                derived = "node_" + sha256_hex(node.public_key_hex)[:16]
                if node.node_id != derived:
                    findings.append(
                        f"node_id {node.node_id} does not derive from the claimed public key"
                    )
        known = self._peers.get(node.node_id)
        if known is not None:
            if known.algo != node.algo:
                findings.append(
                    f"signing algo changed for known peer ({known.algo} -> {node.algo})"
                )
            if known.public_key_hex != node.public_key_hex:
                findings.append("public key changed for known peer")
        return findings

    def peers(self) -> list[PeerRecord]:
        return list(self._peers.values())

    def get(self, node_id: str) -> Optional[PeerRecord]:
        return self._peers.get(node_id)

    def head_history(self, node_id: str) -> dict[int, str]:
        record = self._peers.get(node_id)
        if record is None:
            return {}
        return {int(k): v for k, v in record.heads.items()}

    def record(
        self,
        bundle: AttestationBundle,
        *,
        ledger: Optional[GuardrailLedger] = None,
        allow_divergent: bool = False,
    ) -> PeerRecord:
        """Record a peer attestation; refuse divergent state by default.

        Identity is trust-on-first-use with key continuity: an existing
        peer's signing identity (algo + public key) may never change, and an
        Ed25519 ``node_id`` must derive from its claimed public key. Identity
        forgeries are refused unconditionally — ``allow_divergent`` only
        relaxes ledger-head divergence, never identity.
        """

        identity_findings = self._identity_findings(bundle)
        if identity_findings:
            if ledger is not None:
                ledger.append(
                    KIND_DIVERGENCE,
                    bundle.node.node_id,
                    {"findings": identity_findings, "kind": "identity_forgery"},
                )
            raise FederationError(
                "peer identity forgery refused: " + "; ".join(identity_findings)
            )

        findings = detect_divergence(self, bundle)
        if findings:
            if ledger is not None:
                ledger.append(
                    KIND_DIVERGENCE,
                    bundle.node.node_id,
                    {"findings": [f.to_dict() for f in findings]},
                )
            if not allow_divergent:
                raise FederationError(
                    "divergent peer attestation refused: "
                    + "; ".join(f"{f.kind}@len={f.ledger_length}" for f in findings)
                )

        verified, _reason = verify_signature(
            bundle.head.payload(), bundle.head.signature, bundle.node
        )
        now = _utc_iso()
        record = self._peers.get(bundle.node.node_id)
        if record is None:
            record = PeerRecord(
                node_id=bundle.node.node_id,
                display_name=bundle.node.display_name,
                algo=bundle.node.algo,
                public_key_hex=bundle.node.public_key_hex,
                first_seen=now,
                last_seen=now,
            )
            self._peers[record.node_id] = record
        record.last_seen = now
        record.signature_verified = verified
        record.heads[str(bundle.head.ledger_length)] = bundle.head.ledger_head_hash
        self._save()

        if ledger is not None:
            ledger.append(
                KIND_PEER_ATTESTATION,
                bundle.node.node_id,
                {
                    "ledger_length": bundle.head.ledger_length,
                    "ledger_head_hash": bundle.head.ledger_head_hash,
                    "constitution_version": bundle.head.constitution_version,
                    "bundle_sha256": bundle.bundle_sha256,
                    "signature_verified": verified,
                    "signature_algo": bundle.node.algo if bundle.head.signature else "",
                    "artifact_count": len(bundle.artifacts),
                },
            )
        return record


def detect_divergence(
    registry: FederationRegistry,
    incoming: AttestationBundle,
) -> list[DivergenceFinding]:
    """Deterministic split-brain / fork detection against recorded history."""

    history = registry.head_history(incoming.node.node_id)
    if not history:
        return []
    findings: list[DivergenceFinding] = []
    length = incoming.head.ledger_length
    incoming_hash = incoming.head.ledger_head_hash
    known = history.get(length)
    if known is not None and known != incoming_hash:
        findings.append(
            DivergenceFinding(
                node_id=incoming.node.node_id,
                ledger_length=length,
                hashes=(known, incoming_hash),
                kind="split_brain",
            )
        )
    # A shrinking chain contradicts append-only history: the node previously
    # attested a longer chain, so claiming a shorter head now is a fork
    # (truncation/rewrite), unless it re-attests the identical earlier head.
    max_known = max(history)
    if length < max_known and history.get(length) != incoming_hash:
        if not any(f.kind == "split_brain" for f in findings):
            findings.append(
                DivergenceFinding(
                    node_id=incoming.node.node_id,
                    ledger_length=length,
                    hashes=tuple(h for h in (history.get(length), incoming_hash) if h),
                    kind="fork",
                )
            )
    return findings


__all__ = [
    "LedgerHeadAttestation",
    "ArtifactAttestation",
    "AttestationBundle",
    "attest_local",
    "PeerRecord",
    "DivergenceFinding",
    "FederationRegistry",
    "detect_divergence",
]
