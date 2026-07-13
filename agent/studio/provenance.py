"""Immutable evidence records for generated and authored Studio assets."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


_HASH_PREFIX = "sha256:"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return _HASH_PREFIX + digest.hexdigest()


@dataclass(frozen=True)
class AssetProvenance:
    asset_id: str
    content_hash: str
    formats: tuple[str, ...] = ()
    creator: str = ""
    generator: str = ""
    model_version: str = ""
    source: str = "original"
    prompt_ref: str = ""
    license: str = ""
    license_url: str = ""
    transformations: tuple[str, ...] = ()
    allowed_uses: tuple[str, ...] = ("private",)
    created_at: str = ""
    safety_status: str = "unverified"
    verification: tuple[str, ...] = ()
    signature: str = ""

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("asset_id is required")
        if not self.content_hash.startswith(_HASH_PREFIX) or len(self.content_hash) != 71:
            raise ValueError("content_hash must be sha256:<64 lowercase hex>")
        if any(char not in "0123456789abcdef" for char in self.content_hash[7:]):
            raise ValueError("content_hash must be lowercase hexadecimal")
        if self.source not in {"original", "licensed", "generated", "transformed"}:
            raise ValueError("source is invalid")
        if self.safety_status not in {"unverified", "passed", "blocked", "quarantined"}:
            raise ValueError("safety_status is invalid")
        if any(not isinstance(item, str) or not item for item in self.allowed_uses):
            raise ValueError("allowed_uses must contain non-empty strings")

    def public_record(self) -> dict[str, Any]:
        """Return the evidence-safe record; raw prompts are never a field."""

        return asdict(self)

    def write(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.public_record(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return destination


@dataclass(frozen=True)
class ProvenanceVerification:
    passed: bool
    failures: tuple[str, ...]
    content_hash: str


def verify_provenance(
    path: str | Path,
    provenance: AssetProvenance,
    *,
    required_use: str = "public",
) -> ProvenanceVerification:
    asset = Path(path)
    failures: list[str] = []
    if not asset.is_file():
        failures.append("asset_missing")
        actual_hash = ""
    else:
        actual_hash = sha256_file(asset)
        if actual_hash != provenance.content_hash:
            failures.append("content_hash")
    if not provenance.license.strip():
        failures.append("license")
    if provenance.source == "licensed" and not provenance.license_url.strip():
        failures.append("license_url")
    if required_use not in provenance.allowed_uses:
        failures.append("allowed_uses")
    if provenance.safety_status != "passed":
        failures.append("safety_status")
    if not provenance.creator.strip():
        failures.append("creator")
    if provenance.source == "generated":
        if not provenance.generator:
            failures.append("generator")
        if not provenance.model_version:
            failures.append("model_version")
        if not provenance.prompt_ref.strip():
            failures.append("prompt_ref")
    return ProvenanceVerification(not failures, tuple(failures), actual_hash)


__all__ = [
    "AssetProvenance",
    "ProvenanceVerification",
    "sha256_file",
    "verify_provenance",
]
