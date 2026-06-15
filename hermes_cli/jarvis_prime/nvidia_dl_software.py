"""NVIDIA Deep Learning Software registry + Research Vault bridge.

Loads ``docs/ai-intelligence/nvidia-deep-learning-software.yaml`` (the
machine-readable inventory behind
``docs/ai-intelligence/nvidia-deep-learning-software.md``) and bridges each
tool into the **Research Vault** so the existing JARVIS pipeline can cite
NVIDIA's deep-learning software stack — frameworks, inference, libraries, and
developer/devops tools — with proper provenance.

This module is a thin registry + bridge: it does **not** download, build, or run
any NVIDIA software, and makes **no network calls**. MUSE is hardware-agnostic
and several of these tools are proprietary NVIDIA binaries under the NVIDIA
Software License / EULA — we store provenance cards only. It reuses
``research_vault.ResearchVault`` for storage/provenance and
``research_vault.SourceType`` / ``EvidenceStrength`` for the evidence model.

Clean-room, stdlib + pyyaml.
"""

from __future__ import annotations

import os
import re
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

# Repo-root-relative default, mirroring open_data_sources.py so the registry
# resolves whether or not HERMES_HOME is set. parents[2] climbs
# hermes_cli/jarvis_prime/ -> hermes_cli/ -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = (
    _REPO_ROOT / "docs" / "ai-intelligence" / "nvidia-deep-learning-software.yaml"
)
# A copy bundled alongside the module is preferred when present (e.g. an
# installed wheel that ships docs/ in package data). The repo checkout uses the
# docs/ companion above; either resolves transparently.
_PACKAGED_REGISTRY_PATH = (
    Path(__file__).resolve().parent / "nvidia-deep-learning-software.yaml"
)
# Escape hatch for non-standard installs.
REGISTRY_PATH_ENV = "HERMES_NVIDIA_DL_SOFTWARE_REGISTRY"

_REQUIRED_FIELDS = (
    "rank",
    "key",
    "name",
    "section",
    "category",
    "evidence_strength",
)


class ToolCategory(str, Enum):
    FRAMEWORK = "framework"
    INFERENCE_SDK = "inference-sdk"
    INFERENCE_SERVER = "inference-server"
    INFERENCE_INTEGRATION = "inference-integration"
    LIBRARY = "library"
    PROFILER = "profiler"
    ORCHESTRATION = "orchestration"
    VISUALIZATION = "visualization"


def _slug(text: str) -> str:
    """Lowercase, hyphenated slug for tags (e.g. a section name)."""

    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")


@dataclass
class DevTool:
    rank: int
    key: str
    name: str
    section: str
    category: ToolCategory
    evidence_strength: EvidenceStrength
    purpose: str = ""
    capabilities: tuple[str, ...] = ()
    interfaces: str = ""  # gui | cli | both | library | sdk
    requires_gpu: bool = False
    license: str = ""  # open-source | proprietary | mixed
    official_uri: str = ""
    source_uris: tuple[str, ...] = ()
    license_notes: str = ""

    # -- predicates ---------------------------------------------------------

    @property
    def vault_source_uri(self) -> str:
        """First canonical URI, then the official URI, then an honest
        ``registry://`` placeholder so provenance is never empty."""

        if self.source_uris:
            return self.source_uris[0]
        if self.official_uri:
            return self.official_uri
        return f"registry://nvidia-dl-software/{self.key}"

    # -- serialization ------------------------------------------------------

    @classmethod
    def from_dict(cls, d: dict) -> "DevTool":
        missing = [f for f in _REQUIRED_FIELDS if d.get(f) in (None, "")]
        if missing:
            raise ValueError(
                f"nvidia-dl-software tool {d.get('key', '?')!r} missing required "
                f"field(s): {', '.join(missing)}"
            )
        return cls(
            rank=int(d["rank"]),
            key=str(d["key"]).strip(),
            name=str(d["name"]).strip(),
            section=str(d["section"]).strip(),
            category=ToolCategory(str(d["category"]).strip()),
            evidence_strength=EvidenceStrength(str(d["evidence_strength"]).strip()),
            purpose=str(d.get("purpose", "")).strip(),
            capabilities=tuple(d.get("capabilities", []) or []),
            interfaces=str(d.get("interfaces", "")).strip(),
            requires_gpu=bool(d.get("requires_gpu", False)),
            license=str(d.get("license", "")).strip(),
            official_uri=str(d.get("official_uri", "")).strip(),
            source_uris=tuple(d.get("source_uris", []) or []),
            license_notes=str(d.get("license_notes", "")).strip(),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "key": self.key,
            "name": self.name,
            "section": self.section,
            "category": self.category.value,
            "purpose": self.purpose,
            "capabilities": list(self.capabilities),
            "interfaces": self.interfaces,
            "requires_gpu": self.requires_gpu,
            "license": self.license,
            "official_uri": self.official_uri,
            "source_uris": list(self.source_uris),
            "license_notes": self.license_notes,
            "evidence_strength": self.evidence_strength.value,
        }

    # -- Research Vault bridge ---------------------------------------------

    def register_in_vault(
        self, vault: ResearchVault, *, persist: bool = False
    ) -> ResearchArtifact:
        """Record this tool as a Research Vault artifact.

        Tools are stored as ``OFFICIAL_DOC`` artifacts (NVIDIA product/landing
        pages), except those whose canonical source is a GitHub repo, stored as
        ``REPO``. The artifact carries the source URI, evidence strength, and
        license notes so the pipeline can cite it via
        ``learning_ingest.from_research_artifact``.
        """

        uri = self.vault_source_uri
        source_type = (
            SourceType.REPO if "github.com" in uri.lower() else SourceType.OFFICIAL_DOC
        )
        tags = [
            "nvidia-dl-software",
            f"section:{_slug(self.section)}",
            f"category:{self.category.value}",
        ]
        if self.license:
            tags.append(f"license:{self.license}")
        if self.requires_gpu:
            tags.append("requires-gpu")
        if self.interfaces:
            tags.append(f"interface:{self.interfaces}")
        summary = self.purpose or "; ".join(self.capabilities)
        return vault.add(
            title=self.name,
            source_uri=uri,
            source_type=source_type,
            evidence_strength=self.evidence_strength,
            summary=summary,
            tags=tags,
            license_notes=self.license_notes,
            persist=persist,
        )


