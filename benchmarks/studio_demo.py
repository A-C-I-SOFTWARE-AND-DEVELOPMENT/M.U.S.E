"""End-to-end demo: produce a film + a AAA game project, stub mode.

Run:  python -m benchmarks.studio_demo
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.studio import StudioOrchestrator, FilmBrief, GameBrief, Quality, Provider


def main() -> None:
    studio = StudioOrchestrator()

    print("┌─────────────────────────────────────────────────────────┐")
    print("│ AXIOM STUDIO — full-stack generative production demo    │")
    print("└─────────────────────────────────────────────────────────┘\n")

    # ── FILM ───────────────────────────────────────────────────────
    film = FilmBrief(
        title="The Last Signal",
        logline="A radio engineer in 1962 hears a transmission — from herself, 60 years later.",
        runtime_min=110,
        genre="sci-fi thriller",
        tone="lyrical, paranoid, IMAX-scale",
        target_rating="PG-13",
        quality=Quality.THEATRICAL,
        extra={
            "characters": ["Helena Voss (28)", "Helena Voss (88)", "Director Calder", "The Voice"],
            "sfx_cues": ["1962 tape reel hiss", "morse code", "thunder over Atlantic",
                         "vacuum tube hum", "needle drop", "long-distance static"],
        },
    )
    film_manifest = studio.produce_film(film)
    print(film_manifest.summary())
    print()

    # ── GAME ───────────────────────────────────────────────────────
    game = GameBrief(
        title="Aetherbound",
        genre="action-RPG with soulslike combat",
        target="PC / PS5 / Xbox Series X",
        perspective="third-person over-shoulder",
        setting="post-magical-collapse Victorian London, 1893",
        core_loop="explore districts → take contracts → fight aether-touched → bind essence → craft → upgrade safehouse",
        art_style="painterly photorealism, Frostbite-tier, Lumen GI",
        runtime_hours=40,
        quality=Quality.FINAL,
        engine=Provider.UE5,
        extra={
            "characters": ["Aria Vance", "Cipher", "The Curator",
                           "Father Holm", "Bell of the Foundry"],
            "levels": ["Whitechapel Foundry", "The Aether Spire", "Drowned Court",
                       "Bonewright Cathedral", "The Lower Sky"],
            "npc_voices": ["Merchant", "Constable", "Street Urchin",
                           "Aristocrat", "Foundry Worker"],
            "score_zones": ["exploration", "combat", "boss", "stealth",
                            "main_menu", "hub_town", "endgame"],
            "sfx_set": [
                "footsteps on cobblestone", "footsteps on iron grating",
                "aether-blade draw", "aether-blade parry", "essence-bind ritual",
                "UI confirm", "UI cancel", "UI level-up", "enemy roar",
                "ambient London 1893 street", "rain on slate roof", "gas lamp hiss",
            ],
        },
    )
    game_manifest = studio.produce_game(game)
    print(game_manifest.summary())
    print()

    print("─" * 60)
    print(f"FILM workdir: {film_manifest.workdir}")
    print(f"GAME workdir: {game_manifest.workdir}")
    print()
    print("All stages in STUB mode (no API keys). Wire keys to graduate:")
    print("  OPENROUTER_API_KEY   → real screenplay + GDD via Claude Opus")
    print("  BFL_API_KEY          → Flux 1.1 Pro concept art")
    print("  GOOGLE_VEO_API_KEY   → Veo 3 cinematic video")
    print("  OPENAI_API_KEY       → Sora 2 video (alternative)")
    print("  REPLICATE_API_TOKEN  → Hunyuan3D-2 character meshes")
    print("  ELEVENLABS_API_KEY   → v3 voice + SFX")
    print("  SUNO_API_KEY         → v4 adaptive score")
    print("  GOOGLE_GENIE_API_KEY → Genie 3 interactive worlds")


if __name__ == "__main__":
    main()
