"""Live end-to-end smoke for Axiom Studio:

  brief → produce_film()  → make_bundle()  → single .zip
  brief → produce_game()  → make_bundle()  → single .zip

LLM stages run on local Ollama (qwen3.5:9b, fast).
Image stage runs on Pollinations (free, no key).
Voice stage runs on edge-tts (free, no key).
Everything else stubs to JSON manifests.
"""
from __future__ import annotations

import os
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.studio import (
    StudioOrchestrator, FilmBrief, GameBrief, Quality, Provider, make_bundle,
)
from agent.studio.adapters import ollama_local


# Override default Ollama model env so every adapter uses the fast 9B
os.environ.setdefault("AXIOM_NUM_CTX", "4096")


def main() -> None:
    if not ollama_local._ollama_available():
        print("⚠  Ollama not reachable at", ollama_local.OLLAMA_BASE_URL)
        sys.exit(1)

    print("=" * 70)
    print("Axiom Studio — full pipeline → single bundle (free, local)")
    print("=" * 70)

    out_root = Path(__file__).parent.parent / "studio_output_smoke" / "bundle"
    out_root.mkdir(parents=True, exist_ok=True)

    # ── FILM ───────────────────────────────────────────────────────
    print("\n▶ FILM: 'The Cartographer' (5-min short, DRAFT quality)")
    t0 = time.perf_counter()
    film = StudioOrchestrator(root=out_root).produce_film(FilmBrief(
        title="The Cartographer",
        logline=("A blind mapmaker in 1890s Patagonia discovers her chalk "
                 "drawings of impossible coastlines start appearing in real maps."),
        runtime_min=5,           # tiny to keep smoke fast
        genre="magical-realism",
        tone="contemplative, painterly",
        quality=Quality.DRAFT,
        extra={"characters": ["NARRATOR", "ELIAS"], "sfx_cues": ["wind howl"]},
    ))
    film_wall = time.perf_counter() - t0
    print(f"  pipeline wall: {film_wall:.1f}s   stages: {len(film.stages)}")
    by_provider = {}
    for s in film.stages:
        by_provider[s.provider.value] = by_provider.get(s.provider.value, 0) + 1
    for prov, n in sorted(by_provider.items()):
        print(f"    {prov:30s} {n} stages")

    film_zip = make_bundle(film)
    size_mb = film_zip.stat().st_size / 1e6
    print(f"  bundle: {film_zip.name}   ({size_mb:.2f} MB)")
    with zipfile.ZipFile(film_zip) as zf:
        names = zf.namelist()
        print(f"  entries: {len(names)}")
        for n in sorted(names)[:8]:
            print(f"    · {n}")
        if len(names) > 8:
            print(f"    · …and {len(names) - 8} more")

    # ── GAME ───────────────────────────────────────────────────────
    print("\n▶ GAME: 'Hollowmark' (action-RPG, DRAFT quality)")
    t0 = time.perf_counter()
    game = StudioOrchestrator(root=out_root).produce_game(GameBrief(
        title="Hollowmark",
        genre="action-rpg",
        target="PC",
        perspective="third-person",
        setting="dark fantasy, calligraphic aesthetic",
        core_loop="explore -> combat -> inscribe -> upgrade",
        art_style="ink-wash",
        quality=Quality.DRAFT,
        engine=Provider.UE5,
        extra={
            "characters": ["Kael", "Inkara"],
            "levels": ["Scriptorium"],
            "npc_voices": ["Merchant"],
            "score_zones": ["exploration"],
            "sfx_set": ["ink splash"],
        },
    ))
    game_wall = time.perf_counter() - t0
    print(f"  pipeline wall: {game_wall:.1f}s   stages: {len(game.stages)}")
    by_provider = {}
    for s in game.stages:
        by_provider[s.provider.value] = by_provider.get(s.provider.value, 0) + 1
    for prov, n in sorted(by_provider.items()):
        print(f"    {prov:30s} {n} stages")

    game_zip = make_bundle(game)
    size_mb = game_zip.stat().st_size / 1e6
    print(f"  bundle: {game_zip.name}   ({size_mb:.2f} MB)")
    with zipfile.ZipFile(game_zip) as zf:
        names = zf.namelist()
        print(f"  entries: {len(names)}")
        for n in sorted(names)[:8]:
            print(f"    · {n}")
        if len(names) > 8:
            print(f"    · …and {len(names) - 8} more")

    total = film_wall + game_wall
    print("\n" + "=" * 70)
    print(f"DONE   total wall: {total:.1f}s   cost: $0.00")
    print(f"       film bundle: {film_zip}")
    print(f"       game bundle: {game_zip}")
    print("=" * 70)


if __name__ == "__main__":
    main()
