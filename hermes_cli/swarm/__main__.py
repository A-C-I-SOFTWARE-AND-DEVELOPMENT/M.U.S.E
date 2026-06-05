"""CLI entry: ``python -m hermes_cli.swarm "<goal>" [--repo .] [--grains specs.json]``.

A thin, additive command surface over :func:`hermes_cli.swarm.coordinator.run_swarm`.
By default it runs the conservative ``PROMPT_ONLY`` executor — it partitions the
goal, proves the grains' file-domains disjoint, isolates each grain in a git
worktree, writes a Decision Ledger, and prints the result as JSON. It launches
no model and pushes nothing.
"""

from __future__ import annotations

import argparse
import json
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

    try:
        result = run_swarm(
            args.goal,
            args.repo,
            grains=grains,
            decomposer=decomposer,
            apply_reversible=not args.no_self_update,
            claim_domains=not args.no_claim,
        )
    except OverlapError as exc:
        print(f"OVERLAP REJECTED — no grain ran:\n{exc}", file=sys.stderr)
        return 1

    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
