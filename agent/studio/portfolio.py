"""Axiom Studio — Portfolio manager.

Tracks the studio's slate of projects, their phase, budget burn, and
release calendar. Provides the EP's at-a-glance view of the studio.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from agent.studio.types import (
    BudgetLine, Milestone, Phase, PhaseStatus, Portfolio, Project,
)


class PortfolioManager:
    """Manages the studio's portfolio of projects."""

    def __init__(self, portfolio: Optional[Portfolio] = None) -> None:
        self.portfolio = portfolio or Portfolio()

    def add_project(self, project: Project) -> None:
        self.portfolio.projects.append(project)

    def get(self, project_id: str) -> Optional[Project]:
        for p in self.portfolio.projects:
            if p.id == project_id:
                return p
        return None

    def active(self) -> List[Project]:
        return self.portfolio.active_projects()

    def released(self) -> List[Project]:
        return self.portfolio.released_projects()

    def release_calendar(self) -> List[Dict]:
        """Upcoming releases by quarter."""
        cal: List[Dict] = []
        for p in self.portfolio.projects:
            if not p.target_release_q:
                continue
            phase = p.milestones.get(Phase.LAUNCH)
            if phase and phase.status == PhaseStatus.PASSED:
                continue  # already shipped
            cal.append({
                "title": p.title,
                "target_q": p.target_release_q,
                "current_phase": self._current_phase(p).value if self._current_phase(p) else "—",
                "budget_total": self._budget_total(p),
                "budget_burned": self._budget_burned(p),
            })
        cal.sort(key=lambda x: x["target_q"])
        return cal

    def budget_summary(self) -> Dict:
        """Studio-level rollup."""
        total_est = 0.0
        total_actual = 0.0
        per_project: List[Dict] = []
        for p in self.portfolio.projects:
            est = self._budget_total(p)
            actual = self._budget_burned(p)
            total_est += est
            total_actual += actual
            per_project.append({
                "id": p.id, "title": p.title,
                "est": est, "actual": actual,
                "burn_pct": (actual / est * 100) if est > 0 else 0,
            })
        return {
            "studio_estimated": total_est,
            "studio_actual": total_actual,
            "studio_burn_pct": (total_actual / total_est * 100) if total_est > 0 else 0,
            "projects": per_project,
        }

    def save(self, path: Path) -> Path:
        """Serialize portfolio to JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self.portfolio.name,
            "fiscal_year": self.portfolio.fiscal_year,
            "projects": [
                {
                    "id": p.id, "kind": p.kind, "title": p.title,
                    "target_release_q": p.target_release_q,
                    "milestones": {
                        m.phase.value: {
                            "status": m.status.value,
                            "qa_score": m.qa_score,
                            "qa_threshold": m.qa_threshold,
                            "artifacts": m.artifacts,
                        } for m in p.milestones.values()
                    },
                    "budget": [bl.__dict__ for bl in p.budget],
                    "risk_register": p.risk_register,
                    "post_live_plan": p.post_live_plan,
                }
                for p in self.portfolio.projects
            ],
            "saved_at": int(time.time()),
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    @staticmethod
    def load(path: Path) -> "PortfolioManager":
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        portfolio = Portfolio(name=data.get("name", "Axiom Studios"),
                              fiscal_year=data.get("fiscal_year", ""))
        for pd in data.get("projects", []):
            project = Project(
                id=pd["id"], kind=pd.get("kind", "game"),
                title=pd.get("title", ""),
                target_release_q=pd.get("target_release_q", ""),
                budget=[BudgetLine(**bl) for bl in pd.get("budget", [])],
                risk_register=pd.get("risk_register", []),
                post_live_plan=pd.get("post_live_plan", []),
            )
            # Initialize all 8 milestones first, then override from saved data
            for phase in Phase:
                project.milestones[phase] = Milestone(phase=phase)
            for phase_val, md in pd.get("milestones", {}).items():
                phase = Phase(phase_val)
                m = project.milestones[phase]
                m.status = PhaseStatus(md.get("status", "not_started"))
                m.qa_score = md.get("qa_score", 0.0)
                m.qa_threshold = md.get("qa_threshold", 70.0)
                m.artifacts = md.get("artifacts", [])
            portfolio.projects.append(project)
        return PortfolioManager(portfolio)

    # ── internals ───────────────────────────────────────────────────

    def _current_phase(self, project: Project) -> Optional[Phase]:
        for phase in Phase:
            m = project.milestones.get(phase)
            if m and m.status not in (PhaseStatus.PASSED, PhaseStatus.WAIVED):
                return phase
        return None

    def _budget_total(self, project: Project) -> float:
        return sum(bl.est_cost_usd for bl in project.budget)

    def _budget_burned(self, project: Project) -> float:
        return sum(bl.actual_cost_usd for bl in project.budget)
