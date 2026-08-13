"""Command-line entry point for the Essencebound specialist foundry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import build_data, validate_root


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="needle-eb-world-architect")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-data", help="compile, generate, validate, and publish datasets")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    validate = sub.add_parser("validate", help="reload and validate a generated artifact tree")
    validate.add_argument("--root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build-data":
        result = build_data(args.source, args.output)
        summary = {
            "requirements": result["requirements"],
            "dataset_hash": result["dataset_hash"],
            "validation_passed": result["validation"]["passed"],
            "output": str(args.output.resolve()),
        }
        print(json.dumps(summary, indent=2))
        return 0
    report = validate_root(args.root)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