# --- registry loading -------------------------------------------------------


def resolve_registry_path(path: Optional[Path] = None) -> Path:
    """Resolve the registry YAML, tolerating both source checkouts and installs.

    Order: explicit ``path`` arg, the ``HERMES_NVIDIA_DL_SOFTWARE_REGISTRY`` env
    var, a copy bundled next to this module, then the ``docs/`` companion in a
    source checkout. Raises an actionable ``FileNotFoundError`` if none exist
    rather than a bare traceback (``docs/`` is not shipped in the wheel).
    """

    if path is not None:
        return Path(path)
    env = os.environ.get(REGISTRY_PATH_ENV)
    if env:
        return Path(env)
    for candidate in (_PACKAGED_REGISTRY_PATH, DEFAULT_REGISTRY_PATH):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "nvidia-dl-software registry not found. It ships with the hermes-agent "
        f"source tree at {DEFAULT_REGISTRY_PATH}. Run from a checkout, or set "
        f"{REGISTRY_PATH_ENV}=/path/to/nvidia-deep-learning-software.yaml."
    )


def load_registry(path: Optional[Path] = None) -> list[DevTool]:
    """Parse the YAML registry and return tools sorted by rank.

    Raises ``ValueError`` on duplicate ranks/keys or missing required fields so
    a malformed registry fails loudly rather than silently dropping rows.
    """

    target = resolve_registry_path(path)
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    rows = raw.get("tools", [])
    tools = [DevTool.from_dict(row) for row in rows]

    ranks = [t.rank for t in tools]
    if len(set(ranks)) != len(ranks):
        dupes = sorted({r for r in ranks if ranks.count(r) > 1})
        raise ValueError(f"nvidia-dl-software registry has duplicate rank(s): {dupes}")
    keys = [t.key for t in tools]
    if len(set(keys)) != len(keys):
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        raise ValueError(f"nvidia-dl-software registry has duplicate key(s): {dupes}")

    return sorted(tools, key=lambda t: t.rank)


# --- partitions -------------------------------------------------------------


def get(key: str, *, tools: Optional[Iterable[DevTool]] = None) -> Optional[DevTool]:
    pool = list(tools) if tools is not None else load_registry()
    for t in pool:
        if t.key == key:
            return t
    return None


def by_category(
    category: ToolCategory, *, tools: Optional[Iterable[DevTool]] = None
) -> list[DevTool]:
    pool = list(tools) if tools is not None else load_registry()
    return [t for t in pool if t.category == category]


def by_section(
    section: str, *, tools: Optional[Iterable[DevTool]] = None
) -> list[DevTool]:
    pool = list(tools) if tools is not None else load_registry()
    return [t for t in pool if t.section == section]


def sections(tools: Optional[Iterable[DevTool]] = None) -> list[str]:
    """Page sections in first-seen (rank) order."""

    pool = list(tools) if tools is not None else load_registry()
    seen: list[str] = []
    for t in pool:
        if t.section not in seen:
            seen.append(t.section)
    return seen


# --- Research Vault bulk bridge ---------------------------------------------


@dataclass
class VaultRegistration:
    registered: list[ResearchArtifact] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (key, reason)


def register_all_in_vault(
    vault: ResearchVault,
    *,
    tools: Optional[Iterable[DevTool]] = None,
    persist: bool = True,
) -> VaultRegistration:
    """Bridge every registry tool into ``vault`` in one pass.

    Unlike the open-data registry there is no ``no_llm_training`` analog (these
    are tools, not training corpora), so every tool is registered. ``skipped``
    is kept for shape-parity with ``open_data_sources.register_all_in_vault``.
    Saves once at the end.
    """

    pool = list(tools) if tools is not None else load_registry()
    result = VaultRegistration()
    for tool in pool:
        result.registered.append(tool.register_in_vault(vault, persist=False))
    if persist and result.registered:
        vault.save()
    return result
