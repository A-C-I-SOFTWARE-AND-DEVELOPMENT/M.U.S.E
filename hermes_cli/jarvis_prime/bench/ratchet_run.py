"""Phase-4 adoption gate: template-ON challenger vs template-OFF champion.

Runs both configurations through the existing research_fabric machinery —
``benchmarks.run_suite`` (executable verifiers per domain) feeding
``validators.evaluate_ratchet`` (all 8 conditions, catalog thresholds
UNTOUCHED) — and acts on the verdict exactly once:

- **PASS** (and not ``mechanical_only``): freeze the challenger via
  ``ChampionStore.freeze`` with a real git-sha rollback handle; both the
  SnapshotStore row and the GuardrailLedger record are written by the freeze.
- **FAIL** or ``mechanical_only``: enqueue one structured entry to the
  flywheel ``improvement_queue.jsonl`` and STOP. No retries, no lowered bars.

CLI (owner laptop, with a live llama-server and ``MUSE_TEMPLATES=1``):

    python -m hermes_cli.jarvis_prime.bench.ratchet_run \
        --rollback-handle "$(git rev-parse HEAD)"

In an environment with no real model, pass ``--mechanical-only`` — the full
plumbing runs (scores, verdict, queue entry) but nothing is ever frozen.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from ..guardrail_evidence import GuardrailLedger
from ..research_fabric.benchmarks import (
    BenchmarkTaskSpec,
    SuiteResult,
    load_suite,
    run_suite,
)
from ..research_fabric.champion import Champion, ChampionStore
from ..research_fabric.store import SnapshotStore, open_store
from ..research_fabric.validators import RatchetVerdict, evaluate_ratchet
from .corpus import FIXTURE_SUITE, HELDOUT_DIR

Runner = Callable[[str], str]

SAFETY_DOMAIN = "safety"


@dataclass(frozen=True)
class ConfigurationScore:
    domain_scores: dict[str, float]
    safety_counts: dict[str, float]
    per_task_correctness: dict[str, float]
    mean_latency_s: float


@dataclass(frozen=True)
class RatchetRunResult:
    verdict: RatchetVerdict
    frozen: bool
    champion_id: Optional[str]
    rollback_handle: str
    mechanical_only: bool
    challenger: ConfigurationScore
    champion: ConfigurationScore
    holdout_scores: dict[str, float]
    eval_win_rate: float


def _strip_embedded_candidates(specs: Sequence[BenchmarkTaskSpec]) -> list[BenchmarkTaskSpec]:
    """Remove fixture-embedded candidates so the live runner is what's scored."""

    stripped = []
    for spec in specs:
        payload = {k: v for k, v in spec.payload.items() if k not in ("candidate", "candidate_fail")}
        stripped.append(
            BenchmarkTaskSpec(task_id=spec.task_id, domain=spec.domain, kind=spec.kind, payload=payload)
        )
    return stripped


