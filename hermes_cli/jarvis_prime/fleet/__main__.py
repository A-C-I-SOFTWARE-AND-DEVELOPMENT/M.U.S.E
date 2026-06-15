"""CLI for the Nero-Fleet Admiralty registry."""

from __future__ import annotations

import argparse
import json
import sys

from hermes_cli.jarvis_prime.fleet.registry import get_registry
from hermes_cli.jarvis_prime.fleet.solar_map import solar_system_view


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nero-Fleet Admiralty telemetry")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Print fleet command node snapshot (JSON)")

    solar_p = sub.add_parser("solar", help="Print Nero Solar System view (JSON)")
    solar_p.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON",
    )

    args = parser.parse_args(argv)

    if args.cmd == "status":
        data = get_registry().snapshot()
        print(json.dumps(data, indent=2))
        return 0

    if args.cmd == "solar":
        reg = get_registry()
        data = solar_system_view(reg.snapshot())
        indent = 2 if args.pretty else None
        print(json.dumps(data, indent=indent))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
