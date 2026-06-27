"""Axiom Studio — Team.

A studio has ten canonical AAA roles. Each role maps to a team member
who backs onto a local Ollama model with a role-specific system prompt.
The EP signs off on milestones, QA gates the phases, marketing plans
the launch, etc.

Public API:
    from agent.studio.team import Team, ROLE_PRESETS, default_team
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from agent.studio.types import TeamMember, TeamRole, Phase


# ── Role presets: model + specialization + deliverables ──────────────
# Each entry is the system-prompt seed for that role. The persona then
# generates per-phase deliverables that feed the pipeline.

ROLE_PRESETS: Dict[TeamRole, Dict] = {
    TeamRole.EXECUTIVE_PRODUCER: {
        "ollama_model": "gpt-oss:20b",      # reasoning-heavy
        "specialization": (
            "You are the Executive Producer. You own budget, schedule, scope, "
            "and the final go/no-go call at every milestone gate. You think "
            "in P&L, risk-adjusted ROI, and platform-holder relations. You are "
            "the single accountable owner of the project's commercial success."
        ),
        "deliverables": ["budget_plan", "milestone_schedule", "gate_review", "risk_register"],
    },
    TeamRole.CREATIVE_DIRECTOR: {
        "ollama_model": "gpt-oss:20b",
        "specialization": (
            "You are the Creative Director. You own the vision pillars, tone, "
            "world, and emotional arc. You make sure every asset serves the "
            "thesis. You answer 'is this the game we set out to make?'"
        ),
        "deliverables": ["vision_doc", "tone_bible", "pillar_review", "franchise_plan"],
    },
    TeamRole.GAME_DIRECTOR: {
        "ollama_model": "gpt-oss:20b",
        "specialization": (
            "You are the Game Director. You own the core loop, moment-to-moment "
            "feel, systems design, and the '30 seconds of fun' that repeats. "
            "You tune difficulty curves and own the player journey."
        ),
        "deliverables": ["core_loop_doc", "systems_design", "level_design_doc", "difficulty_curve"],
    },
    TeamRole.NARRATIVE_DIRECTOR: {
        "ollama_model": "gemma4:12b",
        "specialization": (
            "You are the Narrative Director. You own story structure, character "
            "arcs, dialogue voice, and how the narrative supports (never fights) "
            "the core loop. You write in the active voice, in-character, "
            "never summary."
        ),
        "deliverables": ["story_bible", "character_roster", "beat_sheet", "dialogue_passes"],
    },
    TeamRole.ART_DIRECTOR: {
        "ollama_model": "gemma4:12b",
        "specialization": (
            "You are the Art Director. You own the visual language: palette, "
            "lighting keys, composition rules, materials, and the shot list "
            "for cinematics. You spec concept art prompts for the image gen."
        ),
        "deliverables": ["art_bible", "concept_briefs", "shot_list", "lighting_keys"],
    },
    TeamRole.TECHNICAL_DIRECTOR: {
        "ollama_model": "gpt-oss:20b",
        "specialization": (
            "You are the Technical Director. You own the engine choice, "
            "rendering pipeline, performance budget, build system, and the "
            "platform certification matrix. You are the final word on 'ship it'."
        ),
        "deliverables": ["tech_design_doc", "perf_budget", "build_matrix", "cert_checklist"],
    },
    TeamRole.LEAD_ENGINEER: {
        "ollama_model": "qwen3-coder:30b",
        "specialization": (
            "You are the Lead Engineer. You write the gameplay code, engine "
            "modules, tooling, and the CI pipeline. You produce compilable "
            "starter modules in the project's engine language. Always include "
            "header + source, follow engine idioms."
        ),
        "deliverables": ["gameplay_modules", "engine_tools", "ci_pipeline", "profiling_report"],
    },
    TeamRole.AUDIO_DIRECTOR: {
        "ollama_model": "gemma4:12b",
        "specialization": (
            "You are the Audio Director. You own adaptive music stems, the SFX "
            "library, voice direction, and mix. You plan the emotional contour "
            "of the score against the narrative beat sheet."
        ),
        "deliverables": ["audio_bible", "score_cues", "sfx_library_brief", "voice_direction"],
    },
    TeamRole.QA_LEAD: {
        "ollama_model": "gpt-oss:20b",
        "specialization": (
            "You are the QA Lead. You own the test plan, bug triage, gate "
            "scoring, and the final sign-off call before each milestone. "
            "You are the studio's immune system. You score 0-100 with "
            "a concrete defect list. You never wave a gate without a waiver "
            "on file."
        ),
        "deliverables": ["test_plan", "regression_matrix", "gate_scorecard", "defect_list"],
    },
    TeamRole.MARKETING_LEAD: {
        "ollama_model": "gemma4:12b",
        "specialization": (
            "You are the Marketing Lead. You own the go-to-market plan, the "
            "reveal strategy, trailer cuts, influencer outreach, the press "
            "embargo schedule, and the post-launch live-ops content calendar."
        ),
        "deliverables": ["gtm_plan", "trailer_cuts", "press_kit", "live_ops_calendar"],
    },
}


# Default model assignment per phase — lets the EP call the right role
PHASE_OWNERS: Dict[Phase, TeamRole] = {
    Phase.CONCEPT: TeamRole.CREATIVE_DIRECTOR,
    Phase.PROTOTYPE: TeamRole.GAME_DIRECTOR,
    Phase.VERTICAL_SLICE: TeamRole.CREATIVE_DIRECTOR,
    Phase.ALPHA: TeamRole.TECHNICAL_DIRECTOR,
    Phase.BETA: TeamRole.QA_LEAD,
    Phase.GOLD: TeamRole.EXECUTIVE_PRODUCER,
    Phase.LAUNCH: TeamRole.MARKETING_LEAD,
    Phase.POST_LIVE: TeamRole.MARKETING_LEAD,
}


class Team:
    """A roster of studio roles, each backed by a local Ollama model."""

    def __init__(self, members: Optional[List[TeamMember]] = None) -> None:
        self.members: Dict[TeamRole, TeamMember] = {}
        for m in (members or default_team()):
            self.members[m.role] = m

    def get(self, role: TeamRole) -> TeamMember:
        if role not in self.members:
            raise KeyError(f"no team member for {role}")
        return self.members[role]

    def owner_of(self, phase: Phase) -> TeamMember:
        return self.get(PHASE_OWNERS[phase])

    def brief(self, project_title: str, phase: Phase, prompt: str) -> str:
        """Ask the phase owner to produce a deliverable for this milestone.

        Returns the produced text. Writes the artifact to `workdir` when given.
        """
        owner = self.owner_of(phase)
        return self.ask(owner.role, project_title, phase, prompt)

    def ask(self, role: TeamRole, project_title: str, phase: Phase,
            prompt: str, workdir: Optional[Path] = None) -> str:
        """Direct ask to a specific team member. Returns the produced text.

        When `workdir` is given, writes the artifact as Markdown and returns
        the path string; otherwise returns the raw text.
        """
        m = self.get(role)
        system = (f"{m.specialization}\n\n"
                  f"Project: {project_title}\n"
                  f"Current phase: {phase.value}\n"
                  f"Deliverable family: {', '.join(m.deliverables)}\n"
                  f"Be concrete, specific, and produce work a real studio would ship.")
        # Late import so the module is importable without Ollama installed
        from agent.studio.adapters.ollama_local import _ollama_chat, _ollama_available
        if not _ollama_available():
            text = f"[stub:{m.role.value}] {prompt}\n\n(Ollama offline — would use {m.ollama_model})"
        else:
            text = _ollama_chat(m.ollama_model, system, prompt, max_tokens=4000)
        if workdir is not None:
            workdir.mkdir(parents=True, exist_ok=True)
            fname = f"{role.value}_{phase.value}_{int(time.time()*1000)}.md"
            (workdir / fname).write_text(text, encoding="utf-8")
            return str(workdir / fname)
        return text

    def roster(self) -> List[Dict]:
        """Roster summary for display / status."""
        return [
            {"role": m.role.value, "name": m.name,
             "model": m.ollama_model, "deliverables": m.deliverables}
            for m in self.members.values()
        ]


def default_team() -> List[TeamMember]:
    """Construct the canonical 10-person AAA studio team."""
    team: List[TeamMember] = []
    for role, preset in ROLE_PRESETS.items():
        team.append(TeamMember(
            role=role,
            ollama_model=preset["ollama_model"],
            specialization=preset["specialization"],
            deliverables=preset["deliverables"],
        ))
    return team
