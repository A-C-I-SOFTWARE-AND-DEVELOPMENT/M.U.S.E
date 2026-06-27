"""Axiom Studio — Budget model.

Three scenarios for any project:
  - FREE     : all-local Ollama + Pollinations + edge-tts, $0 API spend
  - INDIE    : + paid image (Flux Pro) + paid voice (ElevenLabs), ~$500/project
  - AAA      : + paid video (Sora2/Veo3) + 3D mesh + mocap, ~$50k-$500k/project

Used by the EP to model ROI and by the pipeline to decide which adapter
tier to activate for each stage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from agent.studio.types import BudgetLine, Project


# Per-stage unit costs (USD) by tier. "free" is always $0.
STAGE_COSTS: Dict[str, Dict[str, float]] = {
    # LLM stages — free on local Ollama
    "script":           {"free": 0.0, "indie": 0.0, "aaa": 0.50},
    "gdd":              {"free": 0.0, "indie": 0.0, "aaa": 1.00},
    "world_bible":      {"free": 0.0, "indie": 0.0, "aaa": 1.00},
    "dialogue_text":    {"free": 0.0, "indie": 0.0, "aaa": 0.50},
    "gameplay_code":    {"free": 0.0, "indie": 0.0, "aaa": 2.00},
    "shot_list":        {"free": 0.0, "indie": 0.0, "aaa": 1.00},
    # Image stages — free via Pollinations, paid via Flux Pro
    "concept_art":      {"free": 0.0, "indie": 0.05, "aaa": 0.10},
    # Voice — free via edge-tts, paid via ElevenLabs
    "voice":            {"free": 0.0, "indie": 0.30, "aaa": 1.00},
    # Music — stubbed at free, Suno at indie, orchestral session at AAA
    "music":            {"free": 0.0, "indie": 0.50, "aaa": 5000.0},
    # SFX — stubbed free, ElevenLabs SFX indie, foley session AAA
    "sfx":              {"free": 0.0, "indie": 0.10, "aaa": 2000.0},
    # Video — stubbed free, Kling indie, Sora2/Veo3 AAA
    "video":            {"free": 0.0, "indie": 5.00, "aaa": 50.0},
    # 3D mesh — stubbed free, Meshy indie, Hunyuan3D + cleanup AAA
    "mesh3d":           {"free": 0.0, "indie": 1.00, "aaa": 50.0},
    # Interactive world — stubbed (Genie3/DreamX not public yet)
    "world":            {"free": 0.0, "indie": 0.0, "aaa": 0.0},
    # Engine project scaffold — always free
    "engine_project":   {"free": 0.0, "indie": 0.0, "aaa": 0.0},
}

# Fixed studio overhead per project (non-generation spend)
STUDIO_OVERHEAD = {
    "free":  {"team": 0.0, "render_farm": 0.0, "engine_license": 0.0,
              "marketing": 0.0, "mocap": 0.0, "qa": 0.0, "cert": 0.0},
    "indie": {"team": 0.0, "render_farm": 0.0, "engine_license": 0.0,
              "marketing": 500.0, "mocap": 0.0, "qa": 200.0, "cert": 0.0},
    "aaa":   {"team": 2_000_000.0, "render_farm": 100_000.0,
              "engine_license": 50_000.0, "marketing": 5_000_000.0,
              "mocap": 200_000.0, "qa": 300_000.0, "cert": 50_000.0},
}


@dataclass
class BudgetScenario:
    tier: str  # "free" | "indie" | "aaa"
    project_title: str
    line_items: List[BudgetLine] = field(default_factory=list)
    total_est: float = 0.0

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "project": self.project_title,
            "total_est": self.total_est,
            "lines": [
                {"category": l.category, "description": l.description,
                 "est": l.est_cost_usd}
                for l in self.line_items
            ],
        }


def estimate(project: Project, stage_counts: Dict[str, int],
             tier: str = "free") -> BudgetScenario:
    """Estimate the budget for a project at a given tier.

    Args:
        project: The project to estimate
        stage_counts: How many of each stage will run
                      (e.g. {"concept_art": 20, "voice": 3, ...})
        tier: "free" | "indie" | "aaa"
    """
    if tier not in STAGE_COSTS.get("concept_art", {}):
        raise ValueError(f"unknown tier: {tier}")

    lines: List[BudgetLine] = []

    # Per-stage variable costs
    for stage, count in stage_counts.items():
        if stage not in STAGE_COSTS:
            continue
        unit = STAGE_COSTS[stage].get(tier, 0.0)
        if unit == 0.0:
            continue
        lines.append(BudgetLine(
            category="generation",
            description=f"{stage} × {count} ({tier} tier)",
            est_cost_usd=unit * count,
        ))

    # Fixed studio overhead
    overhead = STUDIO_OVERHEAD.get(tier, {})
    for cat, amount in overhead.items():
        if amount > 0:
            lines.append(BudgetLine(
                category=cat,
                description=f"{cat} overhead ({tier})",
                est_cost_usd=amount,
            ))

    total = sum(l.est_cost_usd for l in lines)
    return BudgetScenario(
        tier=tier, project_title=project.title,
        line_items=lines, total_est=total,
    )


def compare_tiers(project: Project,
                  stage_counts: Dict[str, int]) -> List[BudgetScenario]:
    """Produce all three tier scenarios for comparison."""
    return [estimate(project, stage_counts, tier) for tier in ("free", "indie", "aaa")]
