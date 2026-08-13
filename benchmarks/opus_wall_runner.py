#!/usr/bin/env python3
"""Opus Benchmark Wall — dual-run candidate vs Claude Opus 4.6.

Scores MUSE Super (or any OpenAI-compatible endpoint) against Opus under the
same harness. Emits JSONL scorecards for promotion gates.

Usage:
  set HERMES_HOME=C:\\Users\\Echer\\AppData\\Local\\hermes
  python -m benchmarks.opus_wall_runner --suite polyglot --limit 5 \\
      --candidate-model muse --candidate-base-url http://127.0.0.1:11435/v1 \\
      --opus-model anthropic/claude-opus-4.6 --opus-base-url https://openrouter.ai/api/v1
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Suites reuse existing runners where possible; polyglot is the smoke default.
OPUS_BASELINES_PATH = Path(
    os.environ.get("HERMES_HOME", str(Path.home() / "AppData" / "Local" / "hermes"))
) / "jarvis_prime" / "opus_baselines.json"

WALL_RESULTS_PATH = Path(
    os.environ.get("HERMES_HOME", str(Path.home() / "AppData" / "Local" / "hermes"))
) / "jarvis_prime" / "opus_wall_results.jsonl"


# Published Opus 4.6 ballpark anchors (re-measure with --freeze-baselines).
PUBLISHED_OPUS_46 = {
    "swe_bench_verified": 0.808,
    "gpqa_diamond": 0.913,
    "terminal_bench_2": 0.654,
    "mmlu_pro": 0.820,
    "humaneval_plus": 0.935,
    "ifeval": 0.910,
}


def _chat(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    *,
    timeout: float = 180.0,
) -> Tuple[str, float]:
    from openai import OpenAI

    client = OpenAI(base_url=base_url.rstrip("/"), api_key=api_key or "none", timeout=timeout)
    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
        temperature=0.2,
    )
    elapsed = time.perf_counter() - t0
    content = (resp.choices[0].message.content or "") if resp.choices else ""
    return content, elapsed


def _polyglot_prompts(limit: int) -> List[Dict[str, str]]:
    """Minimal coding prompts (inline) — full suite uses benchmarks.polyglot_runner."""
    tasks = [
        {
            "id": "py_sum",
            "prompt": "Write a Python function `add(a, b)` that returns a+b. Reply with code only.",
            "expect": "def add",
        },
        {
            "id": "py_fizz",
            "prompt": "Write Python `fizzbuzz(n)` returning list of fizzbuzz strings 1..n. Code only.",
            "expect": "fizz",
        },
        {
            "id": "js_reverse",
            "prompt": "Write JavaScript function reverseString(s). Code only.",
            "expect": "function",
        },
        {
            "id": "reason_prime",
            "prompt": "How many primes are there below 30? Answer with the integer only.",
            "expect": "10",
        },
        {
            "id": "reason_gpqa_style",
            "prompt": "In quantum mechanics, what is the eigenvalue of σ_z for spin up along z? Answer briefly.",
            "expect": "ħ/2",
        },
    ]
    return tasks[: max(1, limit)]


def _score(text: str, expect: str) -> float:
    t = (text or "").lower()
    e = (expect or "").lower()
    if e in t:
        return 1.0
    # soft credit for code-ish answers
    if any(k in t for k in ("def ", "function", "return")) and e in ("def add", "function", "fizz"):
        return 0.5
    return 0.0


def run_suite(
    *,
    suite: str,
    limit: int,
    candidate_model: str,
    candidate_base_url: str,
    candidate_key: str,
    opus_model: str,
    opus_base_url: str,
    opus_key: str,
) -> Dict[str, Any]:
    tasks = _polyglot_prompts(limit) if suite in ("polyglot", "smoke") else _polyglot_prompts(limit)
    rows: List[Dict[str, Any]] = []
    cand_scores: List[float] = []
    opus_scores: List[float] = []

    for task in tasks:
        prompt = task["prompt"]
        expect = task["expect"]
        c_text, c_t = _chat(candidate_base_url, candidate_key, candidate_model, prompt)
        o_text, o_t = _chat(opus_base_url, opus_key, opus_model, prompt)
        c_s = _score(c_text, expect)
        o_s = _score(o_text, expect)
        cand_scores.append(c_s)
        opus_scores.append(o_s)
        rows.append(
            {
                "id": task["id"],
                "candidate_score": c_s,
                "opus_score": o_s,
                "candidate_latency_s": round(c_t, 3),
                "opus_latency_s": round(o_t, 3),
                "delta": round(c_s - o_s, 3),
            }
        )

    summary = {
        "suite": suite,
        "product": "MUSE Super",
        "campaign": "beat_opus_4_6",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candidate": {"model": candidate_model, "base_url": candidate_base_url},
        "opus": {"model": opus_model, "base_url": opus_base_url},
        "n": len(rows),
        "candidate_mean": round(sum(cand_scores) / max(len(cand_scores), 1), 4),
        "opus_mean": round(sum(opus_scores) / max(len(opus_scores), 1), 4),
        "win": (sum(cand_scores) / max(len(cand_scores), 1))
        >= (sum(opus_scores) / max(len(opus_scores), 1)),
        "rows": rows,
        "published_opus_46_anchors": PUBLISHED_OPUS_46,
    }
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Opus Benchmark Wall dual-runner")
    parser.add_argument("--suite", default="smoke", choices=["smoke", "polyglot"])
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--candidate-model", default="muse")
    parser.add_argument("--candidate-base-url", default="http://127.0.0.1:11435/v1")
    parser.add_argument("--candidate-key", default="muse-local")
    parser.add_argument("--opus-model", default="anthropic/claude-opus-4.6")
    parser.add_argument("--opus-base-url", default="https://openrouter.ai/api/v1")
    parser.add_argument("--opus-key", default=os.getenv("OPENROUTER_API_KEY", ""))
    parser.add_argument("--freeze-baselines", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Write schema only, no API calls")
    args = parser.parse_args(argv)

    WALL_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    if args.freeze_baselines:
        OPUS_BASELINES_PATH.write_text(
            json.dumps(
                {
                    "opus_version": "4.6",
                    "published": PUBLISHED_OPUS_46,
                    "note": "Re-measure with identical harness before claiming suite wins",
                    "frozen_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Wrote {OPUS_BASELINES_PATH}")
        return 0

    if args.dry_run:
        summary = {
            "suite": args.suite,
            "dry_run": True,
            "candidate": args.candidate_model,
            "opus": args.opus_model,
            "n": args.limit,
        }
        print(json.dumps(summary, indent=2))
        return 0

    if not args.opus_key:
        print("OPENROUTER_API_KEY required for Opus side (or pass --opus-key)")
        return 2

    summary = run_suite(
        suite=args.suite,
        limit=args.limit,
        candidate_model=args.candidate_model,
        candidate_base_url=args.candidate_base_url,
        candidate_key=args.candidate_key,
        opus_model=args.opus_model,
        opus_base_url=args.opus_base_url,
        opus_key=args.opus_key,
    )
    with WALL_RESULTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))
    print(f"Appended full rows → {WALL_RESULTS_PATH}")
    return 0 if summary.get("win") else 1


if __name__ == "__main__":
    raise SystemExit(main())
