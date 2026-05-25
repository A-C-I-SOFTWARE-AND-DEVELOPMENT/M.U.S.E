"""Minimal module entrypoint for ``python -m hermes_cli.jarvis_prime``.

Wave 0 does **not** implement the CLI surface — that lands on the
``feature/jarvis-cli`` lane in Wave 1. This module exists only so the
foundation-lock verification step
(``python -m hermes_cli.jarvis_prime --help``) has something to invoke
without a runtime stack. It is stdlib-only, prints a short status
summary, and exits cleanly.
"""

from __future__ import annotations

import argparse
import sys

from . import (
    OWNER_AUTHORIZATION_PHRASE,
    VALID_RISK_CLASSES,
    WorkPacket,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m hermes_cli.jarvis_prime",
        description=(
            "JARVIS Prime — foundation lock (Wave 0). "
            "The full CLI surface is added in Wave 1 on its dedicated "
            "feature branch. This entrypoint exists so the Wave 0 "
            "verification command has something to invoke."
        ),
        epilog=(
            "See CANONICAL_REPO.md and docs/jarvis-prime-wave-plan.md "
            "for the canonical repo declaration and the wave build "
            "strategy."
        ),
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print a short status summary for the JARVIS Prime package.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.status:
        print("JARVIS Prime — Wave 0 (foundation lock)")
        print(f"  WorkPacket: {WorkPacket.__module__}.{WorkPacket.__name__}")
        print(f"  Risk classes: {', '.join(VALID_RISK_CLASSES)}")
        print(f"  Owner authorization phrase: {OWNER_AUTHORIZATION_PHRASE!r}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
