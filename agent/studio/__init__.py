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
    BudgetLine,
)

__all__ = [
    "StudioOrchestrator", "FilmBrief", "GameBrief",
    "StageResult", "ProjectManifest", "Quality", "Provider",
    "make_bundle", "make_bundle_dir", "build_index",
    "AAAStudio", "Team", "default_team", "ROLE_PRESETS",
    "Pipeline", "PHASE_BRIEFS", "PortfolioManager",
    "estimate", "compare_tiers", "BudgetScenario",
    "Phase", "PhaseStatus", "Milestone", "Project", "Portfolio",
    "TeamMember", "TeamRole", "BudgetLine",
]