def _heldout_base_ids(heldout_dir: Path = HELDOUT_DIR) -> set[str]:
    ids: set[str] = set()
    for path in sorted(heldout_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                ids.add(str(json.loads(line)["task_id"]).split("#", 1)[0])
    return ids


def score_configuration(
    runner: Runner,
    specs: Sequence[BenchmarkTaskSpec],
    *,
    base_dir: Optional[Path] = None,
) -> ConfigurationScore:
    """Score a runner over a suite through the executable verifiers."""

    latencies: list[float] = []

    def solver(task) -> str:  # research_fabric AlgorithmSolver
        start = time.perf_counter()
        out = runner(task.prompt)
        latencies.append(time.perf_counter() - start)
        return out

    def fixer(task, current: str) -> str:  # research_fabric SweFixer
        start = time.perf_counter()
        out = runner(f"{task.task_id}\n{current}")
        latencies.append(time.perf_counter() - start)
        return out

    result: SuiteResult = run_suite(
        _strip_embedded_candidates(specs), solver=solver, swe_fixer=fixer, base_dir=base_dir
    )
    safety_failures = sum(
        1.0 for o in result.outcomes if o.domain == SAFETY_DOMAIN and o.correctness < 1.0
    )
    return ConfigurationScore(
        domain_scores=result.per_domain_scores(),
        safety_counts={"safety_task_failures": safety_failures},
        per_task_correctness={o.task_id: o.correctness for o in result.outcomes},
        mean_latency_s=statistics.fmean(latencies) if latencies else 0.0,
    )


def _head_to_head_win_rate(
    challenger: ConfigurationScore, champion: ConfigurationScore
) -> float:
    """AlphaGo-Zero evaluator gate input: per-task wins, ties = 0.5."""

    tasks = sorted(set(challenger.per_task_correctness) & set(champion.per_task_correctness))
    if not tasks:
        return 0.0
    points = 0.0
    for task_id in tasks:
        a = challenger.per_task_correctness[task_id]
        b = champion.per_task_correctness[task_id]
        points += 1.0 if a > b else (0.5 if a == b else 0.0)
    return points / len(tasks)


def run_ratchet(
    *,
    champion_runner: Runner,
    candidate_runner: Runner,
    rollback_handle: str,
    db_path: Path,
    ledger_path: Path,
    suite_path: Path = FIXTURE_SUITE,
    heldout_dir: Path = HELDOUT_DIR,
    mechanical_only: bool = False,
    base_dir: Optional[Path] = None,
    queue_improvement: Optional[Callable[..., object]] = None,
) -> RatchetRunResult:
    specs = load_suite(suite_path)
    held_ids = _heldout_base_ids(heldout_dir)
    train_specs = [s for s in specs if s.task_id not in held_ids]
    held_specs = [s for s in specs if s.task_id in held_ids]

    store = open_store(db_path)
    ledger = GuardrailLedger(ledger_path)
    champions = ChampionStore(store, ledger)

    challenger = score_configuration(candidate_runner, train_specs, base_dir=base_dir)
    challenger_held = score_configuration(candidate_runner, held_specs, base_dir=base_dir)

    existing = champions.current()
    if existing is not None:
        champion_scores: Optional[dict[str, float]] = dict(existing.domain_scores)
        champion_safety: Optional[dict[str, float]] = dict(existing.safety_counts)
        champion_cfg = ConfigurationScore(
            domain_scores=dict(existing.domain_scores),
            safety_counts=dict(existing.safety_counts),
            per_task_correctness={},
            mean_latency_s=0.0,
        )
        eval_win_rate = _head_to_head_win_rate(
            challenger, score_configuration(champion_runner, train_specs, base_dir=base_dir)
        )
    else:
        champion_cfg = score_configuration(champion_runner, train_specs, base_dir=base_dir)
        champion_scores = champion_cfg.domain_scores or None
        champion_safety = champion_cfg.safety_counts
        eval_win_rate = _head_to_head_win_rate(challenger, champion_cfg)

    verdict = evaluate_ratchet(
        champion_domain_scores=champion_scores,
        candidate_domain_scores=challenger.domain_scores,
        holdout_scores=challenger_held.domain_scores,
        candidate_safety_counts=challenger.safety_counts,
        champion_safety_counts=champion_safety,
        eval_win_rate=eval_win_rate,
    )

    frozen = False
    champion_id: Optional[str] = None
    if verdict.passed and not mechanical_only:
        new_champion = Champion.make(
            domain_scores=challenger.domain_scores,
            composite=verdict.composite_candidate,
            rollback_handle=rollback_handle,
            safety_counts=challenger.safety_counts,
            note="template fastpath (MUSE_TEMPLATES challenger) promoted via ratchet",
        )
        champions.freeze(new_champion, reason="ratchet pass: template fastpath")
        # The freeze must be visible in BOTH stores before reporting success.
        assert store.latest("champion_freeze") is not None
        frozen = True
        champion_id = new_champion.champion_id
    else:
        queue = queue_improvement
        if queue is None:
            from .. import flywheel

            queue = flywheel.queue_improvement
        reason = (
            "deferred live run (mechanical-only environment)"
            if verdict.passed and mechanical_only
            else "ratchet rejected template fastpath challenger"
        )
        queue(
            f"templates ratchet: {reason}",
            kind="templates.ratchet",
            payload={
                "verdict": verdict.to_dict(),
                "challenger_domain_scores": challenger.domain_scores,
                "holdout_scores": challenger_held.domain_scores,
                "eval_win_rate": round(eval_win_rate, 4),
                "mechanical_only": mechanical_only,
                "rollback_handle": rollback_handle,
            },
            source="template_fastpath",
        )

    return RatchetRunResult(
        verdict=verdict,
        frozen=frozen,
        champion_id=champion_id,
        rollback_handle=rollback_handle,
        mechanical_only=mechanical_only,
        challenger=challenger,
        champion=champion_cfg,
        holdout_scores=challenger_held.domain_scores,
        eval_win_rate=eval_win_rate,
    )


def _default_paths() -> tuple[Path, Path]:
    import os

    base = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes") / "research_fabric"
    base.mkdir(parents=True, exist_ok=True)
    return base / "snapshots.sqlite3", base / "guardrail_ledger.jsonl"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Template fast-path ratchet adoption run")
    parser.add_argument("--rollback-handle", required=True, help="git sha to record for rollback")
    parser.add_argument("--mechanical-only", action="store_true", help="never freeze; plumbing only")
    parser.add_argument("--suite", type=Path, default=FIXTURE_SUITE)
    parser.add_argument("--heldout-dir", type=Path, default=HELDOUT_DIR)
    args = parser.parse_args(argv)

    from ..gemma_runner import build_gemma_runner

    base_runner = build_gemma_runner()
    if base_runner is None:
        if not args.mechanical_only:
            print("no Gemma runner available (install Ollama + a gemma model), aborting")
            return 2

        def base_runner(prompt: str) -> str:  # mechanical stub
            return "def solve():\n    return None\n"

    import os

    os.environ["MUSE_TEMPLATES"] = "1"
    from ..template_fastpath import maybe_wrap_runner

    candidate = maybe_wrap_runner(base_runner)
    os.environ["MUSE_TEMPLATES"] = "0"

    db_path, ledger_path = _default_paths()
    result = run_ratchet(
        champion_runner=base_runner,
        candidate_runner=candidate,
        rollback_handle=args.rollback_handle,
        db_path=db_path,
        ledger_path=ledger_path,
        suite_path=args.suite,
        heldout_dir=args.heldout_dir,
        mechanical_only=args.mechanical_only,
    )
    print(json.dumps(
        {
            "passed": result.verdict.passed,
            "frozen": result.frozen,
            "champion_id": result.champion_id,
            "reasons": list(result.verdict.reasons),
            "challenger_domain_scores": result.challenger.domain_scores,
            "holdout_scores": result.holdout_scores,
            "eval_win_rate": round(result.eval_win_rate, 4),
            "challenger_mean_latency_s": round(result.challenger.mean_latency_s, 4),
            "champion_mean_latency_s": round(result.champion.mean_latency_s, 4),
        },
        indent=2,
    ))
    return 0 if (result.frozen or not result.verdict.passed or result.mechanical_only) else 1


if __name__ == "__main__":
    raise SystemExit(main())
