"""Live smoke test for Axiom Studio against the local Ollama daemon.

Requires Ollama running at $OLLAMA_BASE_URL (default http://localhost:11434).
Runs a tiny film + game brief through the full DAG; all LLM stages hit
local models for free. Image / video / audio stages stub out (no API keys).

Usage:  python benchmarks/bench_studio_local.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.studio import StudioOrchestrator, FilmBrief, GameBrief
from agent.studio.adapters import ollama_local
from agent.studio.types import Provider, Quality


def main() -> None:
    if not ollama_local._ollama_available():
        print("⚠  Ollama not reachable at", ollama_local.OLLAMA_BASE_URL)
        print("   Start it with: ollama serve")
        sys.exit(1)

    print("=" * 70)
    print("Axiom Studio — local Ollama smoke run")
    print("=" * 70)
    print(f"Ollama base: {ollama_local.OLLAMA_BASE_URL}")
    print()

    out_root = Path(__file__).parent.parent / "studio_output_smoke"
    orch = StudioOrchestrator(root=out_root)

    # ── Tiny film brief ────────────────────────────────────────────
    print("▶ FILM pipeline: 'The Cartographer' (10-min short)")
    t0 = time.perf_counter()
    film = orch.produce_film(FilmBrief(
        title="The Cartographer",
        logline=("A blind mapmaker in 1890s Patagonia discovers her chalk "
                 "drawings of impossible coastlines start appearing in real maps."),
        runtime_min=10,
        genre="magical-realism drama",
        tone="contemplative, painterly, slow-burn",
        quality=Quality.DRAFT,
    ))
    film_wall = time.perf_counter() - t0
    print(f"  wall: {film_wall:6.1f}s  stages: {len(film.stages)}")
    local_stages = [s for s in film.stages if s.provider == Provider.OLLAMA_LOCAL]
    print(f"  local-ollama stages: {len(local_stages)}  (free)")
    for s in local_stages:
        artifact = s.artifacts[0] if s.artifacts else "—"
        print(f"    • {s.stage:14s} {s.duration_s:5.1f}s  {Path(artifact).name}")
    print(f"  manifest: {film.workdir / 'manifest.txt'}")

    # ── Tiny game brief ────────────────────────────────────────────
    print()
    print("▶ GAME pipeline: 'Hollowmark' (action-RPG)")
    t0 = time.perf_counter()
    game = orch.produce_game(GameBrief(
        title="Hollowmark",
        logline=("A scribe-knight bonded to a sentient ink-spirit must inscribe "
                 "the names of forgotten gods before reality un-writes itself."),
        genre="action-rpg",
        target="PC/PS5",
        perspective="third-person",
        setting="dark fantasy, baroque calligraphic aesthetic",
        core_loop="explore -> combat -> inscribe -> upgrade -> explore",
        art_style="hand-painted ink-wash, Studio Ghibli x FromSoftware",
        quality=Quality.DRAFT,
        engine=Provider.UE5,
    ))
    game_wall = time.perf_counter() - t0
    print(f"  wall: {game_wall:6.1f}s  stages: {len(game.stages)}")
    local_stages = [s for s in game.stages if s.provider == Provider.OLLAMA_LOCAL]
    print(f"  local-ollama stages: {len(local_stages)}  (free)")
    for s in local_stages:
        artifact = s.artifacts[0] if s.artifacts else "—"
        print(f"    • {s.stage:14s} {s.duration_s:5.1f}s  {Path(artifact).name}")
    print(f"  manifest: {game.workdir / 'manifest.txt'}")

    print()
    print("=" * 70)
    print(f"TOTAL: {film_wall + game_wall:.1f}s   cost: $0.00   "
          f"(all LLM stages local — image/video/audio still stubbed)")
    print("=" * 70)


if __name__ == "__main__":
    main()
