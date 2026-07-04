"""Axiom Studio — top-level AAA Studio facade.

Ties together team, pipeline, portfolio, and budget into one object.

Usage:
    from agent.studio import AAAStudio, GameBrief, Quality

    studio = AAAStudio()
    project = studio.new_game_project(GameBrief(
        title="Hollowmark", genre="action-rpg", target="PC/PS5",
    ))
    studio.run_phase(project.id)            # concept doc from Creative Director
    studio.qa_review(project.id)            # QA Lead scores the gate
    studio.run_phase(project.id)            # next phase (prototype)
    studio.bundle(project.id)              # zip everything produced so far
    studio.portfolio_status()               # EP's portfolio view
    studio.budget_comparison(project.id)    # free vs indie vs AAA
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional

from agent.studio.budget import BudgetScenario, compare_tiers, estimate
from agent.studio.bundle import make_bundle
from agent.studio.orchestrator import StudioOrchestrator
from agent.studio.pipeline import Pipeline, PHASE_BRIEFS
from agent.studio.portfolio import PortfolioManager
from agent.studio.team import Team, default_team
from agent.studio.types import (
    FilmBrief, GameBrief, Milestone, Phase, PhaseStatus, Portfolio, Project,
    Quality, TeamMember,
)


class AAAStudio:
    """The full AAA game studio, in one object."""

    def __init__(self, root: Optional[Path] = None,
                 team: Optional[Team] = None,
                 portfolio: Optional[Portfolio] = None) -> None:
        self.root = Path(root or Path.cwd() / "studio_output")
        self.root.mkdir(parents=True, exist_ok=True)
        self.team = team or Team()
        self.portfolio_mgr = PortfolioManager(portfolio or Portfolio(name="Axiom Studios"))
        self.orchestrator = StudioOrchestrator(root=self.root)

    # ── project factory ─────────────────────────────────────────────

    def new_game_project(self, brief: GameBrief,
                         target_release_q: str = "") -> Project:
        slug = "".join(c if c.isalnum() else "_" for c in brief.title.lower()).strip("_")
        pid = f"{slug}_{int(time.time())}"
        wd = self.root / "projects" / pid
        wd.mkdir(parents=True, exist_ok=True)
        project = Project(
            id=pid, kind="game", title=brief.title, brief=brief,
            team=list(self.team.members.values()),
            target_release_q=target_release_q, workdir=wd,
        )
        # Initialize all 8 milestones so portfolio_status sees the project
        for phase in Phase:
            project.milestones[phase] = Milestone(phase=phase)
        self.portfolio_mgr.add_project(project)
        return project

    def new_film_project(self, brief: FilmBrief,
                         target_release_q: str = "") -> Project:
        slug = "".join(c if c.isalnum() else "_" for c in brief.title.lower()).strip("_")
        pid = f"{slug}_{int(time.time())}"
        wd = self.root / "projects" / pid
        wd.mkdir(parents=True, exist_ok=True)
        project = Project(
            id=pid, kind="film", title=brief.title, brief=brief,
            team=list(self.team.members.values()),
            target_release_q=target_release_q, workdir=wd,
        )
        for phase in Phase:
            project.milestones[phase] = Milestone(phase=phase)
        self.portfolio_mgr.add_project(project)
        return project

    # ── pipeline operations ─────────────────────────────────────────

    def _pipeline(self, project_id: str) -> Pipeline:
        project = self.portfolio_mgr.get(project_id)
        if project is None:
            raise KeyError(f"unknown project: {project_id}")
        # Ensure all 8 milestones exist (Pipeline does this but we need
        # them present for portfolio_status before the pipeline runs)
        for phase in Phase:
            if phase not in project.milestones:
                project.milestones[phase] = Milestone(phase=phase)
        return Pipeline(project, self.team, root=self.root)

    def run_phase(self, project_id: str,
                  phase: Optional[Phase] = None,
                  extra_prompt: str = "") -> Dict:
        """Run the current (or specified) phase's deliverable."""
        return self._pipeline(project_id).run_phase(phase, extra_prompt)

    def qa_review(self, project_id: str,
                  phase: Optional[Phase] = None,
                  force_score: Optional[float] = None) -> Dict:
        """QA Lead reviews and scores the phase."""
        return self._pipeline(project_id).qa_review(phase, force_score)

    def waive_gate(self, project_id: str, phase: Phase, reason: str) -> Dict:
        """EP override to waive a blocked gate."""
        return self._pipeline(project_id).waive(phase, reason)

    def advance(self, project_id: str, force_score: float = 80.0) -> Dict:
        """Convenience: run current phase + auto-pass QA with force_score."""
        run = self.run_phase(project_id)
        qa = self.qa_review(project_id, force_score=force_score)
        return {"phase_run": run, "qa_review": qa}

    # ── asset production ────────────────────────────────────────────

    def produce(self, project_id: str) -> Dict:
        """Run the full asset production pipeline (GDD → concept art → ... → bundle).

        Delegates to StudioOrchestrator.produce_game or produce_film based
        on project kind. Returns the manifest dict.
        """
        project = self.portfolio_mgr.get(project_id)
        if project is None:
            raise KeyError(f"unknown project: {project_id}")
        if project.brief is None:
            # brief is not serialized by PortfolioManager.save()/load(), so a
            # project reloaded from disk has brief=None. Fail with an actionable
            # message instead of an opaque AttributeError deep in produce_*().
            raise RuntimeError(
                f"project {project_id} has no brief — the brief is not persisted "
                "across save/load; recreate the project via new_game_project / "
                "new_film_project before calling produce()."
            )
        if project.kind == "game":
            manifest = self.orchestrator.produce_game(project.brief)
        else:
            manifest = self.orchestrator.produce_film(project.brief)
        project.manifest = manifest
        return {
            "project_id": project_id,
            "stages": len(manifest.stages),
            "cost_usd": manifest.total_cost_usd,
            "wall_s": manifest.total_duration_s,
            "workdir": str(manifest.workdir),
        }

    def bundle(self, project_id: str) -> Path:
        """Zip all artifacts produced so far into a single bundle."""
        project = self.portfolio_mgr.get(project_id)
        if project is None:
            raise KeyError(f"unknown project: {project_id}")
        if project.manifest is None:
            raise RuntimeError(f"project {project_id} has no manifest — call produce() first")
        return make_bundle(project.manifest)

    # ── portfolio / budget views ────────────────────────────────────

    def portfolio_status(self) -> Dict:
        return {
            "studio_name": self.portfolio_mgr.portfolio.name,
            "total_projects": len(self.portfolio_mgr.portfolio.projects),
            "active": len(self.portfolio_mgr.active()),
            "released": len(self.portfolio_mgr.released()),
            "release_calendar": self.portfolio_mgr.release_calendar(),
            "budget": self.portfolio_mgr.budget_summary(),
        }

    def project_status(self, project_id: str) -> Dict:
        return self._pipeline(project_id).status()

    def budget_comparison(self, project_id: str,
                          stage_counts: Optional[Dict[str, int]] = None) -> List[Dict]:
        """Compare free vs indie vs AAA budget for this project."""
        project = self.portfolio_mgr.get(project_id)
        if project is None:
            raise KeyError(f"unknown project: {project_id}")
        if stage_counts is None:
            # Default: one of each LLM stage + 10 concept art + 5 voice
            stage_counts = {
                "script": 1, "gdd": 1, "world_bible": 1,
                "dialogue_text": 3, "gameplay_code": 1, "shot_list": 1,
                "concept_art": 10, "voice": 5, "music": 5, "sfx": 10,
                "video": 8, "mesh3d": 5, "world": 4, "engine_project": 1,
            }
        return [s.to_dict() for s in compare_tiers(project, stage_counts)]

    # ── roster ──────────────────────────────────────────────────────

    def roster(self) -> List[Dict]:
        return self.team.roster()
