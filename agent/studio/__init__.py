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
from agent.studio.types import (
    FilmBrief, GameBrief, StageResult, ProjectManifest,
    Quality, Provider,
)

__all__ = [
    "StudioOrchestrator", "FilmBrief", "GameBrief",
    "StageResult", "ProjectManifest", "Quality", "Provider",
]
