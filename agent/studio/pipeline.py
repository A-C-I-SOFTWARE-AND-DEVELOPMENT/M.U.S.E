"""Axiom Studio — AAA production pipeline.

Runs a project through the 8 milestone gates (CONCEPT → POST_LIVE) with
QA scoring at each gate. The pipeline is stateful: it won't advance a
project past a gate until the QA Lead signs off.

Each phase produces a defined set of deliverables, stored as artifacts
on disk under <workdir>/<phase>/.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

from agent.studio.types import (
    Milestone, Phase, PhaseStatus, Project, TeamMember, TeamRole,
)
from agent.studio.team import Team, PHASE_OWNERS


# Per-phase deliverable briefs — what the phase owner produces at this gate
PHASE_BRIEFS: Dict[Phase, str] = {
    Phase.CONCEPT: (
        "Produce the vision document: thesis, 3 pillars, target audience, "
        "USP, comparable titles, high-level scope, and a 12-month milestone "
        "schedule ending in a vertical slice."
    ),
    Phase.PROTOTYPE: (
        "Produce the prototype design: core loop diagram, primary verb, one "
        "enemy AI spec, one progression hook, and the minimum playable build "
        "scope. Goal: prove the fun in 5 minutes."
    ),
    Phase.VERTICAL_SLICE: (
        "Produce the vertical slice spec: 15-30 minutes of AAA-quality "
        "gameplay, one full level, onboarding flow, full art/audio pass, "
        "and the narrative beat for this section."
    ),
    Phase.ALPHA: (
        "Produce the alpha checklist: feature-complete list, content pipeline "
        "status, perf budget vs actuals, known crash list, and the QA test "
        "plan covering every system."
    ),
    Phase.BETA: (
        "Produce the beta exit criteria: content-complete confirmation, "
        "bug burndown chart, platform certification readiness, and the "
        "day-1 patch plan."
    ),
    Phase.GOLD: (
        "Produce the gold submission package: release candidate build ID, "
        "platform-holder submission form, final perf report, and the launch "
        "readiness sign-off."
    ),
    Phase.LAUNCH: (
        "Produce the go-to-market plan: reveal trailer cut list, influencer "
        "outreach list, press embargo schedule, day-1 patch comms, and the "
        "first 30-day live-ops calendar."
    ),
    Phase.POST_LIVE: (
        "Produce the post-live roadmap: DLC plan, seasonal content calendar, "
        "community feedback loop, and the live-service monetization update."
    ),
}


class Pipeline:
    """Stateful milestone-gated production pipeline for one project."""

    def __init__(self, project: Project, team: Team,
                 root: Optional[Path] = None) -> None:
        self.project = project
        self.team = team
        self.root = Path(root or Path.cwd() / "studio_output")

        # Ensure all 8 milestones exist on the project
        if not project.milestones:
            for phase in Phase:
                project.milestones[phase] = Milestone(phase=phase)

    # ── phase progression ───────────────────────────────────────────

    def current_phase(self) -> Phase:
        """The first NOT_STARTED or IN_PROGRESS phase."""
        for phase in Phase:
            m = self.project.milestones[phase]
            if m.status not in (PhaseStatus.PASSED, PhaseStatus.WAIVED):
                return phase
        return list(Phase)[-1]  # everything passed

    def run_phase(self, phase: Optional[Phase] = None,
                  extra_prompt: str = "") -> Dict:
        """Run the owner of `phase` (or current) to produce deliverables.

        Marks the milestone IN_PROGRESS, calls the team member, writes the
        artifact to <workdir>/<phase>/, and returns a status dict.
        """
        if phase is None:
            phase = self.current_phase()
        m = self.project.milestones[phase]
        m.status = PhaseStatus.IN_PROGRESS
        m.started_at = time.time()

        wd = self._phase_dir(phase)
        brief = PHASE_BRIEFS[phase]
        if extra_prompt:
            brief = f"{brief}\n\n{extra_prompt}"

        artifact_path = self.team.brief(
            project_title=self.project.title,
            phase=phase,
            prompt=brief,
        )

        # team.brief returns text; write it to disk and record
        out_file = wd / f"{phase.value}_{int(time.time()*1000)}.md"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(artifact_path, encoding="utf-8")

        m.artifacts.append(str(out_file))
        return {
            "phase": phase.value,
            "owner": self.team.owner_of(phase).role.value,
            "artifact": str(out_file),
            "status": m.status.value,
        }

    # ── QA gate ─────────────────────────────────────────────────────

    def qa_review(self, phase: Optional[Phase] = None,
                  force_score: Optional[float] = None) -> Dict:
        """QA Lead reviews the phase and assigns a 0-100 score.

        Pass `force_score` to bypass the LLM (used in tests / fast mode).
        If the score clears the threshold, the gate is PASSED.
        """
        if phase is None:
            phase = self.current_phase()
        m = self.project.milestones[phase]

        if force_score is not None:
            score = float(force_score)
            notes = f"force-scored (test/fast mode)"
        else:
            # Ask QA Lead for a structured score
            artifact_text = ""
            for p in m.artifacts:
                try:
                    artifact_text += Path(p).read_text(encoding="utf-8")[:4000] + "\n---\n"
                except Exception:
                    pass
            prompt = (
                f"Review the following {phase.value} deliverables and produce a "
                f"QA scorecard. Output JSON: "
                f'{{"score": 0-100, "defects": ["..."], "verdict": "pass|fail|waive", '
                f'"notes": "..."}}.\n\nDeliverables:\n{artifact_text[:8000]}'
            )
            from agent.studio.adapters.ollama_local import (
                _ollama_chat, _ollama_available,
            )
            if not _ollama_available():
                # Fast stub: pass with 75 if artifacts exist
                score = 75.0 if m.artifacts else 0.0
                notes = "stub QA (Ollama offline) — auto 75 if artifacts present"
            else:
                qa = self.team.get(TeamRole.QA_LEAD)
                raw = _ollama_chat(qa.ollama_model, qa.specialization,
                                   prompt, max_tokens=1500)
                try:
                    parsed = json.loads(raw.strip().strip("`").strip())
                    score = float(parsed.get("score", 0))
                    notes = parsed.get("notes", "")
                    m.review_notes = json.dumps(parsed, indent=2)
                except (json.JSONDecodeError, ValueError):
                    score = 0.0
                    notes = f"QA returned unparseable output: {raw[:200]}"

        m.qa_score = max(0.0, min(100.0, score))
        m.notes = notes

        if m.can_pass():
            m.status = PhaseStatus.PASSED
            m.completed_at = time.time()
        elif m.qa_score > 0:
            m.status = PhaseStatus.BLOCKED

        return {
            "phase": phase.value,
            "qa_score": m.qa_score,
            "threshold": m.qa_threshold,
            "status": m.status.value,
            "passed": m.status == PhaseStatus.PASSED,
            "notes": notes,
        }

    def waive(self, phase: Phase, reason: str) -> Dict:
        """EP override: waive a blocked gate."""
        m = self.project.milestones[phase]
        m.status = PhaseStatus.WAIVED
        m.notes = f"WAIVED: {reason}"
        m.completed_at = time.time()
        return {"phase": phase.value, "status": "waived", "reason": reason}

    # ── helpers ─────────────────────────────────────────────────────

    def _phase_dir(self, phase: Phase) -> Path:
        wd = self.project.workdir or self.root / self.project.id
        wd = Path(wd)
        d = wd / phase.value
        d.mkdir(parents=True, exist_ok=True)
        return d

    def status(self) -> Dict:
        """Full pipeline status for display."""
        return {
            "project_id": self.project.id,
            "title": self.project.title,
            "current_phase": self.current_phase().value,
            "milestones": [
                {"phase": m.phase.value, "status": m.status.value,
                 "qa_score": m.qa_score, "threshold": m.qa_threshold,
                 "artifacts": len(m.artifacts)}
                for m in self.project.milestones.values()
            ],
        }
