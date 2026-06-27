"""Core types for Axiom Studio."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class Quality(str, Enum):
    DRAFT = "draft"          # Stub / cheap models, fastest iteration
    PREVIZ = "previz"        # Mid-tier, good enough for review reels
    FINAL = "final"          # SOTA models, longest render, real cost
    THEATRICAL = "theatrical"  # 4K HDR, ProRes, longest possible


class Provider(str, Enum):
    # World / interactive sim
    GENIE3 = "google/genie-3"
    DECART_OASIS = "decart/oasis"
    WORLDLABS_MARBLE = "worldlabs/marble"
    ODYSSEY = "odyssey/explorer-1"
    DREAMX = "dreamx/world"
    # Long-form video
    VEO3 = "google/veo-3"
    SORA2 = "openai/sora-2"
    RUNWAY_GEN4 = "runway/gen-4"
    KLING2 = "kuaishou/kling-2"
    HUNYUAN_VIDEO = "tencent/hunyuan-video"
    WAN21 = "alibaba/wan-2.1"
    LTX_VIDEO = "lightricks/ltx-video"
    # 3D
    HUNYUAN3D = "tencent/hunyuan3d-2"
    TRIPO3D = "tripo3d/v2.5"
    MESHY5 = "meshy/v5"
    TRELLIS = "microsoft/trellis"
    RODIN = "deemos/rodin"
    # Image / concept / storyboard
    MIDJOURNEY_V7 = "midjourney/v7"
    FLUX_PRO = "bfl/flux-1.1-pro"
    SD35 = "stability/sd-3.5-large"
    IDEOGRAM2 = "ideogram/v2"
    RECRAFT_V3 = "recraft/v3"
    # Voice
    ELEVENLABS_V3 = "elevenlabs/v3"
    CARTESIA_SONIC = "cartesia/sonic-2"
    HUME_EVI = "hume/evi-2"
    F5_TTS = "swivid/f5-tts"
    # Music
    SUNO_V4 = "suno/v4"
    UDIO = "udio/v1.5"
    STABLE_AUDIO_2 = "stability/stable-audio-2"
    MUSICGEN = "meta/musicgen-large"
    # SFX
    ELEVENLABS_SFX = "elevenlabs/sfx"
    MMAUDIO = "sonyai/mmaudio"
    # LLM (script / GDD / dialogue)
    CLAUDE_OPUS = "anthropic/claude-opus-4.6"
    GPT5 = "openai/gpt-5"
    GEMINI_25_PRO = "google/gemini-2.5-pro"
    # Animation / mocap
    MOVE_AI = "move/api-v3"
    CASCADEUR = "cascadeur/auto"
    DEEPMOTION = "deepmotion/animate-3d"
    # Engine
    UE5 = "epic/ue-5.5"
    UNITY6 = "unity/6-muse"
    GODOT4 = "godot/4.3"
    # Stub fallback (always available)
    STUB = "axiom/stub"
    # Local (Ollama on this device — free, runs on your GPU)
    OLLAMA_LOCAL = "ollama/local"


@dataclass
class FilmBrief:
    title: str
    logline: str
    runtime_min: int = 110
    genre: str = "drama"
    tone: str = "cinematic, character-driven"
    target_rating: str = "PG-13"
    quality: Quality = Quality.PREVIZ
    aspect: str = "2.39:1"
    fps: int = 24
    resolution: str = "3840x1608"  # 4K scope
    workdir: Optional[Path] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GameBrief:
    title: str
    genre: str
    target: str = "PC"
    perspective: str = "third-person"
    setting: str = ""
    core_loop: str = ""
    art_style: str = "stylized realism"
    runtime_hours: int = 25
    quality: Quality = Quality.PREVIZ
    engine: Provider = Provider.UE5
    workdir: Optional[Path] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageResult:
    stage: str
    provider: Provider
    status: str          # "ok" | "stubbed" | "skipped" | "failed"
    artifacts: List[str] = field(default_factory=list)   # file paths
    duration_s: float = 0.0
    est_cost_usd: float = 0.0
    notes: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectManifest:
    kind: str            # "film" | "game"
    title: str
    workdir: Path
    quality: Quality
    stages: List[StageResult] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_duration_s: float = 0.0

    def summary(self) -> str:
        lines = [
            f"=== {self.kind.upper()}: {self.title} ===",
            f"workdir: {self.workdir}",
            f"quality: {self.quality.value}",
            f"stages:  {len(self.stages)}",
            f"cost:    ${self.total_cost_usd:,.2f}",
            f"time:    {self.total_duration_s:.1f}s",
            "",
        ]
        for s in self.stages:
            tag = {"ok": "✓", "stubbed": "·", "skipped": "—", "failed": "✗"}.get(s.status, "?")
            lines.append(
                f"  {tag} {s.stage:24s} {s.provider.value:32s}  "
                f"{s.duration_s:6.2f}s  ${s.est_cost_usd:6.2f}  {s.notes}"
            )
        return "\n".join(lines)
