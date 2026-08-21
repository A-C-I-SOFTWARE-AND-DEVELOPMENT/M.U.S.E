#!/usr/bin/env python3
"""Command-line precheck over a benchmark results file.


    python -m tools.grading.cli results.jsonl
    python -m tools.grading.cli results.jsonl --json report.json
    python -m tools.grading.cli --answer 17000 --gold 17

The input shape is the one ``benchmarks/gaia_runner.py`` already writes:
``{"task_id", "question", "level", "model_answer", "gold_answer", ...}``.  Two
optional per-row fields are honoured if present and simply absent otherwise:
``unit_hint`` and ``date_order``.

Exit codes
----------
``0``  every row is decidable and the incumbent grader agrees.
``1``  the incumbent grader disagrees with the validator on at least one row —
       a recorded score is wrong in one direction or the other.
``2``  at least one row is ``ambiguous_unit``: the benchmark row does not say
       what unit its gold field is in, so it cannot be graded either way.
       This is reported, never resolved.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Sequence

from .validator import (
    GradingContext,
    OutputNormalizationValidator,
    ValidationReport,
    Verdict,
)


def _load_jsonl(path: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno}: not valid JSON ({exc})") from exc
            if not isinstance(parsed, dict):
                raise SystemExit(f"{path}:{lineno}: expected a JSON object")
            rows.append(parsed)
    return rows


def _load(path: Path) -> List[Dict[str, object]]:
    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            payload = payload.get("results", [])
        if not isinstance(payload, list):
            raise SystemExit(f"{path}: expected a list of result objects")
        return [row for row in payload if isinstance(row, dict)]
    return _load_jsonl(path)


def _exit_code(report: ValidationReport) -> int:
    if report.ambiguous:
        return 2
    if any(r.is_grading_defect for r in report.results):
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.grading.cli",
        description=(
            "Normalize benchmark answers and interpret units BEFORE grading. "
            "Reports match / mismatch / ambiguous_unit; never resolves an "
            "ambiguity on the task's behalf."
        ),
    )
    parser.add_argument("results", nargs="?", type=Path, help="results.jsonl or .json")
    parser.add_argument("--answer", help="single answer to check (with --gold)")
    parser.add_argument("--gold", help="single gold field to check against")
    parser.add_argument("--question", default="", help="question text for --answer mode")
    parser.add_argument("--unit-hint", default=None, help="declared unit for the gold field")
    parser.add_argument("--date-order", default=None, choices=[None, "MDY", "DMY"])
    parser.add_argument("--json", type=Path, default=None, help="write the report here")
    parser.add_argument(
        "--only-defects",
        action="store_true",
        help="print only the rows a human has to look at",
    )
    args = parser.parse_args(argv)

    validator = OutputNormalizationValidator()

    if args.answer is not None or args.gold is not None:
        if args.answer is None or args.gold is None:
            parser.error("--answer and --gold must be given together")
        context = GradingContext(
            question=args.question,
            unit_hint=args.unit_hint,
            date_order=args.date_order,
        )
        result = validator.validate(args.answer, args.gold, context)
        print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
        if result.verdict is Verdict.AMBIGUOUS_UNIT:
            return 2
        return 1 if result.is_grading_defect else 0

    if args.results is None:
        parser.error("give a results file, or --answer with --gold")
    if not args.results.exists():
        raise SystemExit(f"no such file: {args.results}")

    report = validator.validate_records(_load(args.results))

    if args.only_defects:
        for result in report.defects:
            print(json.dumps(result.as_dict(), ensure_ascii=False))
    else:
        print(report.render())

    if args.json is not None:
        payload = {
            "summary": report.summary(),
            "results": [r.as_dict() for r in report.results],
        }
        args.json.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    return _exit_code(report)


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess
    sys.exit(main())
