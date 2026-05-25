"""Wave 0 placeholder entry point for `python -m hermes_cli.jarvis_prime`.

This is intentionally minimal. The full CLI surface (subcommands, modes,
router) is deferred to the Wave 1 lane `feature/jarvis-cli-expansion`
(see `docs/jarvis-prime-wave-plan.md`). The presence of this module is
only so that `python -m hermes_cli.jarvis_prime --help` returns a useful
status instead of a "package cannot be directly executed" traceback.
"""

from __future__ import annotations

import sys

from . import (
    OWNER_AUTHORIZATION_PHRASE,
    VALID_RISK_CLASSES,
    WorkPacket,
)


HELP_TEXT = """\
JARVIS Prime — Wave 0 foundation lock

This package currently exposes only the foundation surface:

  - WorkPacket dataclass            hermes_cli.jarvis_prime.WorkPacket
  - WorkPacketValidationFinding     hermes_cli.jarvis_prime.WorkPacketValidationFinding
  - Risk classes                    {risk_classes}
  - Owner authorization phrase      {phrase!r}

Subcommands (router, modes, gates, memory, awareness, tick) are
deferred to Wave 1. See docs/jarvis-prime-wave-plan.md for the build
plan and CANONICAL_REPO.md for owner-gated action rules.

Usage:
  python -m hermes_cli.jarvis_prime --help     Show this help
  python -m hermes_cli.jarvis_prime --version  Show package version
"""


def _print_help() -> int:
    print(
        HELP_TEXT.format(
            risk_classes=sorted(VALID_RISK_CLASSES),
            phrase=OWNER_AUTHORIZATION_PHRASE,
        )
    )
    return 0


def _print_version() -> int:
    print(f"JARVIS Prime foundation (Wave 0) — WorkPacket={WorkPacket.__name__}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help", "help"):
        return _print_help()
    if args[0] in ("-V", "--version", "version"):
        return _print_version()
    print(
        f"unknown argument: {args[0]!r}. Wave 0 only supports --help and --version.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
