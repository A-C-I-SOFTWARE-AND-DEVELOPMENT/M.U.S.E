#!/usr/bin/env python3
"""Run an LLM-backed live JARVIS self-audit + capability card (CI / manual).

Builds a model_invoke from the env-configured model bridge
(``SELF_AUDIT_MODEL_*``) or the generic ``HERMES_SELF_AUDIT_MODEL_CMD`` path,
runs the Constitution self-audit on the held-out core seeds, evaluates the
capability band, prints/writes the result as JSON, and — with ``--strict`` —
exits non-zero if the audit is blocked or the band is withheld.

Skips gracefully (exit 0) when no model is configured, so a scheduled or
opt-in CI job never fails for lack of credentials.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hermes_cli.jarvis_prime import capability_wall as cw
from hermes_cli.jarvis_prime.self_audit import (
    live,
    llm_judge,
    llm_target,
    model_bridge,
    run_report,
    select_seeds,
)


def resolve_invoke():
    """Prefer the env-configured OpenAI-compatible bridge, else the live hatch."""

    if model_bridge.is_configured():
        return model_bridge.complete
    return live.resolve_model_invoke()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="LLM-backed live JARVIS self-audit")
    parser.add_argument("--risk-class", dest="risk_class", default="RC3")
    parser.add_argument("--out", help="Write the JSON result to this path")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if the audit is blocked or the band is withheld",
    )
    args = parser.parse_args(argv)

    invoke = resolve_invoke()
    if invoke is None:
        print(
            "skipped: no model configured "
            "(set SELF_AUDIT_MODEL_* or HERMES_SELF_AUDIT_MODEL_CMD)"
        )
        return 0

    # The capability wall is held out on the core pool; the audit reuses it.
    report = run_report(
        select_seeds(pool="core"),
        llm_target(invoke),
        grader=llm_judge(invoke),
        run_id="ci_live",
    )
    wall = cw.evaluate(report, args.risk_class)
    result = {
        "audit": report.summary_payload(),
        "capability_card": wall.capability_card(),
    }
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")

    blocked = report.overall_verdict == "blocked"
    withheld = not wall.passed
    if args.strict and (blocked or withheld):
        print(
            f"::error::live self-audit failed (blocked={blocked}, withheld={withheld})",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
