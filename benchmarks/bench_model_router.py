"""Micro-benchmark for fusion_model_router.

Runs 10k routing decisions over 8 query-type mixes and prints:
  - throughput (decisions/sec)
  - per-decision latency (mean / p95 / p99)
  - load-balance fairness (stddev of selection counts across models)

Run: python benchmarks/bench_model_router.py
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import statistics
import time
from collections import Counter
from agent.fusion_model_router import MoEModelRouter, QueryType

PROMPT_MIX = [
    ("def quicksort(arr): pass  # refactor this", QueryType.CODE),
    ("integrate x^2 dx from 0 to 1, show steps", QueryType.MATH),
    ("write a story about a robot in love", QueryType.CREATIVE),
    ("translate to french: hello, how are you?", QueryType.MULTILINGUAL),
    ("compare and contrast REST vs GraphQL trade-offs", QueryType.ANALYTICAL),
    ("what is the capital of japan?", QueryType.FACTUAL),
    ("hi", QueryType.GENERAL),
    ("debug this stack trace: TypeError at line 42 in async handler", QueryType.CODE),
]

MODELS = [
    "anthropic/claude-opus-4.6",
    "google/gemini-2.5-pro",
    "deepseek/deepseek-r1",
    "openai/gpt-5",
    "meta-llama/llama-4-70b",
]


def main(n: int = 10000) -> None:
    router = MoEModelRouter(available_models=MODELS, anchor_model=MODELS[0])

    # Warmup classify cache
    for p, _ in PROMPT_MIX:
        router.classify_query(p)

    selections: Counter[str] = Counter()
    type_hits = 0
    timings_us: list[float] = []

    start = time.perf_counter()
    for i in range(n):
        prompt, expected = PROMPT_MIX[i % len(PROMPT_MIX)]
        t0 = time.perf_counter_ns()
        qtype = router.classify_query(prompt)
        # Pick top model for this query type (simulate routing)
        try:
            picked = router.route(prompt, k=2)
            for m in picked:
                selections[m] += 1
        except Exception:
            # Older API: just count classification
            selections[MODELS[hash(qtype) % len(MODELS)]] += 1
        timings_us.append((time.perf_counter_ns() - t0) / 1000.0)
        if qtype == expected:
            type_hits += 1
    wall = time.perf_counter() - start

    timings_us.sort()
    mean = statistics.mean(timings_us)
    p95 = timings_us[int(len(timings_us) * 0.95)]
    p99 = timings_us[int(len(timings_us) * 0.99)]

    # Load-balance fairness: lower stddev = fairer distribution
    counts = [selections.get(m, 0) for m in MODELS]
    fairness = statistics.stdev(counts) if len(counts) > 1 else 0.0
    expected_per_model = sum(counts) / len(counts)
    fairness_pct = (fairness / expected_per_model * 100) if expected_per_model else 0.0

    print("=== fusion_model_router bench ===")
    print(f"  iterations:        {n}")
    print(f"  wall:              {wall*1000:7.2f} ms")
    print(f"  throughput:        {n/wall:9.0f} decisions/sec")
    print(f"  mean latency:      {mean:7.2f} us")
    print(f"  p95 latency:       {p95:7.2f} us")
    print(f"  p99 latency:       {p99:7.2f} us")
    print(f"  classify accuracy: {type_hits/n*100:5.1f}% (vs labeled corpus)")
    print(f"  selections:        {dict(selections)}")
    print(f"  load stddev:       {fairness:7.1f}  ({fairness_pct:.1f}% of mean)")
    print(f"  -> lower stddev means fairer load balancing across models")


if __name__ == "__main__":
    main()
