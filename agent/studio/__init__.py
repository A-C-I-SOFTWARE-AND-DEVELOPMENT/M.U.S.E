"""Axiom Studio — AAA game + theatrical film production orchestrator.

Public API:
    from agent.studio import StudioOrchestrator, FilmBrief, GameBrief

    orch = StudioOrchestrator()
    result = orch.produce_film(FilmBrief(title="...", logline="...", runtime_min=110))
    result = orch.produce_game(GameBrief(title="...", genre="...", target="PC/PS5"))

Each pipeline stage runs through a registered adapter. Adapters fall back to
stub manifests when API keys are missing, so the full DAG executes end-to-end
without spending money — then graduates to real generation as keys are wired.
"""
from agent.studio.orchestrator import StudioOrchestrator
from agent.studio.bundle import make_bundle, make_bundle_dir, build_index
from agent.studio.studio import AAAStudio
from agent.studio.team import Team, default_team, ROLE_PRESETS
from agent.studio.pipeline import Pipeline, PHASE_BRIEFS
from agent.studio.portfolio import PortfolioManager
from agent.studio.budget import estimate, compare_tiers, BudgetScenario
from agent.studio.types import (
    FilmBrief, GameBrief, StageResult, ProjectManifest, Quality, Provider,
    Phase, PhaseStatus, Milestone, Project, Portfolio, TeamMember, TeamRole,
    BudgetLine, BuildGateResult, GameBuildManifest, GameProductionSpec,
    VerticalSliceSpec,
)
from agent.studio.game_foundry import GameFoundry, PRODUCTION_LANES
from agent.studio.prompt_spec import (
    parse_vertical_slice_prompt, to_game_production_spec, write_vertical_slice_spec,
)
from agent.studio.ue5_vertical_slice import generate_ue5_vertical_slice
from agent.studio.lingbot_previs import (
    CameraKeyframe, PrevisRequest, PrevisResult, run_previs,
    write_camera_conditioning,
)
from agent.studio.stereo import (
    StereoCamera, StereoCameraRig, StereoFrameMetrics, StereoQcIssue,
    StereoQcLimits, StereoQcResult, StereoShot, evaluate_stereo_qc,
)
from agent.studio.render_manifest import RenderFrameRecord, RenderManifest, RenderValidation
from agent.studio.cinema import CinemaPackage, CinemaPackager
from agent.studio.blueprints import (
    OpenWorldRpgBlueprint, CapabilityDomain, RoadmapPhase, DependencyEdge,
    load_open_world_rpg_blueprint,
)
from agent.studio.aaa_pipeline import (
    AAAPipeline, AAAPipelineBrief, AAAPipelineResult, run_creature_hunting_pipeline,
)
from agent.studio.quality_profiles import (
    FidelityTier, QualityProfile, load_quality_profile, QUALITY_PROFILES,
    AAA_BENCHMARK_PROFILE, HIGH_FIDELITY_PROFILE,
)
from agent.studio.manifests import (
    AssetManifest, AssetManifestEntry, WorldManifest, PipelineManifest, decompose_brief,
)
from agent.studio.acceptance import AcceptanceReport, evaluate_acceptance
from agent.studio.checkpoints import PipelineCheckpoint, PipelineStage
from agent.studio.gates import CostGate, HardwareGate, LicenseGate, gates_passed
from agent.studio.provider_config import ProviderConfig, build_provider_config
from agent.studio.blender_contract import BlenderContract, build_creature_blender_contract
from agent.studio.creature_specs import CreatureManifest, build_creature_manifests
from agent.studio.world_specs import WorldSystemsManifest, build_world_systems
from agent.studio.ue5_generator import generate_ue5_project

__all__ = [
    "StudioOrchestrator", "FilmBrief", "GameBrief",
    "StageResult", "ProjectManifest", "Quality", "Provider",
    "make_bundle", "make_bundle_dir", "build_index",
    "AAAStudio", "Team", "default_team", "ROLE_PRESETS",
    "Pipeline", "PHASE_BRIEFS", "PortfolioManager",
    "estimate", "compare_tiers", "BudgetScenario",
    "Phase", "PhaseStatus", "Milestone", "Project", "Portfolio",
    "TeamMember", "TeamRole", "BudgetLine",
    "BuildGateResult", "GameBuildManifest", "GameProductionSpec",
    "VerticalSliceSpec", "GameFoundry", "PRODUCTION_LANES",
    "parse_vertical_slice_prompt", "to_game_production_spec",
    "write_vertical_slice_spec",
    "generate_ue5_vertical_slice",
    "CameraKeyframe", "PrevisRequest", "PrevisResult", "run_previs",
    "write_camera_conditioning",
    "StereoCamera", "StereoCameraRig", "StereoFrameMetrics", "StereoQcIssue",
    "StereoQcLimits", "StereoQcResult", "StereoShot", "evaluate_stereo_qc",
    "RenderFrameRecord", "RenderManifest", "RenderValidation",
    "CinemaPackage", "CinemaPackager",
    "OpenWorldRpgBlueprint", "CapabilityDomain", "RoadmapPhase", "DependencyEdge",
    "load_open_world_rpg_blueprint",
    "AAAPipeline", "AAAPipelineBrief", "AAAPipelineResult", "run_creature_hunting_pipeline",
    "FidelityTier", "QualityProfile", "load_quality_profile", "QUALITY_PROFILES",
    "AAA_BENCHMARK_PROFILE", "HIGH_FIDELITY_PROFILE",
    "AssetManifest", "AssetManifestEntry", "WorldManifest", "PipelineManifest", "decompose_brief",
    "AcceptanceReport", "evaluate_acceptance",
    "PipelineCheckpoint", "PipelineStage",
    "CostGate", "HardwareGate", "LicenseGate", "gates_passed",
    "ProviderConfig", "build_provider_config",
    "BlenderContract", "build_creature_blender_contract",
    "CreatureManifest", "build_creature_manifests",
    "WorldSystemsManifest", "build_world_systems",
    "generate_ue5_project",
]
