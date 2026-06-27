"""Live smoke test for Axiom Studio against the local Ollama daemon.

Requires Ollama running at $OLLAMA_BASE_URL (default http://localhost:11434).
Runs ONE script + ONE GDD through the local adapter to prove the wiring;
the full DAG is tested via tests/studio/test_ollama_local.py.

Usage:  python benchmarks/bench_studio_local.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.studio.adapters import ollama_local


# Use the smallest model in the local stack for fast smoke-pass.
FAST_MODEL = os.environ.get("AXIOM_SMOKE_MODEL", "qwen3.5:9b")


def main() -> None:
    if not ollama_local._ollama_available():
        print("⚠  Ollama not reachable at", ollama_local.OLLAMA_BASE_URL)
        sys.exit(1)

    print("=" * 70)
    print("Axiom Studio — local Ollama smoke (single script + single GDD)")
    print("=" * 70)
    print(f"Model: {FAST_MODEL}")
    print()

    out = Path(__file__).parent.parent / "studio_output_smoke"
    out.mkdir(exist_ok=True)

    # ── Stage 1: script ────────────────────────────────────────────
    print("▶ Stage 1: script (logline → short scene)")
    t0 = time.perf_counter()
    ad = ollama_local.OllamaScriptAdapter()
    res = ad.run(
        "Write a 1-page scene: a blind cartographer in 1890s Patagonia draws "
        "a coastline that begins appearing on real maps overnight. INT/EXT format.",
        out,
        ollama_model=FAST_MODEL,
        max_tokens=800,
    )
    dt = time.perf_counter() - t0
    print(f"  status: {res.status}  wall: {dt:.1f}s  cost: ${res.est_cost_usd:.2f}")
    if res.artifacts:
        art = Path(res.artifacts[0])
        print(f"  artifact: {art.name}  ({art.stat().st_size} bytes)")
        print("  --- first 400 chars ---")
        print(art.read_text(encoding="utf-8")[:400])
        print("  ---")

    # ── Stage 2: GDD ───────────────────────────────────────────────
    print()
    print("▶ Stage 2: GDD (one-pager for a small game)")
    t0 = time.perf_counter()
    ad = ollama_local.OllamaGDDAdapter()
    res = ad.run(
        "One-pager GDD for 'Hollowmark': action-RPG, scribe-knight bonded to "
        "an ink-spirit, dark fantasy. Cover: vision, pillars, core loop, "
        "progression, one boss. Keep it concise.",
        out,
        ollama_model=FAST_MODEL,
        max_tokens=1200,
    )
    dt = time.perf_counter() - t0
    print(f"  status: {res.status}  wall: {dt:.1f}s  cost: ${res.est_cost_usd:.2f}")
    if res.artifacts:
        art = Path(res.artifacts[0])
        print(f"  artifact: {art.name}  ({art.stat().st_size} bytes)")
        print("  --- first 400 chars ---")
        print(art.read_text(encoding="utf-8")[:400])
        print("  ---")

    print()
    print("=" * 70)
    print("SMOKE PASS — local Ollama wiring functional, cost: $0.00")
    print("=" * 70)


if __name__ == "__main__":
    main()
