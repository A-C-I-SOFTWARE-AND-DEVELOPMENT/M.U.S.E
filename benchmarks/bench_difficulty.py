"""Micro-benchmark for fusion_difficulty.classify_difficulty.

Times N classifications across a mixed prompt corpus and reports
p50/p95/p99 latency in microseconds plus throughput.

Run: python benchmarks/bench_difficulty.py
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import statistics
from agent.fusion_difficulty import classify_difficulty, extrapolate_rounds, FusionDepth

CORPUS = [
    ("hi", "", 0),
    ("what is python?", "", 0),
    ("thanks!", "", 0),
    ("compare React and Vue for SSR", "", 1),
    ("explain how attention works in transformers", "", 0),
    ("debug this stack trace: NullPointerException at line 42", "", 2),
    (
        "design a distributed cache with LRU eviction, write-through, and "
        "active-active replication across 3 regions; explain trade-offs vs Redis",
        "", 5,
    ),
    (
        "refactor this async function to use a context manager and "
        "explain the difference between asyncio.gather and asyncio.wait",
        "long response " * 100, 3,
    ),
]


def main(n: int = 1000) -> None:
    # Warmup
    for prompt, resp, tools in CORPUS:
        classify_difficulty(prompt, resp, tools)

    timings_us: list[float] = []
    depth_counts: dict[str, int] = {}

    start = time.perf_counter()
    for i in range(n):
        prompt, resp, tools = CORPUS[i % len(CORPUS)]
        t0 = time.perf_counter_ns()
        a = classify_difficulty(prompt, resp, tools)
        timings_us.append((time.perf_counter_ns() - t0) / 1000.0)
        depth_counts[a.depth.name] = depth_counts.get(a.depth.name, 0) + 1
    wall = time.perf_counter() - start

    timings_us.sort()
    p50 = timings_us[len(timings_us) // 2]
    p95 = timings_us[int(len(timings_us) * 0.95)]
    p99 = timings_us[int(len(timings_us) * 0.99)]
    mean = statistics.mean(timings_us)

    # Sanity: extrapolate on the hardest sample
    hard = classify_difficulty(CORPUS[-2][0], CORPUS[-2][1], CORPUS[-2][2])
    rounds = extrapolate_rounds(hard, base_rounds=1, max_rounds=5)

    print("=== fusion_difficulty.classify_difficulty bench ===")
    print(f"  iterations:  {n}")
    print(f"  wall:        {wall*1000:7.2f} ms")
    print(f"  throughput:  {n/wall:9.0f} ops/sec")
    print(f"  mean:        {mean:7.2f} us")
    print(f"  p50:         {p50:7.2f} us")
    print(f"  p95:         {p95:7.2f} us")
    print(f"  p99:         {p99:7.2f} us")
    print(f"  depth dist:  {depth_counts}")
    print(f"  deep sample: score={hard.score:.3f} -> rounds={rounds}")


if __name__ == "__main__":
    main()
