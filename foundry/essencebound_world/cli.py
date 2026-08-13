"""Command-line entry point for the Essencebound specialist foundry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import build_data, validate_root
from .runtime_eval import evaluate_rung
from .report import build_final_report
from .training import run_training, training_preflight


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="needle-eb-world-architect")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-data", help="compile, generate, validate, and publish datasets")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    validate = sub.add_parser("validate", help="reload and validate a generated artifact tree")
    validate.add_argument("--root", type=Path, required=True)
    preflight = sub.add_parser("training-preflight", help="verify pinned artifacts and WSL2 CUDA")
    preflight.add_argument("--root", type=Path, required=True)
    preflight.add_argument("--repo-root", type=Path, default=Path.cwd())
    train = sub.add_parser("train-rung", help="train and export one validated rung")
    train.add_argument("--root", type=Path, required=True)
    train.add_argument("--repo-root", type=Path, default=Path.cwd())
    train.add_argument("--rung", type=int, choices=(250, 500, 1000, 2000, 4000), required=True)
    train.add_argument("--epochs", type=int, default=1)
    train.add_argument("--batch-size", type=int, default=8)
    train.add_argument("--lr", type=float, default=1e-4)
    train.add_argument("--lora-rank", type=int, default=16)
    evaluate = sub.add_parser("evaluate-rung", help="compare stock and tuned models, then apply gates")
    evaluate.add_argument("--root", type=Path, required=True)
    evaluate.add_argument("--repo-root", type=Path, default=Path.cwd())
    evaluate.add_argument("--rung", type=int, choices=(250, 500, 1000, 2000, 4000), required=True)
    evaluate.add_argument("--run-dir", type=Path)
    report = sub.add_parser(
        "final-report", aliases=["report"], help="write measured report and conditionally register"
    )
    report.add_argument("--root", type=Path, required=True)
    report.add_argument("--rung", type=int, choices=(250, 500, 1000, 2000, 4000))
    report.add_argument("--registry", type=Path)
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
    if args.command == "validate":
        report = validate_root(args.root)
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 2
    if args.command == "training-preflight":
        report = training_preflight(args.root, args.repo_root)
        print(json.dumps(report, indent=2))
        return 0 if report["passed"] else 2
    if args.command in {"final-report", "report"}:
        report = build_final_report(args.root, rung=args.rung, registry_path=args.registry)
        print(json.dumps(report, indent=2))
        return 0
    if args.command == "train-rung":
        result = run_training(
            root=args.root,
            repo_root=args.repo_root,
            rung=args.rung,
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            lora_rank=args.lora_rank,
        )
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "TRAINED_UNEVALUATED" else 2
    result = evaluate_rung(
        root=args.root, repo_root=args.repo_root, rung=args.rung, run_dir=args.run_dir
    )
    print(json.dumps(result, indent=2))
    return 0 if result["all_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
