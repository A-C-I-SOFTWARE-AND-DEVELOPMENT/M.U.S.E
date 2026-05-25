"""Wave 0 entry point for ``python -m hermes_cli.jarvis_prime``.

This module exists so the foundation lock can be verified end-to-end
without committing to a full CLI surface yet. Later waves (CLI
expansion, runtime enforcement) will replace this with a real
dispatcher. For now it prints a status banner describing what is
available and exits 0 on ``--help``.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import (
    REQUIRED_FIELDS,
    VALID_RISK_CLASSES,
    WorkPacket,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hermes_cli.jarvis_prime",
        description=(
            "JARVIS Prime Wave 0 foundation. Only the WorkPacket schema "
            "is wired up at this stage. Runtime, router, gates, memory, "
            "research, epistemics, self-update, awareness, and tick "
            "modules ship in later waves."
        ),
    )
    parser.add_argument(
        "--schema",
        action="store_true",
        help="Print the WorkPacket schema fields and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.schema:
        empty = WorkPacket()
        payload = {
            "required_fields": list(REQUIRED_FIELDS),
            "valid_risk_classes": list(VALID_RISK_CLASSES),
            "fields": sorted(empty.to_dict().keys()),
        }
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    sys.stdout.write(
        "JARVIS Prime: Wave 0 foundation lock. "
        "Use --help for options, --schema to inspect the WorkPacket schema.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
