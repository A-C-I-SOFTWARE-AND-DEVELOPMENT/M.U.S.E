"""``python -m hermes_cli.jarvis_prime`` entry point.

Wave 0 deliberately ships no real CLI surface (CLI expansion is a
Wave 1 lane). This module exists so that ``python -m
hermes_cli.jarvis_prime --help`` returns a useful banner instead of
crashing with "package cannot be directly executed", and so that
contributors discovering the package learn where the real surface
will land.
"""

from __future__ import annotations

import argparse
import sys

from hermes_cli.jarvis_prime import (
    OWNER_AUTHORIZATION_PHRASE,
    RISK_CLASSES,
    WorkPacket,
)


_BANNER = """\
JARVIS Prime (Wave 0 foundation)

This package currently exposes the standard WorkPacket data model and
its validation findings type. The runtime, mode router, gates, owner
auth, memory, research, epistemics, self-update, awareness, and tick
subsystems are scheduled for Wave 1 lanes — see
docs/jarvis-prime-wave-plan.md.

Available now:
  - hermes_cli.jarvis_prime.WorkPacket
  - hermes_cli.jarvis_prime.WorkPacketValidationFinding
  - hermes_cli.jarvis_prime.RISK_CLASSES
  - hermes_cli.jarvis_prime.OWNER_AUTHORIZATION_PHRASE
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m hermes_cli.jarvis_prime",
        description=(
            "JARVIS Prime foundation entry point. Wave 0 ships data "
            "model + validation only; a real CLI lands in Wave 1."
        ),
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print foundation status and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print("hermes_cli.jarvis_prime: Wave 0 foundation")
        print(f"  WorkPacket fields: {len(WorkPacket().to_dict())}")
        print(f"  risk classes: {', '.join(RISK_CLASSES)}")
        print(f"  owner authorization phrase: {OWNER_AUTHORIZATION_PHRASE!r}")
        return 0

    sys.stdout.write(_BANNER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
