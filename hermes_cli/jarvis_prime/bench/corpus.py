"""Corpus of (task, output, verifier verdict) triples for the template fast path.

The ship plan asks for triples mined from ``$HERMES_HOME/flywheel/events.jsonl``;
that history was empty in this environment, so the sanctioned fallback applies:
the corpus is built from the committed fixture suite
(``bench/fixtures/algorithm_suite.jsonl``). The PASS tag on every record is
*mechanically earned* — each embedded candidate is executed through the real
``score_algorithm_candidate`` verifier, never trusted from the fixture labels.

Held-out splits are deterministic on ``sha256(task_id)`` so mining can never
see the held-out side, and are exported per domain to
``research_fabric/heldout/<domain>.jsonl``.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Sequence

from ..research_fabric.benchmarks import BenchmarkTaskSpec, load_suite
from ..research_fabric.verifier.algorithms import (
    AlgorithmCase,
    AlgorithmTask,
    score_algorithm_candidate,
)

FIXTURE_SUITE = Path(__file__).resolve().parent / "fixtures" / "algorithm_suite.jsonl"
HELDOUT_DIR = Path(__file__).resolve().parent.parent / "research_fabric" / "heldout"


@dataclass(frozen=True)
class CorpusRecord:
    task_id: str
    domain: str
    prompt: str
    output: str
    verifier_passed: bool
    source: str  # provenance: "fixture:<suite filename>" or "flywheel"

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def output_hash(self) -> str:
        return hashlib.sha256(self.output.encode("utf-8")).hexdigest()


def _algorithm_task(spec: BenchmarkTaskSpec) -> AlgorithmTask:
    p = spec.payload
    return AlgorithmTask(
        task_id=spec.task_id,
        entrypoint=str(p.get("entrypoint", "solve")),
        prompt=str(p.get("prompt", "")),
        public_cases=tuple(
            AlgorithmCase(args=list(c["args"]), expected=c["expected"])
            for c in p.get("public_cases", [])
        ),
        holdout_cases=tuple(
            AlgorithmCase(args=list(c["args"]), expected=c["expected"])
            for c in p.get("holdout_cases", [])
        ),
    )


def build_corpus(
    *,
    suite_path: Path = FIXTURE_SUITE,
    max_per_domain: Optional[int] = None,
    include_failures: bool = True,
) -> list[CorpusRecord]:
    """Build verifier-verdicted records from the fixture suite.

    Every candidate (good and bad alike) is executed through
    ``score_algorithm_candidate``; ``verifier_passed`` is the verifier's
    ``accepted`` bit, not the fixture's claim. ``max_per_domain`` bounds the
    spec count per domain (tests use a small bound to stay fast).
    """

    records: list[CorpusRecord] = []
    seen_per_domain: dict[str, int] = {}
    source = f"fixture:{Path(suite_path).name}"
    for spec in load_suite(Path(suite_path)):
        if spec.kind != "algorithm":
            continue
        n = seen_per_domain.get(spec.domain, 0)
        if max_per_domain is not None and n >= max_per_domain:
            continue
        seen_per_domain[spec.domain] = n + 1
        task = _algorithm_task(spec)
        prompt = str(spec.payload.get("prompt", ""))
        candidates = [str(spec.payload.get("candidate", ""))]
        if include_failures and spec.payload.get("candidate_fail"):
            candidates.append(str(spec.payload["candidate_fail"]))
        for idx, code in enumerate(candidates):
            if not code:
                continue
            score = score_algorithm_candidate(code, task)
            records.append(
                CorpusRecord(
                    task_id=f"{spec.task_id}#c{idx}",
                    domain=spec.domain,
                    prompt=prompt,
                    output=code,
                    verifier_passed=score.accepted,
                    source=source,
                )
            )
    return records


def split_heldout(
    records: Sequence[CorpusRecord],
    *,
    ratio: float = 0.2,
    seed: int = 0,
) -> tuple[list[CorpusRecord], list[CorpusRecord]]:
    """Deterministic stratified (train, heldout) split.

    Stratified per domain so EVERY domain keeps a held-out wall (a plain hash
    split left whole domains empty on a 30-task corpus). Within a domain, base
    task ids are ranked by ``sha256(seed:base_id)`` and the lowest
    ``ceil(ratio * n)`` go to held-out. Both candidates of one fixture task
    share the base id (before ``#``), so a task's pass/fail pair always lands
    on the same side — no leakage of a held-out task's prompt into mining via
    its sibling candidate.
    """

    def rank(base_id: str) -> int:
        digest = hashlib.sha256(f"{seed}:{base_id}".encode("utf-8")).digest()
        return int.from_bytes(digest[:4], "big")

    base_ids_by_domain: dict[str, set[str]] = {}
    for rec in records:
        base_ids_by_domain.setdefault(rec.domain, set()).add(rec.task_id.split("#", 1)[0])

    heldout_ids: set[str] = set()
    for domain in sorted(base_ids_by_domain):
        ordered = sorted(base_ids_by_domain[domain], key=lambda b: (rank(b), b))
        n_held = max(1, math.ceil(ratio * len(ordered))) if ordered else 0
        heldout_ids.update(ordered[:n_held])

    train: list[CorpusRecord] = []
    heldout: list[CorpusRecord] = []
    for rec in records:
        base_id = rec.task_id.split("#", 1)[0]
        (heldout if base_id in heldout_ids else train).append(rec)
    return train, heldout


def write_heldout(records: Sequence[CorpusRecord], out_dir: Path = HELDOUT_DIR) -> list[Path]:
    """Export held-out records per domain as ``<domain>.jsonl``."""

    out_dir.mkdir(parents=True, exist_ok=True)
    by_domain: dict[str, list[CorpusRecord]] = {}
    for rec in records:
        by_domain.setdefault(rec.domain, []).append(rec)
    written: list[Path] = []
    for domain in sorted(by_domain):
        path = out_dir / f"{domain}.jsonl"
        lines = [json.dumps(r.to_dict(), sort_keys=True) for r in by_domain[domain]]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append(path)
    return written


def corpus_hash(records: Sequence[CorpusRecord]) -> str:
    """Stable content hash over the full record list (provenance versioning)."""

    payload = json.dumps([r.to_dict() for r in records], sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "CorpusRecord",
    "FIXTURE_SUITE",
    "HELDOUT_DIR",
    "build_corpus",
    "split_heldout",
    "write_heldout",
    "corpus_hash",
]
