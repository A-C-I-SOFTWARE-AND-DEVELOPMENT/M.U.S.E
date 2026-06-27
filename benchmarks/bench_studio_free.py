"""Live smoke for free image (Pollinations) + voice (edge-tts) adapters."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.studio.adapters import free_providers


def main() -> None:
    out = Path(__file__).parent.parent / "studio_output_smoke" / "free"
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Axiom Studio — free image + voice smoke")
    print("=" * 70)

    # ── Image ──────────────────────────────────────────────────────
    print(f"\n▶ Pollinations available: {free_providers._pollinations_available()}")
    if free_providers._pollinations_available():
        ad = free_providers.PollinationsImageAdapter()
        t0 = time.perf_counter()
        r = ad.run(
            "cinematic key frame, blind cartographer in 1890s Patagonia, "
            "candlelit cabin, ink-stained hands on parchment, anamorphic, "
            "shot on Arri Alexa 65, painterly, contemplative",
            out, width=1024, height=576, seed=7,
        )
        dt = time.perf_counter() - t0
        print(f"  status: {r.status}  wall: {dt:.1f}s")
        print(f"  notes: {r.notes}")
        if r.artifacts:
            p = Path(r.artifacts[0])
            print(f"  artifact: {p.name}  ({p.stat().st_size} bytes)")
    else:
        print("  (pollinations unreachable, skipped)")

    # ── Voice ──────────────────────────────────────────────────────
    print(f"\n▶ edge-tts available: {free_providers._edge_tts_available()}")
    if free_providers._edge_tts_available():
        ad = free_providers.EdgeTTSVoiceAdapter()
        t0 = time.perf_counter()
        r = ad.run(
            "Greeting line for Hero NPC.",
            out,
            text="Hold the line, brothers. The dawn will find us standing.",
        )
        dt = time.perf_counter() - t0
        print(f"  status: {r.status}  wall: {dt:.1f}s")
        print(f"  notes: {r.notes}")
        if r.artifacts:
            p = Path(r.artifacts[0])
            print(f"  artifact: {p.name}  ({p.stat().st_size} bytes)")
    else:
        print("  (edge-tts missing, skipped)")

    print("\n" + "=" * 70)
    print("DONE   cost: $0.00")
    print("=" * 70)


if __name__ == "__main__":
    main()
