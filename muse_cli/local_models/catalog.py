"""Open-weight model candidate catalog.

The repo already ships a *provider* catalog (``muse_model_catalog.py`` +
``config/model-catalog.yaml``) describing hosted/keyed models. This module is
the complementary **open-weight / local** view: the candidate models you might
*download and run yourself* (Qwen, DeepSeek, Kimi, GLM coding/reasoning
families, plus local embeddings and rerankers), each annotated with the fields
a bootstrap decision and a routing policy need:

- name, source, access type, **license**
- recommended runtime + minimum RAM/VRAM + context length
- strengths / weaknesses
- default routing lanes
- checksum / source-verification instructions

It reads the ``open_weight_candidates`` section of the same YAML so adding a
model stays a data edit. The section is optional — if absent, the catalog is
simply empty, so this never breaks the existing provider loader or its tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "model-catalog.yaml"
)

# Tiers a candidate can be recommended for (mirrors hardware_probe tiers).
VALID_TIERS: frozenset[str] = frozenset({"laptop", "desktop", "workstation", "server"})


@dataclass(frozen=True)
class OpenWeightModel:
    name: str
    source: str  # e.g. "huggingface:Qwen/Qwen2.5-Coder-7B-Instruct" or "ollama:qwen2.5-coder"
    access: str  # "open-weight" | "open-source" | "gated"
    license: str
    runtime: str  # recommended ServerAdapter runtime
    min_ram_gb: float
    min_vram_gb: float
    context: Optional[int]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    routing_lanes: tuple[str, ...]
    tiers: tuple[str, ...]
    kind: str = "chat"  # "chat" | "coder" | "reasoning" | "embedding" | "reranker"
    verify: str = ""  # checksum / source-verification instructions

    def fits(self, *, ram_gb: float, vram_gb: float) -> bool:
        """True if a box with this RAM/VRAM can plausibly run the model.

        VRAM satisfies the requirement if present; otherwise RAM must cover the
        *RAM* floor (CPU inference). A model with ``min_vram_gb == 0`` is
        CPU-friendly and only needs RAM.
        """

        if self.min_vram_gb > 0 and vram_gb >= self.min_vram_gb:
            return True
        if self.min_vram_gb > 0 and vram_gb < self.min_vram_gb:
            # No GPU big enough — fall back to RAM only if it's generous.
            return ram_gb >= max(self.min_ram_gb, self.min_vram_gb)
        return ram_gb >= self.min_ram_gb

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "access": self.access,
            "license": self.license,
            "runtime": self.runtime,
            "min_ram_gb": self.min_ram_gb,
            "min_vram_gb": self.min_vram_gb,
            "context": self.context,
            "kind": self.kind,
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "routing_lanes": list(self.routing_lanes),
            "tiers": list(self.tiers),
            "verify": self.verify,
        }


@dataclass
class OpenWeightCatalog:
    models: list[OpenWeightModel] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | str | None = None) -> "OpenWeightCatalog":
        catalog_path = Path(path) if path else DEFAULT_CATALOG_PATH
        if not catalog_path.exists():
            return cls()
        raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
        section = raw.get("open_weight_candidates") or []
        models: list[OpenWeightModel] = []
        for entry in section:
            models.append(_parse(entry))
        # Validate up front so a bad YAML edit fails loudly, not silently.
        for m in models:
            bad = set(m.tiers) - VALID_TIERS
            if bad:
                raise ValueError(f"{m.name}: invalid tiers {sorted(bad)}")
            if not m.license:
                raise ValueError(f"{m.name}: license field is required")
        return cls(models=models)

    def by_kind(self, kind: str) -> list[OpenWeightModel]:
        return [m for m in self.models if m.kind == kind]

    def by_lane(self, lane: str) -> list[OpenWeightModel]:
        return [m for m in self.models if lane in m.routing_lanes]

    def for_tier(self, tier: str) -> list[OpenWeightModel]:
        return [m for m in self.models if tier in m.tiers]

    def get(self, name: str) -> Optional[OpenWeightModel]:
        for m in self.models:
            if m.name == name:
                return m
        return None


def _parse(entry: dict[str, Any]) -> OpenWeightModel:
    def req(key: str) -> Any:
        if key not in entry:
            raise ValueError(
                f"open-weight candidate missing required field {key!r}: {entry}"
            )
        return entry[key]

    return OpenWeightModel(
        name=str(req("name")),
        source=str(req("source")),
        access=str(entry.get("access", "open-weight")),
        license=str(req("license")),
        runtime=str(entry.get("runtime", "ollama")),
        min_ram_gb=float(entry.get("min_ram_gb", 0)),
        min_vram_gb=float(entry.get("min_vram_gb", 0)),
        context=int(entry["context"]) if entry.get("context") is not None else None,
        strengths=tuple(entry.get("strengths", []) or []),
        weaknesses=tuple(entry.get("weaknesses", []) or []),
        routing_lanes=tuple(entry.get("routing_lanes", []) or []),
        tiers=tuple(entry.get("tiers", []) or []),
        kind=str(entry.get("kind", "chat")),
        verify=str(entry.get("verify", "")),
    )


def load_open_weight_catalog(path: Path | str | None = None) -> OpenWeightCatalog:
    return OpenWeightCatalog.load(path)
