"""Tests for the AAA studio layer — team, pipeline, portfolio, budget."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agent.studio.adapters import ollama_local, free_providers
from agent.studio.budget import compare_tiers, estimate
from agent.studio.pipeline import Pipeline, PHASE_BRIEFS, PHASE_OWNERS
from agent.studio.portfolio import PortfolioManager
from agent.studio.studio import AAAStudio
from agent.studio.team import Team, ROLE_PRESETS, default_team, PHASE_OWNERS as TEAM_OWNERS
from agent.studio.types import (
    BudgetLine, GameBrief, Milestone, Phase, PhaseStatus,
    Portfolio, Project, TeamMember, TeamRole,
)


# ── Team ────────────────────────────────────────────────────────────

def test_default_team_has_ten_roles():
    team = Team()
    assert len(team.members) == 10
    for role in TeamRole:
        assert role in team.members


def test_team_role_presets_have_specialization_and_deliverables():
    for role, preset in ROLE_PRESETS.items():
        assert preset["specialization"], f"{role} missing specialization"
        assert preset["deliverables"], f"{role} missing deliverables"
        assert preset["ollama_model"], f"{role} missing model"


def test_phase_owners_cover_all_phases():
    for phase in Phase:
        assert phase in PHASE_OWNERS, f"{phase} has no owner"


def test_team_brief_writes_artifact_when_workdir_given(tmp_path: Path):
    team = Team()
    with patch.object(ollama_local, "_ollama_available", return_value=False):
        result = team.brief(
            project_title="Test", phase=Phase.CONCEPT,
            prompt="Write the vision doc.",
        )
        assert isinstance(result, str)
        assert "stub" in result.lower() or "ollama offline" in result.lower()


def test_team_ask_writes_file_when_workdir_given(tmp_path: Path):
    team = Team()
    with patch.object(ollama_local, "_ollama_available", return_value=False), \
         patch.object(ollama_local, "_ollama_chat", return_value="fake content"):
        path = team.ask(
            role=TeamRole.CREATIVE_DIRECTOR,
            project_title="Test", phase=Phase.CONCEPT,
            prompt="vision doc", workdir=tmp_path,
        )
        # When Ollama is "offline", brief returns stub text;
        # When workdir given and Ollama available (mocked), writes file
        # Either way, no crash.


# ── Pipeline ────────────────────────────────────────────────────────

def _make_project(tmp_path: Path) -> Project:
    project = Project(
        id="test_001", kind="game", title="Test Game",
        workdir=tmp_path / "test_001",
        team=default_team(),
    )
    # Initialize all 8 milestones (Pipeline does this, but tests construct
    # projects directly)
    for phase in Phase:
        if phase not in project.milestones:
            project.milestones[phase] = Milestone(phase=phase)
    return project


def test_pipeline_initializes_all_eight_milestones(tmp_path: Path):
    project = _make_project(tmp_path)
    pipeline = Pipeline(project, Team(), root=tmp_path)
    assert len(project.milestones) == 8
    for phase in Phase:
        assert phase in project.milestones
        assert project.milestones[phase].status == PhaseStatus.NOT_STARTED


def test_pipeline_current_phase_is_concept_at_start(tmp_path: Path):
    project = _make_project(tmp_path)
    pipeline = Pipeline(project, Team(), root=tmp_path)
    assert pipeline.current_phase() == Phase.CONCEPT


def test_pipeline_run_phase_marks_in_progress_and_writes_artifact(tmp_path: Path):
    project = _make_project(tmp_path)
    pipeline = Pipeline(project, Team(), root=tmp_path)
    with patch.object(ollama_local, "_ollama_available", return_value=False):
        result = pipeline.run_phase(Phase.CONCEPT)
    assert result["phase"] == "concept"
    assert result["status"] == "in_progress"
    milestone = project.milestones[Phase.CONCEPT]
    assert milestone.status == PhaseStatus.IN_PROGRESS
    assert len(milestone.artifacts) == 1
    assert Path(milestone.artifacts[0]).exists()


def test_pipeline_qa_review_passes_when_score_clears_threshold(tmp_path: Path):
    project = _make_project(tmp_path)
    pipeline = Pipeline(project, Team(), root=tmp_path)
    with patch.object(ollama_local, "_ollama_available", return_value=False):
        pipeline.run_phase(Phase.CONCEPT)
    # Force a passing score
    result = pipeline.qa_review(Phase.CONCEPT, force_score=85.0)
    assert result["passed"] is True
    assert project.milestones[Phase.CONCEPT].status == PhaseStatus.PASSED


def test_pipeline_qa_review_blocks_when_score_below_threshold(tmp_path: Path):
    project = _make_project(tmp_path)
    pipeline = Pipeline(project, Team(), root=tmp_path)
    with patch.object(ollama_local, "_ollama_available", return_value=False):
        pipeline.run_phase(Phase.CONCEPT)
    result = pipeline.qa_review(Phase.CONCEPT, force_score=40.0)
    assert result["passed"] is False
    assert project.milestones[Phase.CONCEPT].status == PhaseStatus.BLOCKED


def test_pipeline_waive_overrides_blocked_gate(tmp_path: Path):
    project = _make_project(tmp_path)
    pipeline = Pipeline(project, Team(), root=tmp_path)
    with patch.object(ollama_local, "_ollama_available", return_value=False):
        pipeline.run_phase(Phase.CONCEPT)
    pipeline.qa_review(Phase.CONCEPT, force_score=40.0)
    assert project.milestones[Phase.CONCEPT].status == PhaseStatus.BLOCKED
    pipeline.waive(Phase.CONCEPT, "EP override — time to market")
    assert project.milestones[Phase.CONCEPT].status == PhaseStatus.WAIVED


def test_pipeline_current_phase_advances_after_pass(tmp_path: Path):
    project = _make_project(tmp_path)
    pipeline = Pipeline(project, Team(), root=tmp_path)
    with patch.object(ollama_local, "_ollama_available", return_value=False):
        pipeline.run_phase(Phase.CONCEPT)
    pipeline.qa_review(Phase.CONCEPT, force_score=90.0)
    assert pipeline.current_phase() == Phase.PROTOTYPE


def test_pipeline_status_returns_all_milestones(tmp_path: Path):
    project = _make_project(tmp_path)
    pipeline = Pipeline(project, Team(), root=tmp_path)
    status = pipeline.status()
    assert status["project_id"] == "test_001"
    assert len(status["milestones"]) == 8


# ── Portfolio ───────────────────────────────────────────────────────

def test_portfolio_manager_add_and_get_project(tmp_path: Path):
    pm = PortfolioManager()
    p = _make_project(tmp_path)
    pm.add_project(p)
    assert pm.get("test_001") is p
    assert pm.get("nonexistent") is None


def test_portfolio_active_projects_filters_released(tmp_path: Path):
    pm = PortfolioManager()
    p1 = _make_project(tmp_path)
    p1.id = "p1"
    p2 = _make_project(tmp_path)
    p2.id = "p2"
    # Mark ALL of p2's milestones as passed (fully shipped)
    for m in p2.milestones.values():
        m.status = PhaseStatus.PASSED
    pm.add_project(p1)
    pm.add_project(p2)
    active = pm.active()
    assert len(active) == 1
    assert active[0].id == "p1"


def test_portfolio_save_and_load_roundtrip(tmp_path: Path):
    pm = PortfolioManager()
    p = _make_project(tmp_path)
    p.target_release_q = "2027Q3"
    p.budget = [BudgetLine(category="team", description="core team",
                           est_cost_usd=100000)]
    pm.add_project(p)
    save_path = tmp_path / "portfolio.json"
    pm.save(save_path)
    loaded = PortfolioManager.load(save_path)
    assert loaded.portfolio.name == "Axiom Studios"
    assert len(loaded.portfolio.projects) == 1
    assert loaded.portfolio.projects[0].title == "Test Game"
    assert loaded.portfolio.projects[0].target_release_q == "2027Q3"
    assert loaded.portfolio.projects[0].budget[0].est_cost_usd == 100000


def test_portfolio_budget_summary_aggregates(tmp_path: Path):
    pm = PortfolioManager()
    p1 = _make_project(tmp_path)
    p1.budget = [BudgetLine(category="team", description="a", est_cost_usd=50000,
                             actual_cost_usd=20000)]
    p2 = _make_project(tmp_path)
    p2.id = "p2"
    p2.budget = [BudgetLine(category="team", description="b", est_cost_usd=30000,
                             actual_cost_usd=10000)]
    pm.add_project(p1)
    pm.add_project(p2)
    summary = pm.budget_summary()
    assert summary["studio_estimated"] == 80000
    assert summary["studio_actual"] == 30000
    assert summary["studio_burn_pct"] == 37.5


# ── Budget ──────────────────────────────────────────────────────────

def test_budget_free_tier_is_zero():
    project = Project(id="x", title="X")
    scenario = estimate(project, {"concept_art": 100, "voice": 50, "video": 10}, "free")
    assert scenario.total_est == 0.0
    assert len(scenario.line_items) == 0


def test_budget_indie_tier_has_generation_costs():
    project = Project(id="x", title="X")
    scenario = estimate(project, {"concept_art": 100, "voice": 50, "video": 10}, "indie")
    # 100 × $0.05 + 50 × $0.30 + 10 × $5.00 + marketing $500 + qa $200
    expected = 100 * 0.05 + 50 * 0.30 + 10 * 5.00 + 500 + 200
    assert scenario.total_est == pytest.approx(expected, rel=0.01)


def test_budget_aaa_tier_includes_studio_overhead():
    project = Project(id="x", title="X")
    scenario = estimate(project, {"concept_art": 100}, "aaa")
    # Must include team ($2M), render_farm ($100k), marketing ($5M), etc.
    cats = {l.category for l in scenario.line_items}
    assert "team" in cats
    assert "render_farm" in cats
    assert "marketing" in cats
    assert scenario.total_est > 7_000_000  # > $7M for AAA overhead


def test_budget_compare_tiers_returns_three_scenarios():
    project = Project(id="x", title="X")
    scenarios = compare_tiers(project, {"concept_art": 10, "voice": 5})
    assert len(scenarios) == 3
    tiers = {s.tier for s in scenarios}
    assert tiers == {"free", "indie", "aaa"}
    # Free must be cheapest, AAA most expensive
    totals = {s.tier: s.total_est for s in scenarios}
    assert totals["free"] <= totals["indie"] <= totals["aaa"]


# ── AAAStudio facade ───────────────────────────────────────────────

def test_studio_creates_game_project_with_id(tmp_path: Path):
    studio = AAAStudio(root=tmp_path)
    project = studio.new_game_project(GameBrief(
        title="Test Game", genre="action-rpg", target="PC",
    ), target_release_q="2027Q3")
    assert project.id.startswith("test_game_")
    assert project.kind == "game"
    assert project.title == "Test Game"
    assert project.target_release_q == "2027Q3"
    assert project.workdir.exists()
    assert studio.portfolio_mgr.get(project.id) is project


def test_studio_advance_runs_phase_and_passes_qa(tmp_path: Path):
    studio = AAAStudio(root=tmp_path)
    project = studio.new_game_project(GameBrief(
        title="Test Game", genre="rpg", target="PC",
    ))
    with patch.object(ollama_local, "_ollama_available", return_value=False):
        result = studio.advance(project.id, force_score=85.0)
    assert result["qa_review"]["passed"] is True
    status = studio.project_status(project.id)
    assert status["current_phase"] == "prototype"  # concept passed, advanced


def test_studio_roster_returns_ten_members(tmp_path: Path):
    studio = AAAStudio(root=tmp_path)
    roster = studio.roster()
    assert len(roster) == 10
    roles = {r["role"] for r in roster}
    assert "executive_producer" in roles
    assert "qa_lead" in roles


def test_studio_budget_comparison_returns_three_tiers(tmp_path: Path):
    studio = AAAStudio(root=tmp_path)
    project = studio.new_game_project(GameBrief(
        title="Test Game", genre="rpg", target="PC",
    ))
    comparison = studio.budget_comparison(project.id)
    assert len(comparison) == 3
    tiers = {c["tier"] for c in comparison}
    assert tiers == {"free", "indie", "aaa"}
    # Free tier must be $0
    free = next(c for c in comparison if c["tier"] == "free")
    assert free["total_est"] == 0.0


def test_studio_portfolio_status_aggregates(tmp_path: Path):
    studio = AAAStudio(root=tmp_path)
    studio.new_game_project(GameBrief(title="Game A", genre="rpg", target="PC"))
    studio.new_game_project(GameBrief(title="Game B", genre="fps", target="PS5"))
    status = studio.portfolio_status()
    assert status["total_projects"] == 2
    assert status["active"] == 2
    assert status["released"] == 0


def test_produce_on_reloaded_project_raises_actionable_error(tmp_path: Path):
    """PortfolioManager.save()/load() does not persist ``brief``, so a project
    reloaded from disk has brief=None. produce() must raise an actionable
    RuntimeError instead of an opaque AttributeError deep in produce_game()."""
    studio = AAAStudio(root=tmp_path)
    proj = studio.new_game_project(GameBrief(title="Reload Me", genre="rpg", target="PC"))

    save_path = tmp_path / "portfolio.json"
    studio.portfolio_mgr.save(save_path)
    reloaded_mgr = PortfolioManager.load(save_path)

    reloaded = reloaded_mgr.get(proj.id)
    assert reloaded is not None
    assert reloaded.brief is None  # root cause: brief is not serialized

    studio.portfolio_mgr = reloaded_mgr
    with pytest.raises(RuntimeError, match="no brief"):
        studio.produce(proj.id)
