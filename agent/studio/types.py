"""Core types for Axiom Studio."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


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
    IMAGEN4 = "google/imagen-4"
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
    UE5 = "epic/ue-5.6"
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


@dataclass(frozen=True)
class GameProductionSpec:
    """Release-oriented inputs for a source-complete game production run."""

    title: str
    project_id: str = ""
    engine: str = "unreal"
    engine_version: str = "5.6"
    platforms: tuple[str, ...] = ("windows",)
    multiplayer_model: str = "single_player"
    world_streaming: str = "partitioned"
    performance_budgets: Mapping[str, float] = field(default_factory=dict)
    accessibility_requirements: tuple[str, ...] = ()
    rights_checklist: tuple[str, ...] = ()
    rating_checklist: tuple[str, ...] = ()
    store_checklist: tuple[str, ...] = ()
    save_schema_version: int = 1
    migration_plan: str = ""
    crash_telemetry: str = "disabled"
    test_commands: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    build_commands: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    release_channels: tuple[str, ...] = ("internal",)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("game title is required")
        if self.engine not in {"unreal", "godot", "unity"}:
            raise ValueError("engine must be unreal, godot, or unity")
        if type(self.save_schema_version) is not int or self.save_schema_version < 1:
            raise ValueError("save_schema_version must be a positive integer")
        if not self.platforms:
            raise ValueError("at least one target platform is required")


@dataclass(frozen=True)
class GameBuildManifest:
    """Truthful game-foundry output; evidence controls ``playable``."""

    project_id: str
    title: str
    root: Path
    lanes: tuple[str, ...]
    engine: str
    engine_version: str
    engine_validation: str
    compiled: bool = False
    package_verified: bool = False
    smoke_verified: bool = False
    playable: bool = False
    command_evidence: tuple[Mapping[str, Any], ...] = ()
    artifact_hashes: Mapping[str, str] = field(default_factory=dict)
    unavailable_reason: str = ""
    created_at: str = ""


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


# ── AAA studio domain types ─────────────────────────────────────────


class Phase(str, Enum):
    """Canonical AAA production milestone gates."""
    CONCEPT = "concept"            # pitch / GDD draft / scope
    PROTOTYPE = "prototype"        # playable core loop
    VERTICAL_SLICE = "vertical_slice"  # 15-30 min AAA-quality slice
    ALPHA = "alpha"                # feature-complete, full content pipeline running
    BETA = "beta"                  # content-complete, bug-fixing + polish
    GOLD = "gold"                  # release candidate submitted to platform holder
    LAUNCH = "launch"              # live, marketing ramp, day-1 patch pipeline active
    POST_LIVE = "post_live"        # DLC / live-ops / live-service content


class PhaseStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    PASSED = "passed"              # gate cleared by QA
    WAIVED = "waived"              # executive override


class TeamRole(str, Enum):
    EXECUTIVE_PRODUCER = "executive_producer"
    CREATIVE_DIRECTOR = "creative_director"
    GAME_DIRECTOR = "game_director"
    NARRATIVE_DIRECTOR = "narrative_director"
    ART_DIRECTOR = "art_director"
    TECHNICAL_DIRECTOR = "technical_director"
    LEAD_ENGINEER = "lead_engineer"
    AUDIO_DIRECTOR = "audio_director"
    QA_LEAD = "qa_lead"
    MARKETING_LEAD = "marketing_lead"


@dataclass
class TeamMember:
    """A studio role, backed by a local Ollama model."""
    role: TeamRole
    name: str = ""                # display name (defaults to role title)
    ollama_model: str = "gemma4:12b"
    specialization: str = ""       # system-prompt specialization for the role
    deliverables: List[str] = field(default_factory=list)  # artifacts this role owns

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.role.value.replace("_", " ").title()


@dataclass
class Milestone:
    """One gate in the AAA production pipeline."""
    phase: Phase
    status: PhaseStatus = PhaseStatus.NOT_STARTED
    started_at: Optional[float] = None   # epoch
    completed_at: Optional[float] = None
    qa_score: float = 0.0               # 0-100, must clear threshold to pass gate
    qa_threshold: float = 70.0           # studio default; override per-project
    notes: str = ""
    artifacts: List[str] = field(default_factory=list)
    review_notes: str = ""               # filled by QA Lead pass

    def can_pass(self) -> bool:
        return self.status in (PhaseStatus.IN_PROGRESS, PhaseStatus.BLOCKED) \
            and self.qa_score >= self.qa_threshold


@dataclass
class BudgetLine:
    """One line item in the project budget (USD)."""
    category: str              # "team", "render_farm", "marketing", "engine_license", "mocap", etc.
    description: str
    est_cost_usd: float
    actual_cost_usd: float = 0.0
    notes: str = ""


@dataclass
class Project:
    """One AAA game (or film) in the studio portfolio."""
    id: str
    kind: str = "game"         # "game" | "film"
    title: str = ""
    brief: Optional[Any] = None  # GameBrief | FilmBrief
    team: List[TeamMember] = field(default_factory=list)
    milestones: Dict[Phase, Milestone] = field(default_factory=dict)
    budget: List[BudgetLine] = field(default_factory=list)
    target_release_q: str = ""   # e.g. "2027Q3"
    workdir: Optional[Path] = None
    manifest: Optional[ProjectManifest] = None
    risk_register: List[Dict[str, str]] = field(default_factory=list)
    post_live_plan: List[str] = field(default_factory=list)


@dataclass
class Portfolio:
    """The studio's slate of projects."""
    name: str = "Axiom Studios"
    projects: List[Project] = field(default_factory=list)
    studio_budget_total_usd: float = 0.0
    fiscal_year: str = ""

    def active_projects(self) -> List[Project]:
        """Projects that are in-progress (have at least one incomplete milestone)."""
        result = []
        for p in self.projects:
            if not p.milestones:
                continue
            # Active = not all milestones passed/waived yet
            has_incomplete = any(
                m.status not in (PhaseStatus.PASSED, PhaseStatus.WAIVED)
                for m in p.milestones.values()
            )
            has_passed = any(
                m.status in (PhaseStatus.PASSED, PhaseStatus.WAIVED)
                for m in p.milestones.values()
            )
            if has_incomplete or not has_passed:
                result.append(p)
        return result

    def released_projects(self) -> List[Project]:
        return [p for p in self.projects
                if p.milestones.get(Phase.LAUNCH) and
                p.milestones[Phase.LAUNCH].status == PhaseStatus.PASSED]


@dataclass
class ProjectManifest:
    kind: str            # "film" | "game"
    title: str
    workdir: Path
    quality: Quality
    stages: List[StageResult] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_duration_s: float = 0.0
    asset_provenance: List[Any] = field(default_factory=list)
    asset_validations: List[Any] = field(default_factory=list)
    rollback_source: Dict[str, Any] = field(default_factory=dict)

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
