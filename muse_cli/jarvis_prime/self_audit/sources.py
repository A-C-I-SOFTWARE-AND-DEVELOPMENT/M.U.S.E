"""Bridge the reconstruction's cited sources into the Research Vault.

Loads ``docs/ai-intelligence/self-audit-sources.yaml`` and registers each entry
as a source-cited ``ResearchArtifact`` so the Self-Audit + Constitution layer is
itself source-backed (Petri, the reward-hacking paper, Constitutional AI, …).
The unverified "Mythos" seed is bridged at WEAK/contested and never asserted as
fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from muse_cli.jarvis_prime.research_vault import (
    EvidenceStrength,
    ResearchVault,
    SourceType,
)


def default_sources_path() -> Path:
    """Resolve the in-repo registry path relative to this module."""

    # .../muse_cli/jarvis_prime/self_audit/sources.py -> parents[3] == repo root
    return (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "ai-intelligence"
        / "self-audit-sources.yaml"
    )


@dataclass(frozen=True)
class ReconstructionSource:
    key: str
    title: str
    source_uri: str
    source_type: SourceType
    evidence_strength: EvidenceStrength
    reconstructs: str = ""
    tags: tuple[str, ...] = ()
    contested: bool = False


def load_sources(path: Optional[Path] = None) -> list[ReconstructionSource]:
    """Parse the registry YAML into :class:`ReconstructionSource` records."""

    import yaml  # local import: PyYAML is already a repo dependency

    target = Path(path) if path else default_sources_path()
    data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    out: list[ReconstructionSource] = []
    for raw in data.get("sources", []):
        out.append(
            ReconstructionSource(
                key=str(raw.get("key", "")),
                title=str(raw.get("title", "")),
                source_uri=str(raw.get("source_uri", "") or ""),
                source_type=SourceType(str(raw.get("source_type", "manual"))),
                evidence_strength=EvidenceStrength(
                    str(raw.get("evidence_strength", "moderate"))
                ),
                reconstructs=str(raw.get("reconstructs", "")),
                tags=tuple(raw.get("tags", []) or []),
                contested=bool(raw.get("contested", False)),
            )
        )
    return out


def register_in_vault(
    vault: ResearchVault,
    *,
    path: Optional[Path] = None,
    include_contested: bool = True,
    persist: bool = False,
) -> list[str]:
    """Add each source to ``vault`` as a ResearchArtifact; return artifact ids.

    ``persist`` defaults to ``False`` so the caller decides when to
    ``vault.save()`` — an existing vault is never clobbered by a partial write.
    """

    ids: list[str] = []
    for src in load_sources(path):
        if src.contested and not include_contested:
            continue
        art = vault.add(
            title=src.title,
            source_uri=src.source_uri,
            source_type=src.source_type,
            evidence_strength=src.evidence_strength,
            summary=src.reconstructs,
            tags=("self-audit", "mythos-reconstruction", *src.tags),
            persist=persist,
        )
        ids.append(art.id)
    return ids
