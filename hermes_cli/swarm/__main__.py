"""CLI entry: ``python -m hermes_cli.swarm "<goal>" [--repo .] [--grains specs.json]``.

A thin, additive command surface over :func:`hermes_cli.swarm.coordinator.run_swarm`.

By default it runs the conservative ``prompt_only`` executor — it partitions the
goal, proves the grains' file-domains disjoint, isolates each grain in a git
worktree, writes a Decision Ledger, and prints the result as JSON. It launches
no model and pushes nothing.

Pass ``--executor ai`` (plus ``--base_url`` / ``--api_key`` / ``--model`` /
``--provider``) to drive a real model endpoint per grain via
:class:`hermes_cli.swarm.ai_executor.AIAgentExecutor`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from hermes_cli.swarm.coordinator import run_swarm
from hermes_cli.swarm.grain import OverlapError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m hermes_cli.swarm",
        description="Run a Swarm Grainler Parallel job for a code goal.",
    )
    parser.add_argument("goal", help="The code goal to decompose and run.")
    parser.add_argument("--repo", default=".", help="Repository root (default: .).")
    parser.add_argument(
        "--grains",
        default=None,
        help="Path to a JSON file of explicit grain specs (skips decomposition).",
    )
    parser.add_argument(
        "--decomposer",
        default="directory",
        choices=["directory", "keyword", "workpacket", "llm"],
        help="How to carve the goal into grains (default: directory).",
    )
    parser.add_argument(
        "--executor",
        default="prompt_only",
        choices=["prompt_only", "ai"],
        help=(
            "Per-grain executor: 'prompt_only' (default, safe — isolates + "
            "materialises each grain, launches no model) or 'ai' (drives a "
            "real model endpoint via AIAgentExecutor; requires --base_url, "
            "--api_key, --model, and --provider)."
        ),
    )
    parser.add_argument(
        "--base_url",
        default=os.environ.get("SWARM_BASE_URL"),
        help="Model API base URL (env: SWARM_BASE_URL). Required for --executor ai.",
    )
    parser.add_argument(
        "--api_key",
        default=os.environ.get("SWARM_API_KEY") or os.environ.get("KIMI_API_KEY"),
        help=(
            "Model API key (env: SWARM_API_KEY, falls back to KIMI_API_KEY). "
            "Required for --executor ai."
        ),
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("SWARM_MODEL"),
        help="Model name (env: SWARM_MODEL). Required for --executor ai.",
    )
    parser.add_argument(
        "--provider",
        default=os.environ.get("SWARM_PROVIDER", "openai"),
        help=(
            "Provider name (env: SWARM_PROVIDER, default 'openai' — works for "
            "any OpenAI-compatible endpoint including Kimi). Required for "
            "--executor ai."
        ),
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=25,
        help="Per-grain AIAgent max_iterations (default: 25).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="Max grains to run in parallel (default: 2).",
    )
    parser.add_argument(
        "--no-self-update",
        action="store_true",
        help="Disable the auto-apply-reversible self-update loop.",
    )
    parser.add_argument(
        "--no-claim",
        action="store_true",
        help="Skip the dynamic file-domain lease claims (static proof still runs).",
    )
    args = parser.parse_args(argv)

    grains = None
    if args.grains:
        grains = json.loads(Path(args.grains).read_text(encoding="utf-8"))
        if not isinstance(grains, list):
            print("--grains file must contain a JSON list of grain specs", file=sys.stderr)
            return 2

    decomposer = None
    if grains is None:
        from hermes_cli.swarm import decompose as _d
        from hermes_cli.swarm.grainler import default_decomposer

        decomposer = {
            "directory": _d.directory_decomposer,
            "keyword": _d.keyword_decomposer,
            "workpacket": default_decomposer,
            "llm": _d.llm_decomposer,
        }[args.decomposer]

    # When --executor ai, fail fast with a clear message if credentials are
    # missing (the same check happens inside run_swarm → resolve_executor, but
    # a CLI-level error reads better than a stack trace).
    if args.executor == "ai":
        missing = [
            ("--base_url", args.base_url),
            ("--api_key", args.api_key),
            ("--model", args.model),
            ("--provider", args.provider),
        ]
        missing_names = [name for name, value in missing if not value]
        if missing_names:
            print(
                f"--executor ai requires: {', '.join(missing_names)} "
                "(or set SWARM_BASE_URL / SWARM_API_KEY / SWARM_MODEL / SWARM_PROVIDER env vars)",
                file=sys.stderr,
            )
            return 2

    try:
        result = run_swarm(
            args.goal,
            args.repo,
            grains=grains,
            decomposer=decomposer,
            executor=args.executor,
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            provider=args.provider,
            max_iterations=args.max_iterations,
            concurrency=args.concurrency,
            apply_reversible=not args.no_self_update,
            claim_domains=not args.no_claim,
        )
    except OverlapError as exc:
        print(f"OVERLAP REJECTED — no grain ran:\n{exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
