"""Configurable image, 3D, and audio provider adapter configuration."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class ProviderSlot:
    capability: str
    provider_id: str
    model: str
    requires_env: tuple[str, ...]
    est_cost_usd: float
    offline_stub: bool = True
    previs_only: bool = False


DEFAULT_PROVIDER_SLOTS: tuple[ProviderSlot, ...] = (
    ProviderSlot("concept_art", "pollinations", "flux", (), 0.0, True, True),
    ProviderSlot("concept_art", "google/imagen-4", "imagen-4", ("GOOGLE_API_KEY",), 0.04, False, False),
    ProviderSlot("mesh3d", "meshy/v5", "meshy-5", ("MESHY_API_KEY",), 0.80, False, False),
    ProviderSlot("mesh3d", "tripo3d/v2.5", "tripo-2.5", ("TRIPO_API_KEY",), 0.50, False, False),
    ProviderSlot("mesh3d", "axiom/stub", "stub", (), 0.0, True, True),
    ProviderSlot("voice", "edge-tts", "edge-tts", (), 0.0, True, True),
    ProviderSlot("voice", "elevenlabs/v3", "eleven-v3", ("ELEVENLABS_API_KEY",), 0.03, False, False),
    ProviderSlot("music", "meta/musicgen-large", "musicgen", (), 0.0, True, True),
    ProviderSlot("music", "suno/v4", "suno-v4", ("SUNO_API_KEY",), 0.10, False, False),
    ProviderSlot("sfx", "elevenlabs/sfx", "sfx-v1", ("ELEVENLABS_API_KEY",), 0.02, False, False),
    ProviderSlot("sfx", "axiom/stub", "stub", (), 0.0, True, True),
    ProviderSlot("previs", "lingbot/reactor", "reactor", (), 0.0, True, True),
    ProviderSlot("previs", "google/veo-3", "veo-3", ("GOOGLE_API_KEY",), 0.50, False, True),
)


@dataclass(frozen=True)
class ProviderConfig:
    profile: str
    slots: tuple[ProviderSlot, ...]
    offline_mode: bool
    previs_authoritative: bool = False

    def pick(self, capability: str) -> ProviderSlot | None:
        candidates = [s for s in self.slots if s.capability == capability]
        if self.offline_mode:
            stubs = [s for s in candidates if s.offline_stub]
            return stubs[0] if stubs else None
        for slot in candidates:
            if slot.requires_env and all(os.environ.get(k) for k in slot.requires_env):
                return slot
            if not slot.requires_env and not slot.offline_stub:
                return slot
        stubs = [s for s in candidates if s.offline_stub]
        return stubs[0] if stubs else None

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "profile": self.profile,
            "offline_mode": self.offline_mode,
            "previs_authoritative": self.previs_authoritative,
            "slots": [asdict(s) for s in self.slots],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> ProviderConfig:
        data = json.loads(path.read_text(encoding="utf-8"))
        slots = tuple(ProviderSlot(**s) for s in data.get("slots", []))
        return cls(
            profile=data["profile"],
            slots=slots,
            offline_mode=data.get("offline_mode", False),
            previs_authoritative=data.get("previs_authoritative", False),
        )


def build_provider_config(
    profile: str,
    *,
    offline: bool | None = None,
) -> ProviderConfig:
    if offline is None:
        offline = os.environ.get("AXIOM_STUDIO_OFFLINE", "").lower() in ("1", "true", "yes")
    return ProviderConfig(
        profile=profile,
        slots=DEFAULT_PROVIDER_SLOTS,
        offline_mode=offline,
        previs_authoritative=False,
    )


def slot_manifest_entry(slot: ProviderSlot) -> dict[str, Any]:
    return {
        "capability": slot.capability,
        "provider_id": slot.provider_id,
        "model": slot.model,
        "available": slot.offline_stub or all(os.environ.get(k) for k in slot.requires_env),
        "previs_only": slot.previs_only,
        "est_cost_usd": slot.est_cost_usd,
    }


__all__ = [
    "DEFAULT_PROVIDER_SLOTS",
    "ProviderConfig",
    "ProviderSlot",
    "build_provider_config",
    "slot_manifest_entry",
]
