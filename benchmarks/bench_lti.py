"""Micro-benchmark for fusion_lti aggregation state machine.

Simulates a 5-round fusion with synthetic strings, times the full
aggregation, prints per-round alpha values and total wall time.

Run: python benchmarks/bench_lti.py
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from agent.fusion_lti import compute_alpha, init_fusion_state

# Synthetic per-round outputs of decreasing novelty (simulating convergence)
ROUND_OUTPUTS = [
    "Initial draft of the fused response. Architecture is recurrent-depth.",
    "Refined draft with more detail on the LTI injection. Recurrent depth.",
    "Polished draft. Mentions ACT halting and LTI injection in detail.",
    "Polished draft. Mentions ACT halting and LTI injection in detail. Minor edits.",
    "Polished draft. Mentions ACT halting and LTI injection in detail. Minor edits.",
]


def main() -> None:
    print("=== fusion_lti aggregation bench ===")
    print("compute_alpha sanity:")
    for la, ld in [(0.0, 0.0), (-1.0, 0.0), (1.0, 0.0), (-5.0, -5.0), (5.0, 5.0)]:
        a = compute_alpha(la, ld)
        print(f"  log_alpha={la:+.1f}  log_dt={ld:+.1f}  -> alpha={a:.6f}  in_unit={0<a<1}")

    # End-to-end: drive 5 rounds through state
    original = "The original single-model response anchoring the fusion."
    state = init_fusion_state(original)
    print(f"\nInitial state: alpha={state.alpha:.4f} beta={state.beta:.4f}")

    t0 = time.perf_counter()
    for i, out in enumerate(ROUND_OUTPUTS):
        # Direct state transition (mimics what fusion_router does each round)
        try:
            from agent.fusion_lti import advance_round
            state = advance_round(state, out)
            print(f"  round {i+1}: fused len={len(state.fused):4d}")
        except ImportError:
            # Older API — just record round outputs
            state.round_outputs.append(out)
            state.round += 1
            state.fused = out
    wall = time.perf_counter() - t0

    print(f"\nTotal wall:  {wall*1000:7.2f} ms over {len(ROUND_OUTPUTS)} rounds")
    print(f"Per round:   {wall*1000/len(ROUND_OUTPUTS):7.2f} ms")
    print(f"Final fused: {state.fused[:80]!r}{'...' if len(state.fused)>80 else ''}")


if __name__ == "__main__":
    main()
