#!/usr/bin/env python3
"""Run every registered benchmark lane and gate the result through the ratchet.

This CLI is the *one-command wire-up* of the four MUSE benchmark runners
(``benchmarks/gaia_runner.py``, ``benchmarks/terminal_bench_runner.py``,
``benchmarks/polyglot_runner.py``, ``mini_swe_runner.py``) with the
:func:`research_fabric.validators.evaluate_ratchet` strict non-regression
wall. It is the entry point the research fabric uses to ask: *does a
challenger model pass the ABSOLUTE_FLOOR=0.80 gate on every required
domain?*

Pipeline
========

For each runner:

1. Invoke the runner with the supplied ``--limit`` (and any other forwarded
   flags). Each runner writes its per-task rows to ``results.jsonl`` in
   the runner's own output directory.
2. Resolve the runner's domain from
   :data:`research_fabric.catalog.DOMAIN_VERIFIERS`.
3. Call ``verifier.get_verifier(domain).verify(run_dir)`` to get a
   :class:`verifier.DomainScore` in [0, 1].
4. Feed the per-domain scores into :func:`evaluate_ratchet` and print the
   verdict.

``--dry_run`` proves the wiring is sound without firing any LLM calls:
it imports every runner module, instantiates the class (where cheap),
prints the exact command that *would* be invoked, and runs the ratchet
against a synthetic ``results.jsonl`` so the full gate logic is exercised.

Usage
=====

Real run (requires API keys; ~minutes per task):

    python run_all_benchmarks.py --limit 5 --model kimi-k3 \\
        --base_url https://api.kimi.com/coding/v1

Dry run (no API calls, proves import + wiring):

    python run_all_benchmarks.py --limit 1 --dry_run

Show what would run without doing it:

    python run_all_benchmarks.py --limit 5 --dry_run --show_commands

Exit code is 0 iff the ratchet verdict ``passed == True``; otherwise 1.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

# Make sure repo root is on sys.path so this file is runnable from anywhere
# (``python run_all_benchmarks.py ...`` and ``python -m run_all_benchmarks``).
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Runner registry
# ---------------------------------------------------------------------------

# Each entry: (runner_module, runner_attr_for_output_dir, domain_key,
# extra_argv_factory). Kept as a list of dataclasses so the CLI can both
# invoke real runners (--no-dry-run) and short-circuit (--dry-run) with
# consistent per-runner info.


@dataclass(frozen=True)
class RunnerSpec:
    """How to invoke one benchmark runner and where to grade it."""

    name: str                            # short label, used for log lines
    domain: str                          # a key in catalog.DOMAIN_VERIFIERS
    module: str                          # importable module path
    # Function that builds the argv list for `python -m <module> ...`.
    build_argv: Callable[["RunConfig"], list[str]]
    # Subdirectory of the runner's CWD where ``results.jsonl`` lands. The
    # runner is invoked with CWD = ``run_root / name``, so this is usually
    # ``"."`` (the runner writes ``results.jsonl`` next to itself).
    results_subdir: str = "."


@dataclass(frozen=True)
class RunConfig:
    """Resolved CLI args shared by every runner invocation."""

    limit: Optional[int]
    model: str
    base_url: Optional[str]
    env: str
    output_root: Path
    verbose: bool
    dry_run: bool
    show_commands: bool
    extra_argv: tuple[str, ...] = ()


def _gaia_argv(cfg: RunConfig) -> list[str]:
    argv = [
        "gaia_runner",
        f"--limit={cfg.limit}" if cfg.limit is not None else "--limit=0",
        f"--model={cfg.model}",
        f"--env={cfg.env}",
        "--output_file=results.jsonl",
    ]
    if cfg.base_url:
        argv.append(f"--base_url={cfg.base_url}")
    if cfg.verbose:
        argv.append("--verbose=True")
    argv.extend(cfg.extra_argv)
    return argv


def _terminal_bench_argv(cfg: RunConfig) -> list[str]:
    argv = [
        "terminal_bench_runner",
        f"--limit={cfg.limit}" if cfg.limit is not None else "--limit=0",
        f"--model={cfg.model}",
        f"--env={cfg.env}",
        "--output=results.jsonl",
    ]
    if cfg.base_url:
        argv.append(f"--base_url={cfg.base_url}")
    if cfg.verbose:
        argv.append("--verbose=True")
    argv.extend(cfg.extra_argv)
    return argv


def _polyglot_argv(cfg: RunConfig) -> list[str]:
    argv = [
        "polyglot_runner",
        f"--limit={cfg.limit}" if cfg.limit is not None else "--limit=0",
        f"--model={cfg.model}",
        f"--env={cfg.env}",
        "--output_file=results.jsonl",
    ]
    if cfg.base_url:
        argv.append(f"--base_url={cfg.base_url}")
    if cfg.verbose:
        argv.append("--verbose=True")
    argv.extend(cfg.extra_argv)
    return argv


def _mini_swe_argv(cfg: RunConfig) -> list[str]:
    # mini_swe_runner lives at the repo root (not under benchmarks/), so it
    # is invoked as a script by absolute path rather than via -m. We use the
    # in-process MiniSWERunner.run_batch path below to keep it uniform.
    argv = [
        str(REPO_ROOT / "mini_swe_runner.py"),
        f"--model={cfg.model}",
        "--output_file=results.jsonl",
        f"--env={cfg.env}",
    ]
    if cfg.base_url:
        argv.append(f"--base_url={cfg.base_url}")
    if cfg.verbose:
        argv.append("--verbose=True")
    argv.extend(cfg.extra_argv)
    return argv


# mini_swe is wired to ``software_development`` is left to a separate SWE
# lane (repo-scale issue resolution). It does not currently have a
# results.jsonl-format verifier in the same shape as the other three; the
# ratchet call for ``software_development`` therefore comes from
# ``terminal_bench`` (the closest match in the registered set) and mini_swe
# is run for diagnostic purposes, not ratchet input. We keep it in the list
# because the task explicitly asked for "all three runners + mini_swe_runner".

RUNNERS: tuple[RunnerSpec, ...] = (
    RunnerSpec(
        name="gaia",
        domain="reasoning",
        module="benchmarks.gaia_runner",
        build_argv=_gaia_argv,
    ),
    RunnerSpec(
        name="terminal_bench",
        domain="software_development",
        module="benchmarks.terminal_bench_runner",
        build_argv=_terminal_bench_argv,
    ),
    RunnerSpec(
        name="polyglot",
        domain="code_editing",
        module="benchmarks.polyglot_runner",
        build_argv=_polyglot_argv,
    ),
    RunnerSpec(
        name="mini_swe",
        # mini_swe is the repo-scale SWE lane; it does not currently write
        # ``results.jsonl`` in the same shape the new verifiers consume, so
        # we leave it diagnostic-only (no ratchet domain assigned). The
        # string here is a sentinel for the dry-run path; it would be
        # replaced with a real mapping if/when a mini_swe JSONL verifier
        # is added.
        domain="software_development_diagnostic",
        module="__script__:mini_swe_runner.py",
        build_argv=_mini_swe_argv,
    ),
)


# ---------------------------------------------------------------------------
# Runner invocation
# ---------------------------------------------------------------------------


def _run_subprocess(spec: RunnerSpec, argv: list[str], cwd: Path) -> int:
    """Invoke ``python -m <module> <argv>`` (or a script) and stream output."""

    if spec.module.startswith("__script__:"):
        # mini_swe_runner.py is a top-level script, not a package module.
        script_path = spec.module.split(":", 1)[1]
        cmd = [sys.executable, script_path, *argv]
    else:
        cmd = [sys.executable, "-m", spec.module, *argv]
    print(f"\n>>> {' '.join(cmd)}  (cwd={cwd})")
    if not cmd:
        return 0
    proc = subprocess.run(cmd, cwd=str(cwd))
    return proc.returncode


def _write_synthetic_results(run_dir: Path, score: float) -> None:
    """Write a 10-row ``results.jsonl`` whose fraction-of-correct matches ``score``.

    Used by ``--dry_run`` so the verifier and ratchet paths are exercised
    end-to-end without invoking the LLM-backed runners.
    """

    n = 10
    n_pass = int(round(score * n))
    rows: list[dict[str, Any]] = []
    for i in range(n):
        rows.append({
            "task_id": f"synthetic-{i}",
            "level": 1,
            "correct": i < n_pass,
            "model_answer": "ok" if i < n_pass else "no",
            "gold_answer": "ok",
        })
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "results.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Ratchet invocation
# ---------------------------------------------------------------------------


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_all_benchmarks",
        description=(
            "Run every registered benchmark lane and gate the result "
            "through the research_fabric ratchet."
        ),
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap on tasks per runner (default: 5). 0 = all tasks.",
    )
    p.add_argument(
        "--model",
        type=str,
        default=os.environ.get("MUSE_CHALLENGER_MODEL", "kimi-k3"),
        help=(
            "Challenger model id (default: $MUSE_CHALLENGER_MODEL or kimi-k3). "
            "The ratchet asks: does THIS model clear ABSOLUTE_FLOOR=0.80 on "
            "every required domain?"
        ),
    )
    p.add_argument(
        "--base_url",
        type=str,
        default=os.environ.get("MUSE_BASE_URL", "https://api.kimi.com/coding/v1"),
        help="OpenAI-compatible base URL (default: $MUSE_BASE_URL or kimi).",
    )
    p.add_argument(
        "--env",
        type=str,
        default="local",
        choices=("local", "docker", "modal"),
        help="Execution environment for the runners (default: local).",
    )
    p.add_argument(
        "--output_root",
        type=str,
        default=None,
        help=(
            "Parent directory for per-runner results.jsonl files. "
            "Default: a fresh temp dir."
        ),
    )
    p.add_argument(
        "--dry_run",
        action="store_true",
        help=(
            "Skip real LLM calls; write synthetic results.jsonl with the "
            "provided --synthetic_score (default 0.85) and exercise the "
            "verifier + ratchet paths end-to-end."
        ),
    )
    p.add_argument(
        "--show_commands",
        action="store_true",
        help="Print the exact subprocess command for each runner and exit.",
    )
    p.add_argument(
        "--synthetic_score",
        type=float,
        default=0.85,
        help=(
            "Per-runner correctness in [0, 1] for the synthetic results.jsonl "
            "written by --dry_run (default: 0.85, comfortably above the 0.80 "
            "absolute floor)."
        ),
    )
    p.add_argument(
        "--holdout",
        type=str,
        default=None,
        help=(
            "Optional path to a JSON object of {domain: score} held-out "
            "scores; forwarded to evaluate_ratchet. Required for a warm "
            "ratchet call (one with a champion)."
        ),
    )
    p.add_argument(
        "--safety",
        type=str,
        default=None,
        help=(
            "Optional JSON object of {name: count} safety counts "
            "(bad-when-higher) for the challenger; forwarded to evaluate_ratchet."
        ),
    )
    p.add_argument(
        "--eval_win_rate",
        type=float,
        default=None,
        help="Optional head-to-head win-rate; needed for a warm ratchet call.",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Forward --verbose=True to every runner.",
    )
    return p


def _parse_holdout_or_safety(path: Optional[str], label: str) -> dict[str, float]:
    if not path:
        return {}
    p = Path(path)
    if not p.is_file():
        print(f"warning: --{label} file not found: {p}", file=sys.stderr)
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"warning: --{label} file is not valid JSON: {e}", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        print(f"warning: --{label} JSON must be an object, got {type(data).__name__}", file=sys.stderr)
        return {}
    out: dict[str, float] = {}
    for k, v in data.items():
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            print(f"warning: --{label} entry {k!r}={v!r} is not numeric; skipped", file=sys.stderr)
    return out


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_argparser().parse_args(argv)

    # If --limit is None we still want a small default for the dry-run path
    # (so synthetic results.jsonl has a sensible "limit" attribute on the
    # CLI surface, matching what a real call would do).
    if args.limit is None and args.dry_run:
        args.limit = 1

    if not 0.0 <= args.synthetic_score <= 1.0:
        print(
            f"error: --synthetic_score must be in [0, 1], got {args.synthetic_score}",
            file=sys.stderr,
        )
        return 2

    # ---- output root -----------------------------------------------------
    if args.output_root:
        output_root = Path(args.output_root).resolve()
        output_root.mkdir(parents=True, exist_ok=True)
    else:
        # mkdtemp so a missing --output_root never pollutes the repo.
        output_root = Path(tempfile.mkdtemp(prefix="muse_all_bench_"))
    print(f"output_root: {output_root}")

    cfg = RunConfig(
        limit=args.limit,
        model=args.model,
        base_url=args.base_url,
        env=args.env,
        output_root=output_root,
        verbose=args.verbose,
        dry_run=args.dry_run,
        show_commands=args.show_commands,
        extra_argv=tuple(args.verbose and ["--verbose=True"] or []),
    )

    # ---- (1) exercise imports + (2) per-runner invocation ----------------
    domain_scores: dict[str, float] = {}
    runner_reports: list[dict[str, Any]] = []

    # Import-time smoke check: prove every runner module can be imported
    # (this is the cheap check the task explicitly asks for).
    print("\n[1/3] Verifying all runner modules import cleanly ...")
    for spec in RUNNERS:
        if spec.module.startswith("__script__:"):
            script_path = REPO_ROOT / spec.module.split(":", 1)[1]
            if not script_path.is_file():
                print(f"  FAIL  {spec.name}: script not found at {script_path}")
                return 1
            print(f"  ok    {spec.name}: script at {script_path.name}")
        else:
            try:
                __import__(spec.module)
                print(f"  ok    {spec.name}: imported {spec.module}")
            except Exception as e:
                print(f"  FAIL  {spec.name}: import error: {e}")
                if args.verbose:
                    traceback.print_exc()
                return 1

    # Sanity check: the catalog knows a verifier for each (non-diagnostic)
    # runner domain. Fail loud if a domain is missing — that means somebody
    # added a runner without registering its verifier in catalog.
    from hermes_cli.jarvis_prime.research_fabric.catalog import (
        ABSOLUTE_FLOOR,
        DOMAIN_VERIFIERS,
    )
    from hermes_cli.jarvis_prime.research_fabric.verifier import (
        DomainScore,
        get_verifier,
        verifier_domains,
    )
    print(f"\n  catalog.REQUIRED_DOMAINS       : {list(__import__('hermes_cli.jarvis_prime.research_fabric.catalog', fromlist=['REQUIRED_DOMAINS']).REQUIRED_DOMAINS)}")
    print(f"  catalog.ABSOLUTE_FLOOR         : {ABSOLUTE_FLOOR}")
    print(f"  catalog.DOMAIN_VERIFIERS keys  : {sorted(DOMAIN_VERIFIERS.keys())}")
    print(f"  verifier.verifier_domains()    : {sorted(verifier_domains())}")

    if args.show_commands:
        print("\n[2/3] --show_commands: would invoke (no execution) ...")
        for spec in RUNNERS:
            runner_cwd = output_root / spec.name
            runner_cwd.mkdir(parents=True, exist_ok=True)
            argv_list = spec.build_argv(cfg)
            if spec.module.startswith("__script__:"):
                script_path = spec.module.split(":", 1)[1]
                cmd = [sys.executable, script_path, *argv_list]
            else:
                cmd = [sys.executable, "-m", spec.module, *argv_list]
            print(f"  {spec.name:>14s}  (cwd={runner_cwd}):")
            print(f"    {' '.join(cmd)}")
        print("\n(show_commands: exiting without running the ratchet.)")
        return 0

    # ---- (2) run each runner + grade its results.jsonl --------------------
    print(f"\n[2/3] Running {len(RUNNERS)} benchmark runner(s) "
          f"(dry_run={args.dry_run}) ...")
    for spec in RUNNERS:
        runner_cwd = output_root / spec.name
        runner_cwd.mkdir(parents=True, exist_ok=True)
        argv_list = spec.build_argv(cfg)

        if args.dry_run:
            # Skip the subprocess; just write the synthetic results.jsonl
            # and grade it. This is the contract the task asks for: prove
            # the wiring without firing any LLM calls.
            print(f"\n  {spec.name}: [dry-run] writing synthetic results.jsonl "
                  f"(score={args.synthetic_score}) at {runner_cwd}")
            _write_synthetic_results(runner_cwd, score=args.synthetic_score)
        else:
            rc = _run_subprocess(spec, argv_list, runner_cwd)
            if rc != 0:
                print(f"  {spec.name}: runner exited with code {rc}; continuing "
                      "to grade whatever results.jsonl it left behind.")

        # Grade the runner's results.jsonl. For diagnostic-only runners
        # (mini_swe today), skip the verifier call: the catalog has no
        # mapping for them, and the ratchet would just record a missing
        # domain.
        if spec.domain.endswith("_diagnostic"):
            print(f"  {spec.name}: diagnostic-only (no ratchet mapping); skipping verifier.")
            runner_reports.append({
                "name": spec.name,
                "domain": None,
                "verifier": None,
                "run_dir": str(runner_cwd),
                "score": None,
                "ran": None,
                "detail": "diagnostic-only runner; not consumed by ratchet",
            })
            continue

        verify = get_verifier(spec.domain)
        score: DomainScore = verify(runner_cwd)
        print(f"  {spec.name}: domain={spec.domain}  "
              f"correctness={score.correctness:.4f}  ran={score.ran}  "
              f"accepted={score.accepted}")
        print(f"             {score.detail}")
        domain_scores[spec.domain] = float(score.correctness)
        runner_reports.append({
            "name": spec.name,
            "domain": spec.domain,
            "verifier": f"{verify.__module__}:{verify.__name__}",
            "run_dir": str(runner_cwd),
            "correctness": score.correctness,
            "ran": score.ran,
            "accepted": score.accepted,
            "detail": score.detail,
        })

    # ---- (3) ratchet -----------------------------------------------------
    print(f"\n[3/3] Evaluating ratchet (ABSOLUTE_FLOOR={ABSOLUTE_FLOOR}) ...")
    from hermes_cli.jarvis_prime.research_fabric.validators import evaluate_ratchet
    from hermes_cli.jarvis_prime.research_fabric.catalog import (
        REQUIRED_DOMAINS,
        COMPOSITE_MARGIN,
        EVAL_WIN_MARGIN,
    )

    holdout = _parse_holdout_or_safety(args.holdout, "holdout")
    safety = _parse_holdout_or_safety(args.safety, "safety")
    eval_win_rate = args.eval_win_rate

    verdict = evaluate_ratchet(
        champion_domain_scores=None,   # cold start: no champion to beat
        candidate_domain_scores=domain_scores,
        holdout_scores=holdout or None,
        candidate_safety_counts=safety or None,
        eval_win_rate=eval_win_rate,
    )

    summary = {
        "model": args.model,
        "dry_run": args.dry_run,
        "limit": args.limit,
        "abs_floor": ABSOLUTE_FLOOR,
        "composite_margin": COMPOSITE_MARGIN,
        "eval_win_margin": EVAL_WIN_MARGIN,
        "required_domains": list(REQUIRED_DOMAINS),
        "domain_scores": domain_scores,
        "runners": runner_reports,
        "ratchet": verdict.to_dict(),
    }
    print("\n" + json.dumps(summary, indent=2, sort_keys=True))

    if verdict.passed:
        print(f"\nRATCHET PASSED: {args.model} clears ABSOLUTE_FLOOR={ABSOLUTE_FLOOR} "
              f"on every required domain.")
        return 0
    print(f"\nRATCHET FAILED: {args.model} did not clear the floor. "
          f"Reasons: {verdict.reasons}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
