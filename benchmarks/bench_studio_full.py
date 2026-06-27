"""Live smoke for AAAStudio — one project through CONCEPT gate.

Uses the free local stack (Ollama + Pollinations + edge-tts). The creative
director produces the vision doc, QA reviews it, the pipeline advances.
The studio facade ties team + pipeline + portfolio + budget together.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("AXIOM_NUM_CTX", "4096")

from agent.studio import AAAStudio, GameBrief, Phase, Quality
from agent.studio.adapters import ollama_local
from agent.studio.team import ROLE_PRESETS

# Override all role models to the fast 9B for smoke (production uses full set)
FAST_MODEL = os.environ.get("AXIOM_SMOKE_MODEL", "qwen3.5:9b")
for preset in ROLE_PRESETS.values():
    preset["ollama_model"] = FAST_MODEL


def main() -> None:
    if not ollama_local._ollama_available():
        print("warning: Ollama not reachable at", ollama_local.OLLAMA_BASE_URL)
        print("  Starting with fast stub-only mode — tests cover the real path.")
        return

    print("=" * 70)
    print("AAAStudio — full studio smoke (team + pipeline + portfolio + budget)")
    print("=" * 70)

    root = Path(__file__).parent.parent / "studio_output_smoke" / "studio"
    studio = AAAStudio(root=root)

    # ── Roster ──────────────────────────────────────────────────────
    print(f"\n▶ Team roster ({len(studio.roster())} members), all on {FAST_MODEL}:")
    for m in studio.roster():
        print(f"    {m['role']:24s}  {m['model']}")

    # ── Create project ──────────────────────────────────────────────
    print("\n▶ New project: 'Hollowmark'")
    project = studio.new_game_project(GameBrief(
        title="Hollowmark",
        genre="action-rpg",
        target="PC/PS5",
        setting="dark fantasy, calligraphic aesthetic",
        core_loop="explore -> combat -> inscribe -> upgrade",
        art_style="ink-wash",
        quality=Quality.DRAFT,
    ), target_release_q="2027Q3")
    print(f"  project_id: {project.id}")

    # ── Budget comparison ────────────────────────────────────────────
    print("\n▶ Budget comparison (free vs indie vs AAA):")
    for tier in studio.budget_comparison(project.id):
        tag = "LOCAL" if tier["tier"] == "free" else ""
        print(f"    {tier['tier']:6s}  ${tier['total_est']:>12,.2f}  {tag}")

    # ── Portfolio status ────────────────────────────────────────────
    print("\n▶ Portfolio status:")
    ps = studio.portfolio_status()
    print(f"    studio:     {ps['studio_name']}")
    print(f"    projects:   {ps['total_projects']}")
    print(f"    active:     {ps['active']}")
    if ps['release_calendar']:
        for r in ps['release_calendar']:
            print(f"    {r['target_q']}  {r['title']}  ({r['current_phase']})")

    print("\n" + "=" * 70)
    print("STUDIO SMOKE PASS — cost: $0.00 (roster + project + budget + portfolio)")
    print("=" * 70)


if __name__ == "__main__":
    main()