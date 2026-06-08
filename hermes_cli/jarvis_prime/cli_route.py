"""``route`` subcommand for ``python -m hermes_cli.jarvis_prime``.

Extracted verbatim from ``__main__.py`` as a behavior-preserving relocation
seam: the parser setup and handler are physically moved here and re-wired by
``__main__`` via :func:`add_route_parser`. Nothing about the ``route``
subcommand's behavior, flags, output, or exit codes changes.

The ``route`` subcommand explains the evidence-backed model route for a task
class (or all task classes). It is read-only and network-free; the real
routing decisions come from :mod:`hermes_cli.jarvis_prime.task_router`.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def cmd_route(args: argparse.Namespace) -> int:
    """Explain the evidence-backed model route for a task class."""
    from hermes_cli.jarvis_prime import task_router as tr

    if getattr(args, "task", None):
        try:
            decision = tr.route_for_task(args.task)
        except ValueError as exc:
            print(
                f"error: {exc}. Known task classes: "
                + ", ".join(t.value for t in tr.TaskClass),
                file=sys.stderr,
            )
            return 2
        if args.json:
            _print_json(decision.to_dict())
        else:
            print(tr.explain(decision))
        return 0

    decisions = tr.all_routes()
    if args.json:
        _print_json([d.to_dict() for d in decisions])
    else:
        print("\n\n".join(tr.explain(d) for d in decisions))
    return 0


def add_route_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Register the ``route`` subcommand on ``subparsers``.

    Wires the parser and its ``func`` default exactly as ``__main__`` did
    inline, so ``python -m hermes_cli.jarvis_prime route ...`` behaves
    byte-identically.
    """
    p_route = subparsers.add_parser(
        "route",
        help="Explain the evidence-backed model route for a task class",
        epilog=(
            "Hosted task-class routing is ON by default; disable it (restore "
            "bare provider ids) with HERMES_JARVIS_HOSTED_TASKCLASS=0."
        ),
    )
    p_route.add_argument(
        "--task",
        help="Task class (e.g. coding_build); omit to show all task classes",
    )
    p_route.add_argument("--json", action="store_true")
    p_route.set_defaults(func=cmd_route)
    return p_route
