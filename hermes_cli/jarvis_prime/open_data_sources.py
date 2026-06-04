"""Open data sources registry for training / evaluating JARVIS.

Loads ``docs/ai-intelligence/open-data-sources.yaml`` (the canonical,
machine-readable inventory behind
``docs/ai-intelligence/top-open-data-sources-for-training.md``) and bridges
each source into the **Research Vault** so the existing JARVIS learning
pipeline can cite external open data with proper provenance.

This module is a thin registry + bridge: it does **not** download datasets,
re-implement the Research Vault, or train anything. It reuses
``research_vault.ResearchVault`` for storage/provenance and
``research_vault.SourceType`` / ``EvidenceStrength`` for the evidence model.

Clean-room, stdlib + pyyaml. No network calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional

import yaml

from hermes_cli.jarvis_prime.research_vault import (
    EvidenceStrength,
    ResearchArtifact,
    ResearchVault,
    SourceType,
)

# Repo-root-relative default, mirroring hermes_cli/oss_model_brain.py so the
# registry resolves whether or not HERMES_HOME is set. parents[2] climbs
# hermes_cli/jarvis_prime/ -> hermes_cli/ -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = (
    _REPO_ROOT / "docs" / "ai-intelligence" / "open-data-sources.yaml"
)

# Legal posture that must never feed training data (the Stack Overflow case).
NO_LLM_TRAINING = "no_llm_training"

_REQUIRED_FIELDS = (
    "rank",
    "key",
    "name",
    "role",
    "legal_posture",
    "evidence_strength",
)


class DatasetRole(str, Enum):
    TRAIN = "train"
    EVAL = "eval"
    BOTH = "both"


@dataclass
class DataSource:
    rank: int
    key: str
    name: str
    role: DatasetRole
    legal_posture: str
    evidence_strength: EvidenceStrength
    license_notes: str = ""
    languages: str = ""
    size: str = ""
    schema_provenance: str = ""
    quality_strengths: str = ""
    biases: str = ""
    best_tasks: str = ""
    recommended_subset: str = ""
    source_uris: tuple[str, ...] = ()
    core_ingest: bool = False
    benchmark_wall: bool = False

    # -- predicates ---------------------------------------------------------

    @property
    def trainable(self) -> bool:
        """Usable as training data: a train/both role that is not on the eval
        wall and is not legally barred from LLM training."""

        return (
            self.role in (DatasetRole.TRAIN, DatasetRole.BOTH)
            and not self.benchmark_wall
            and self.legal_posture != NO_LLM_TRAINING
        )

    @property
    def vault_source_uri(self) -> str:
        """First canonical URI, or an honest ``registry://`` placeholder when
        the upstream URL is unconfirmed (keeps provenance non-empty)."""

        if self.source_uris:
            return self.source_uris[0]
        return f"registry://open-data/{self.key}"

    # -- serialization ------------------------------------------------------

    @classmethod
    def from_dict(cls, d: dict) -> "DataSource":
        missing = [f for f in _REQUIRED_FIELDS if d.get(f) in (None, "")]
        if missing:
            raise ValueError(
                f"open-data source {d.get('key', '?')!r} missing required "
                f"field(s): {', '.join(missing)}"
            )
        return cls(
            rank=int(d["rank"]),
            key=str(d["key"]).strip(),
            name=str(d["name"]).strip(),
            role=DatasetRole(str(d["role"]).strip()),
            legal_posture=str(d["legal_posture"]).strip(),
            evidence_strength=EvidenceStrength(str(d["evidence_strength"]).strip()),
            license_notes=str(d.get("license_notes", "")).strip(),
            languages=str(d.get("languages", "")).strip(),
            size=str(d.get("size", "")).strip(),
            schema_provenance=str(d.get("schema_provenance", "")).strip(),
            quality_strengths=str(d.get("quality_strengths", "")).strip(),
            biases=str(d.get("biases", "")).strip(),
            best_tasks=str(d.get("best_tasks", "")).strip(),
            recommended_subset=str(d.get("recommended_subset", "")).strip(),
            source_uris=tuple(d.get("source_uris", []) or []),
            core_ingest=bool(d.get("core_ingest", False)),
            benchmark_wall=bool(d.get("benchmark_wall", False)),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "key": self.key,
            "name": self.name,
            "role": self.role.value,
            "legal_posture": self.legal_posture,
            "evidence_strength": self.evidence_strength.value,
            "license_notes": self.license_notes,
            "languages": self.languages,
            "size": self.size,
            "schema_provenance": self.schema_provenance,
            "quality_strengths": self.quality_strengths,
            "biases": self.biases,
            "best_tasks": self.best_tasks,
            "recommended_subset": self.recommended_subset,
            "source_uris": list(self.source_uris),
            "core_ingest": self.core_ingest,
            "benchmark_wall": self.benchmark_wall,
            "trainable": self.trainable,
        }

    # -- Research Vault bridge ---------------------------------------------

    def register_in_vault(
        self, vault: ResearchVault, *, persist: bool = False
    ) -> ResearchArtifact:
        """Record this source as a Research Vault artifact.

        Benchmark-wall sources are stored as ``BENCHMARK`` artifacts; everything
        else as ``REPO``. The artifact carries the source URI, evidence
        strength, and license notes so the learning pipeline can cite it via
        ``learning_ingest.from_research_artifact``.
        """

        source_type = (
            SourceType.BENCHMARK if self.benchmark_wall else SourceType.REPO
        )
        tags = ["open-data-source", self.role.value]
        if self.core_ingest:
            tags.append("core-ingest")
        if self.benchmark_wall:
            tags.append("benchmark-wall")
        return vault.add(
            title=self.name,
            source_uri=self.vault_source_uri,
            source_type=source_type,
            evidence_strength=self.evidence_strength,
            summary=self.quality_strengths or self.best_tasks,
            tags=tags,
            license_notes=self.license_notes,
            persist=persist,
        )


# --- registry loading -------------------------------------------------------


def load_registry(path: Optional[Path] = None) -> list[DataSource]:
    """Parse the YAML registry and return sources sorted by rank.

    Raises ``ValueError`` on duplicate ranks/keys or missing required fields so
    a malformed registry fails loudly rather than silently dropping rows.
    """

    target = Path(path) if path is not None else DEFAULT_REGISTRY_PATH
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    rows = raw.get("sources", [])
    sources = [DataSource.from_dict(row) for row in rows]

    ranks = [s.rank for s in sources]
    if len(set(ranks)) != len(ranks):
        dupes = sorted({r for r in ranks if ranks.count(r) > 1})
        raise ValueError(f"open-data registry has duplicate rank(s): {dupes}")
    keys = [s.key for s in sources]
    if len(set(keys)) != len(keys):
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        raise ValueError(f"open-data registry has duplicate key(s): {dupes}")

    return sorted(sources, key=lambda s: s.rank)


# --- partitions -------------------------------------------------------------


def get(key: str, *, sources: Optional[Iterable[DataSource]] = None) -> Optional[DataSource]:
    pool = list(sources) if sources is not None else load_registry()
    for s in pool:
        if s.key == key:
            return s
    return None


def core_ingest_sources(
    sources: Optional[Iterable[DataSource]] = None,
) -> list[DataSource]:
    pool = list(sources) if sources is not None else load_registry()
    return [s for s in pool if s.core_ingest]


def benchmark_wall_sources(
    sources: Optional[Iterable[DataSource]] = None,
) -> list[DataSource]:
    pool = list(sources) if sources is not None else load_registry()
    return [s for s in pool if s.benchmark_wall]


def eval_only_sources(
    sources: Optional[Iterable[DataSource]] = None,
) -> list[DataSource]:
    pool = list(sources) if sources is not None else load_registry()
    return [s for s in pool if s.role == DatasetRole.EVAL]


# --- Research Vault bulk bridge ---------------------------------------------


@dataclass
class VaultRegistration:
    registered: list[ResearchArtifact] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (key, reason)


def register_all_in_vault(
    vault: ResearchVault,
    *,
    sources: Optional[Iterable[DataSource]] = None,
    include_restricted: bool = False,
    persist: bool = True,
) -> VaultRegistration:
    """Bridge every registry source into ``vault`` in one pass.

    Sources whose ``legal_posture`` is ``no_llm_training`` (e.g. the Stack
    Overflow dump) are skipped by default so they never enter a citeable
    training corpus; pass ``include_restricted=True`` to register them anyway
    (their license_notes still carry the restriction). Saves once at the end.
    """

    pool = list(sources) if sources is not None else load_registry()
    result = VaultRegistration()
    for src in pool:
        if src.legal_posture == NO_LLM_TRAINING and not include_restricted:
            result.skipped.append((src.key, "legal_posture=no_llm_training"))
            continue
        result.registered.append(src.register_in_vault(vault, persist=False))
    if persist and result.registered:
        vault.save()
    return result
