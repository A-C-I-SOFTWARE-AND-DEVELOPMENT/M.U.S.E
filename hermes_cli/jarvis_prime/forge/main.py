"""Standalone Forge CLI (delegated from ``hermes_cli.jarvis_prime``).

Usage: ``python -m hermes_cli.jarvis_prime forge <subcommand> ...`` or
directly via :func:`cli_main`. Ships a built-in demo task (``alg_sum``) so
tournaments run end-to-end offline; exit code 1 signals a refusal
(unresolved lookup, failed verification), 2 a usage/input error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

from hermes_cli.jarvis_prime.guardrail_evidence import EvidenceArtifact, GuardrailLedger
from hermes_cli.jarvis_prime.research_fabric.verifier.algorithms import (
    AlgorithmCase,
    AlgorithmTask,
)

from . import ForgeError
from .leaderboard import anchor_leaderboard, lookup_standing, standings, verify_anchor
from .map_elites import ElitesGrid
from .registry import CandidateRecord, CandidateRegistry
from .tournament import RatingBook, TournamentReport, judge_duel, run_tournament

# Built-in demo task so every subcommand works offline out of the box.
DEMO_TASK = AlgorithmTask(
    task_id="alg_sum",
    entrypoint="solve",
    prompt="Sum a list of integers; solve(xs) -> int.",
    public_cases=(AlgorithmCase([[1, 2, 3]], 6), AlgorithmCase([[10]], 10)),
    holdout_cases=(
        AlgorithmCase([[4, 5]], 9),
        AlgorithmCase([[]], 0),
        AlgorithmCase([[-1, 1, 7]], 7),
    ),
)

TASKS: dict[str, AlgorithmTask] = {DEMO_TASK.task_id: DEMO_TASK}


def _task(task_id: str) -> AlgorithmTask:
    task = TASKS.get(task_id)
    if task is None:
        raise ForgeError(
            f"unknown task {task_id!r}; built-in tasks: {', '.join(sorted(TASKS))}"
        )
    return task


def _emit(data: Any, as_json: bool = True) -> None:
    print(json.dumps(data, indent=2, sort_keys=True, default=str) if as_json else data)


def _cmd_register(args: argparse.Namespace) -> int:
    code = Path(args.code_file).read_text(encoding="utf-8")
    registry = CandidateRegistry(ledger=GuardrailLedger())
    try:
        record = registry.register(
            CandidateRecord.build(
                code=code, task_id=args.task, contributor_id=args.contributor
            )
        )
    except ForgeError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    _emit({"candidate_id": record.candidate_id, "payload_sha256": record.payload_sha256})
    return 0


def _cmd_lookup(args: argparse.Namespace) -> int:
    registry = CandidateRegistry()
    book = RatingBook()
    try:
        if args.hash:
            record = registry.lookup_by_hash(args.hash)
            if record is None:
                print(f"unresolved: no candidate with hash {args.hash}", file=sys.stderr)
                return 1
            candidate_id = record.candidate_id
        else:
            candidate_id = args.candidate_id
        _emit(lookup_standing(candidate_id, book, registry))
    except ForgeError as exc:
        print(f"unresolved: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_candidates(_args: argparse.Namespace) -> int:
    registry = CandidateRegistry()
    _emit(
        [
            {
                "candidate_id": r.candidate_id,
                "task_id": r.task_id,
                "contributor_id": r.contributor_id,
                "payload_sha256": r.payload_sha256,
            }
            for r in registry.all()
        ]
    )
    return 0


def _cmd_duel(args: argparse.Namespace) -> int:
    registry = CandidateRegistry()
    ledger = GuardrailLedger()
    try:
        task = _task(args.task)
        a = registry.resolve(args.a)
        b = registry.resolve(args.b)
    except ForgeError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    duel = judge_duel(task, a, b)
    ledger.append("forge_duel", duel.duel_id, duel.to_dict())
    _emit(duel.to_dict())
    return 0


def _cmd_tournament(args: argparse.Namespace) -> int:
    import random

    registry = CandidateRegistry()
    try:
        task = _task(args.task)
    except ForgeError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    report = run_tournament(
        task,
        registry,
        rounds=args.rounds,
        rating_book=RatingBook(),
        elites=ElitesGrid(ledger=GuardrailLedger()),
        ledger=GuardrailLedger(),
        rng=random.Random(args.seed),
    )
    if args.out:
        Path(args.out).write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
        print(f"wrote {args.out} ({len(report.duels)} duels)")
    else:
        _emit(report.to_dict())
    return 0


def _cmd_ratings(_args: argparse.Namespace) -> int:
    book = RatingBook()
    _emit({cid: r.to_dict() for cid, r in book.all().items()})
    return 0


def _cmd_elites(_args: argparse.Namespace) -> int:
    grid = ElitesGrid()
    _emit(
        {
            "coverage": round(grid.coverage(), 4),
            "qd_score": round(grid.qd_score(), 4),
            "cells": [c.to_dict() for c in grid.cells()],
        }
    )
    return 0


def _cmd_leaderboard(_args: argparse.Namespace) -> int:
    _emit([s.to_dict() for s in standings(RatingBook(), CandidateRegistry())])
    return 0


def _cmd_anchor(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.federation.identity import load_identity

    identity = load_identity()
    artifact = anchor_leaderboard(
        RatingBook(),
        CandidateRegistry(),
        node_id=identity.node_id if identity else "",
        ledger=GuardrailLedger(),
    )
    if args.out:
        Path(args.out).write_text(
            json.dumps(artifact.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
        )
        print(f"wrote {args.out} (merkle_root={artifact.payload['merkle_root']})")
    else:
        _emit(artifact.to_dict())
    return 0


def _cmd_verify_anchor(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    artifact = EvidenceArtifact.from_dict(data)
    ok = verify_anchor(artifact)
    print("anchor verified" if ok else "ANCHOR INVALID — payload or root mismatch")
    return 0 if ok else 1


def _cmd_distill(args: argparse.Namespace) -> int:
    from hermes_cli.jarvis_prime.federation.trust_ladder import ContributorStore
    from hermes_cli.jarvis_prime.learning_dataset import DatasetStore

    from .distill import distill_winners

    registry = CandidateRegistry()
    try:
        task = _task(args.task)
    except ForgeError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    report = TournamentReport.from_dict(
        json.loads(Path(args.report).read_text(encoding="utf-8"))
    )
    store = ContributorStore()
    dataset = DatasetStore()
    decisions = distill_winners(
        report,
        registry,
        task,
        contributor=store.get(args.contributor),
        dataset_store=dataset,
        store=store,
        ledger=GuardrailLedger(),
        top_k=args.top_k,
    )
    _emit([d.to_dict() for d in decisions])
    return 0 if any(d.admitted for d in decisions) else 1


def cli_main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m hermes_cli.jarvis_prime forge",
        description="The Expert Forge: content-addressed candidates, Glicko-2 "
        "tournaments, MAP-Elites, attested leaderboards, distillation",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_reg = sub.add_parser("register", help="Register a candidate from a code file")
    p_reg.add_argument("--task", default=DEMO_TASK.task_id)
    p_reg.add_argument("--code-file", required=True)
    p_reg.add_argument("--contributor", default="local")
    p_reg.set_defaults(func=_cmd_register)

    p_look = sub.add_parser("lookup", help="Resolve a candidate (resolve-or-fail)")
    p_look.add_argument("candidate_id", nargs="?", default="")
    p_look.add_argument("--hash", default="")
    p_look.set_defaults(func=_cmd_lookup)

    sub.add_parser("candidates", help="List registered candidates").set_defaults(
        func=_cmd_candidates
    )

    p_duel = sub.add_parser("duel", help="Run one verifier-judged duel")
    p_duel.add_argument("--task", default=DEMO_TASK.task_id)
    p_duel.add_argument("a")
    p_duel.add_argument("b")
    p_duel.set_defaults(func=_cmd_duel)

    p_t = sub.add_parser("tournament", help="Run a matched tournament over a task")
    p_t.add_argument("--task", default=DEMO_TASK.task_id)
    p_t.add_argument("--rounds", type=int, default=1)
    p_t.add_argument("--seed", type=int, default=0)
    p_t.add_argument("--out", default="")
    p_t.set_defaults(func=_cmd_tournament)

    sub.add_parser("ratings", help="Show the Glicko-2 rating book").set_defaults(
        func=_cmd_ratings
    )
    sub.add_parser("elites", help="Show the MAP-Elites grid").set_defaults(func=_cmd_elites)
    sub.add_parser("leaderboard", help="Show standings").set_defaults(func=_cmd_leaderboard)

    p_anchor = sub.add_parser("anchor", help="Emit a Merkle-anchored leaderboard attestation")
    p_anchor.add_argument("--out", default="")
    p_anchor.set_defaults(func=_cmd_anchor)

    p_va = sub.add_parser("verify-anchor", help="Verify a leaderboard attestation file")
    p_va.add_argument("artifact")
    p_va.set_defaults(func=_cmd_verify_anchor)

    p_d = sub.add_parser("distill", help="Distill tournament winners via the poison filter")
    p_d.add_argument("--task", default=DEMO_TASK.task_id)
    p_d.add_argument("--report", required=True)
    p_d.add_argument("--contributor", default="local")
    p_d.add_argument("--top-k", type=int, default=3)
    p_d.set_defaults(func=_cmd_distill)

    args = parser.parse_args(list(argv) if argv is not None else None)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli_main())
