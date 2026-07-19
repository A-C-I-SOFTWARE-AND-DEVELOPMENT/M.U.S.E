"""Merge engine: pick the best worker, detect conflicts, write the plan.

Phase 14 of the Hermes local orchestrator. The scoring layer
(`hermes_cli.scoring`) tells us *how good* each worker is. This module
decides *what to ship*. It is intentionally conservative: when in doubt
it asks for a human review rather than producing a Frankenstein patch.

Merge policy (in priority order)
--------------------------------

1. **Reject high-risk workers without tests.** A worker that touched
   auth / billing / migrations without adding tests cannot win, full
   stop, even if its weighted score is highest. It is preserved as a
   *rejected candidate* in the council review with an explanation.
2. **Reject workers that leak secrets.** Anything with a non-empty
   ``secrets_safety`` flag is rejected outright — leaking an API key
   is never a tradeoff.
3. **Prefer validated small diffs.** Among the surviving candidates,
   we sort by ``weighted_total`` from `scoring.rank`, which already
   biases toward small diffs that pass tests. We do not stitch patches
   together to chase a higher score.
4. **Detect conflicts.** If the winning worker and *any other* worker
   that crossed the score floor touched the same file, we record a
   ``FileConflict``. Conflicts do not automatically block the winner —
   they appear in ``conflict-report.md`` and the final plan asks the
   human to confirm the resolution.
5. **Preserve losing ideas.** Every losing worker gets a short entry
   in ``council-review.md`` with its score breakdown and its strongest
   note, so the human can lift good ideas from the runners-up before
   the run is filed.
6. **Manual review when there's no clear winner.** If no surviving
   candidate scores above ``MANUAL_REVIEW_FLOOR`` on ``correctness``,
   we still write the artifacts but mark the final plan as requiring
   manual review and leave ``final-patch.diff`` empty.

The engine never executes a patch. It writes plan artifacts to a
``merge/`` directory and returns a `MergeResult` describing what it
chose. Application of the diff is the orchestrator's job.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from hermes_cli.decision_engine import (
    DecisionTier,
    DecisionVerdict,
    merge_decision_inputs,
    policy_input,
    protected_path_input,
    secret_input,
    validation_input,
)
from hermes_cli.scoring import (
    SCORE_CATEGORIES,
    Scorecard,
    WorkerArtifact,
    discover_workers,
    load_artifact,
    rank,
    score_artifact,
)


# Score thresholds. Tuned against the test fixtures; if you tune them,
# update tests/test_merge_engine.py accordingly.
SCORE_FLOOR: float = 0.45            # below this, a worker can't be a candidate
MANUAL_REVIEW_FLOOR: float = 0.55    # winner must beat this to skip manual review
HIGH_RISK_TEST_REQUIRED: bool = True # reject high-risk diffs lacking tests
SECRETS_SAFETY_FLOOR: float = 0.5    # below this, secrets are assumed leaked


@dataclass(frozen=True)
class FileConflict:
    """Two or more candidates touched the same file."""

    path: str
    workers: tuple[str, ...]

    def as_dict(self) -> Mapping[str, object]:
        return {"path": self.path, "workers": list(self.workers)}


@dataclass
class RejectedWorker:
    """A worker excluded from selection, with a human-readable reason."""

    worker_id: str
    profile: str
    reason: str
    score: float

    def as_dict(self) -> Mapping[str, object]:
        return asdict(self)


@dataclass
class MergeResult:
    """End-of-run summary returned by `run_merge`."""

    winner: Optional[Scorecard]
    rejected: list[RejectedWorker] = field(default_factory=list)
    runners_up: list[Scorecard] = field(default_factory=list)
    conflicts: list[FileConflict] = field(default_factory=list)
    manual_review_required: bool = False
    review_reasons: list[str] = field(default_factory=list)
    output_dir: Optional[Path] = None
    # Sprint 2 breadth: the unified auto/ask/refuse verdict for the selection.
    # Recorded, not gating — the policy gates above (high-risk-no-tests,
    # secrets-safety, score floor, manual-review) remain the sole control flow.
    decision_verdict: Optional[DecisionVerdict] = None

    def as_dict(self) -> Mapping[str, object]:
        return {
            "winner": self.winner.as_dict() if self.winner else None,
            "rejected": [r.as_dict() for r in self.rejected],
            "runners_up": [s.as_dict() for s in self.runners_up],
            "conflicts": [c.as_dict() for c in self.conflicts],
            "manual_review_required": self.manual_review_required,
            "review_reasons": list(self.review_reasons),
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "decision_verdict": (
                self.decision_verdict.to_redacted_dict()
                if self.decision_verdict
                else None
            ),
        }


# ──────────────────────────────────────────────────────────────────────
# Selection pipeline
# ──────────────────────────────────────────────────────────────────────


def _reject_high_risk_no_tests(
    cards: Sequence[Scorecard],
) -> tuple[list[Scorecard], list[RejectedWorker]]:
    """Drop workers that touched high-risk surfaces without adding tests."""
    survivors: list[Scorecard] = []
    rejected: list[RejectedWorker] = []
    for card in cards:
        if HIGH_RISK_TEST_REQUIRED and card.touches_high_risk and not card.adds_tests:
            rejected.append(
                RejectedWorker(
                    worker_id=card.worker_id,
                    profile=card.profile,
                    reason=(
                        "touches high-risk paths (auth/billing/migrations/etc.) "
                        "without adding tests — policy blocks selection"
                    ),
                    score=card.weighted_total,
                )
            )
        else:
            survivors.append(card)
    return survivors, rejected


def _reject_leaks_secrets(
    cards: Sequence[Scorecard],
) -> tuple[list[Scorecard], list[RejectedWorker]]:
    """Drop workers whose ``secrets_safety`` is below the floor."""
    survivors: list[Scorecard] = []
    rejected: list[RejectedWorker] = []
    for card in cards:
        secrets_score = card.scores.get("secrets_safety", 1.0)
        if secrets_score < SECRETS_SAFETY_FLOOR:
            rejected.append(
                RejectedWorker(
                    worker_id=card.worker_id,
                    profile=card.profile,
                    reason=(
                        f"secrets_safety score {secrets_score:.2f} is below "
                        f"floor {SECRETS_SAFETY_FLOOR:.2f} — possible secret in diff"
                    ),
                    score=card.weighted_total,
                )
            )
        else:
            survivors.append(card)
    return survivors, rejected


def _reject_below_floor(
    cards: Sequence[Scorecard],
) -> tuple[list[Scorecard], list[RejectedWorker]]:
    """Drop workers whose weighted score is below ``SCORE_FLOOR``."""
    survivors: list[Scorecard] = []
    rejected: list[RejectedWorker] = []
    for card in cards:
        if card.weighted_total < SCORE_FLOOR:
            rejected.append(
                RejectedWorker(
                    worker_id=card.worker_id,
                    profile=card.profile,
                    reason=(
                        f"weighted score {card.weighted_total:.2f} is below "
                        f"floor {SCORE_FLOOR:.2f}"
                    ),
                    score=card.weighted_total,
                )
            )
        else:
            survivors.append(card)
    return survivors, rejected


def _detect_conflicts(
    artifacts_by_id: Mapping[str, WorkerArtifact],
    candidate_ids: Iterable[str],
) -> list[FileConflict]:
    """Return one `FileConflict` per file touched by 2+ candidates."""
    candidate_ids = list(candidate_ids)
    file_to_workers: dict[str, list[str]] = {}
    for wid in candidate_ids:
        art = artifacts_by_id.get(wid)
        if art is None:
            continue
        for path in art.changed_files:
            file_to_workers.setdefault(path, []).append(wid)
    return [
        FileConflict(path=p, workers=tuple(workers))
        for p, workers in sorted(file_to_workers.items())
        if len(workers) >= 2
    ]


def _high_risk_paths(art: Optional[WorkerArtifact]) -> list[str]:
    """Return the winner's changed files that hit a high-risk surface.

    Mirrors :pyattr:`scoring.WorkerArtifact.touches_high_risk` but returns the
    specific paths so the protected-path signal carries detail. Imported lazily
    to avoid coupling to scoring's private hint tuple at module import time.
    """
    if art is None:
        return []
    from hermes_cli.scoring import _HIGH_RISK_PATH_HINTS

    hits: list[str] = []
    for path in art.changed_files:
        lowered = path.lower()
        if any(hint in lowered for hint in _HIGH_RISK_PATH_HINTS):
            hits.append(path)
    return hits


def _build_merge_verdict(
    result: MergeResult,
    artifacts_by_id: Mapping[str, WorkerArtifact],
) -> DecisionVerdict:
    """Compute the unified verdict for a completed selection (recorded, not gating).

    The merge engine's own policy gates already decided what to ship; this maps
    the *same* signals onto the canonical auto/ask/refuse verdict so the cockpit
    and audit ledger see one verdict per merge. It never changes the outcome:

    * No winner  → ``policy`` refuse (nothing passed selection).
    * Winner     → ``validation`` (override-allowed, so a failed run is ``ask``
      not ``refuse`` — matching the existing manual-review path), ``secret``
      (a winner below the secrets floor would have been rejected, so this is
      normally ``auto``), and ``protected_path`` (soft ``ask`` for a high-risk
      winner — the engine already surfaces these for human eyes, never blocks).
    """
    if result.winner is None:
        return merge_decision_inputs(
            "merge_engine.select_winner",
            [
                policy_input(
                    DecisionTier.REFUSE,
                    "no worker survived the policy + score-floor gates",
                )
            ],
        )

    winner = result.winner
    art = artifacts_by_id.get(winner.worker_id)
    secrets_score = winner.scores.get("secrets_safety", 1.0)
    secret_findings = (
        [f"secrets_safety {secrets_score:.2f} below floor {SECRETS_SAFETY_FLOOR:.2f}"]
        if secrets_score < SECRETS_SAFETY_FLOOR
        else []
    )
    return merge_decision_inputs(
        "merge_engine.select_winner",
        [
            validation_input(winner.tests_passed is True, override_allowed=True),
            secret_input(secret_findings),
            protected_path_input(_high_risk_paths(art), hard=False),
        ],
    )


def select_winner(
    artifacts: Sequence[WorkerArtifact],
    scorecards: Sequence[Scorecard],
) -> MergeResult:
    """Run the full selection pipeline and return a `MergeResult`.

    Does not write any files — that's `_write_artifacts`'s job. Pulled
    out as its own function so tests can inspect the decision tree
    without touching the filesystem.
    """
    by_id = {a.worker_id: a for a in artifacts}

    # Stage 1: hard policy gate — high-risk without tests.
    survivors, rejected_risk = _reject_high_risk_no_tests(scorecards)
    # Stage 2: hard policy gate — leaked secrets.
    survivors, rejected_secrets = _reject_leaks_secrets(survivors)
    # Stage 3: score floor.
    survivors, rejected_floor = _reject_below_floor(survivors)

    rejected = rejected_risk + rejected_secrets + rejected_floor

    if not survivors:
        no_winner = MergeResult(
            winner=None,
            rejected=rejected,
            manual_review_required=True,
            review_reasons=[
                "no worker survived the policy + score-floor gates",
            ],
        )
        no_winner.decision_verdict = _build_merge_verdict(no_winner, by_id)
        return no_winner

    ranked = rank(survivors)
    winner = ranked[0]
    runners_up = ranked[1:]

    conflicts = _detect_conflicts(
        by_id,
        [c.worker_id for c in ranked],
    )

    manual = False
    reasons: list[str] = []
    if winner.weighted_total < MANUAL_REVIEW_FLOOR:
        manual = True
        reasons.append(
            f"top weighted score {winner.weighted_total:.2f} is below the "
            f"manual-review floor {MANUAL_REVIEW_FLOOR:.2f}"
        )
    if winner.tests_passed is False:
        manual = True
        reasons.append("winning worker's validation reported failures")
    if winner.touches_high_risk:
        # We already rejected high-risk-no-tests; a high-risk winner
        # *with* tests still gets surfaced for human eyes.
        reasons.append(
            "winning worker touches high-risk paths — confirm before applying"
        )
    if conflicts:
        manual = True
        reasons.append(
            f"{len(conflicts)} file(s) modified by 2+ candidates — "
            "confirm the winning patch resolves them correctly"
        )

    result = MergeResult(
        winner=winner,
        rejected=rejected,
        runners_up=runners_up,
        conflicts=conflicts,
        manual_review_required=manual,
        review_reasons=reasons,
    )
    result.decision_verdict = _build_merge_verdict(result, by_id)
    return result


# ──────────────────────────────────────────────────────────────────────
# Output artifacts
# ──────────────────────────────────────────────────────────────────────


def _format_score_row(card: Scorecard) -> str:
    cells = [f"{card.scores.get(cat, 0.0):.2f}" for cat in SCORE_CATEGORIES]
    return f"| {card.worker_id} | {card.profile} | " + " | ".join(cells) + " |"


def _write_scorecard_json(
    out_dir: Path,
    result: MergeResult,
    scorecards: Sequence[Scorecard],
) -> Path:
    payload = {
        "schema": "hermes.merge.scorecard.v2",
        "categories": list(SCORE_CATEGORIES),
        "winner": result.winner.worker_id if result.winner else None,
        "manual_review_required": result.manual_review_required,
        "review_reasons": list(result.review_reasons),
        "scorecards": [c.as_dict() for c in scorecards],
        "rejected": [r.as_dict() for r in result.rejected],
        "conflicts": [c.as_dict() for c in result.conflicts],
        # Sprint 2 breadth: persist the unified verdict alongside the scores.
        # Recorded only — the winner/manual-review fields above are unchanged.
        "decision_verdict": (
            result.decision_verdict.to_redacted_dict()
            if result.decision_verdict
            else None
        ),
    }
    target = out_dir / "scorecard.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def _write_council_review(
    out_dir: Path,
    result: MergeResult,
    artifacts_by_id: Mapping[str, WorkerArtifact],
    scorecards: Sequence[Scorecard],
) -> Path:
    lines: list[str] = []
    lines.append("# Council review")
    lines.append("")
    if result.winner is None:
        lines.append("**No winner selected.** All workers were rejected.")
    else:
        w = result.winner
        lines.append(f"## Selected: `{w.worker_id}` (profile: {w.profile})")
        lines.append("")
        lines.append(
            f"- Weighted score: **{w.weighted_total:.3f}** "
            f"(unweighted mean {w.total:.3f})"
        )
        lines.append(f"- Validation passed: {w.tests_passed}")
        lines.append(f"- Files changed: {w.changed_file_count}")
        lines.append(f"- Diff lines: {w.diff_line_count}")
        lines.append(f"- Touches high-risk paths: {w.touches_high_risk}")
        lines.append(f"- Adds tests: {w.adds_tests}")
        if w.notes:
            lines.append("")
            lines.append("**Notes from scoring:**")
            for note in w.notes:
                lines.append(f"- {note}")
        if w.flags:
            lines.append("")
            lines.append("**Flags raised on the winning worker:**")
            for flag in w.flags:
                lines.append(f"- {flag}")

    # Score table — all workers, including rejected ones, so the human
    # can sanity-check the decision.
    lines.append("")
    lines.append("## Score breakdown")
    lines.append("")
    header = (
        "| worker | profile | "
        + " | ".join(SCORE_CATEGORIES)
        + " |"
    )
    sep = "| --- | --- | " + " | ".join(["---"] * len(SCORE_CATEGORIES)) + " |"
    lines.append(header)
    lines.append(sep)
    for card in scorecards:
        lines.append(_format_score_row(card))

    # Rejected workers section.
    if result.rejected:
        lines.append("")
        lines.append("## Rejected workers")
        lines.append("")
        for r in result.rejected:
            lines.append(
                f"- **`{r.worker_id}`** ({r.profile}, score {r.score:.2f}): "
                f"{r.reason}"
            )

    # Runners-up — preserve good ideas from losing workers.
    if result.runners_up:
        lines.append("")
        lines.append("## Runners-up (ideas worth preserving)")
        lines.append("")
        for s in result.runners_up:
            best_note = s.notes[0] if s.notes else "(no scoring notes)"
            lines.append(
                f"- `{s.worker_id}` ({s.profile}, score {s.weighted_total:.2f}): "
                f"{best_note}"
            )
            art = artifacts_by_id.get(s.worker_id)
            if art and art.output_md:
                summary = _first_paragraph(art.output_md)
                if summary:
                    lines.append(f"  - Summary: {summary}")

    if result.conflicts:
        lines.append("")
        lines.append("## Conflicts")
        lines.append("")
        for c in result.conflicts:
            lines.append(
                f"- `{c.path}` modified by: " + ", ".join(c.workers)
            )

    if result.review_reasons:
        lines.append("")
        lines.append("## Validation needed")
        lines.append("")
        for reason in result.review_reasons:
            lines.append(f"- {reason}")

    target = out_dir / "council-review.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _write_conflict_report(out_dir: Path, result: MergeResult) -> Path:
    lines: list[str] = ["# Conflict report", ""]
    if not result.conflicts:
        lines.append("No conflicts detected: no file was modified by more than")
        lines.append("one surviving candidate.")
    else:
        lines.append(
            f"{len(result.conflicts)} file(s) were modified by 2+ surviving "
            "candidates. The merge engine does NOT auto-combine patches."
        )
        lines.append("Apply the winning patch and review each path manually:")
        lines.append("")
        for c in result.conflicts:
            lines.append(f"## `{c.path}`")
            lines.append("")
            lines.append(f"- Workers touching this file: {', '.join(c.workers)}")
            if result.winner and result.winner.worker_id in c.workers:
                lines.append(
                    f"- Winner (`{result.winner.worker_id}`) is one of them; "
                    "its version is what `final-patch.diff` contains."
                )
            else:
                lines.append(
                    "- Winner did not touch this file — losing workers' "
                    "ideas may be worth porting manually."
                )
            lines.append("")
    target = out_dir / "conflict-report.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _write_final_plan(
    out_dir: Path,
    result: MergeResult,
    artifacts_by_id: Mapping[str, WorkerArtifact],
) -> Path:
    lines: list[str] = ["# Final plan", ""]
    if result.winner is None:
        lines.append("**Status:** REJECTED — no worker passed selection.")
        lines.append("")
        lines.append("Action: re-run with adjusted prompts or escalate to a human.")
    else:
        w = result.winner
        art = artifacts_by_id.get(w.worker_id)
        status = "MANUAL REVIEW REQUIRED" if result.manual_review_required else "READY"
        lines.append(f"**Status:** {status}")
        lines.append("")
        lines.append(f"- Winner: `{w.worker_id}` (profile: {w.profile})")
        lines.append(f"- Weighted score: {w.weighted_total:.3f}")
        lines.append(f"- Files touched: {w.changed_file_count}")
        lines.append(f"- Diff lines: {w.diff_line_count}")
        lines.append("")
        if art and art.output_md:
            lines.append("## Worker rationale")
            lines.append("")
            lines.append(_first_paragraph(art.output_md) or "(no rationale)")
            lines.append("")
        if art and art.changed_files:
            lines.append("## Files to change")
            lines.append("")
            for path in art.changed_files:
                lines.append(f"- `{path}`")
            lines.append("")
        if result.review_reasons:
            lines.append("## Validation gates")
            lines.append("")
            for reason in result.review_reasons:
                lines.append(f"- {reason}")
            lines.append("")
        lines.append("## How to apply")
        lines.append("")
        if result.manual_review_required:
            lines.append(
                "1. Read `council-review.md` and `conflict-report.md`."
            )
            lines.append(
                "2. Confirm the validation gates above are addressed."
            )
            lines.append(
                "3. Apply `final-patch.diff` with `git apply --3way` and "
                "review each hunk."
            )
        else:
            lines.append(
                "1. Apply `final-patch.diff` with `git apply --3way`."
            )
            lines.append("2. Run the project test suite.")
            lines.append("3. Commit on the working branch.")
    target = out_dir / "final-plan.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def _write_final_patch(
    out_dir: Path,
    result: MergeResult,
    artifacts_by_id: Mapping[str, WorkerArtifact],
) -> Path:
    target = out_dir / "final-patch.diff"
    if result.winner is None or result.winner.worker_id not in artifacts_by_id:
        target.write_text("", encoding="utf-8")
        return target
    art = artifacts_by_id[result.winner.worker_id]
    # We deliberately do not splice or rewrite the diff — what the
    # worker produced is what the human will apply.
    target.write_text(art.patch_diff, encoding="utf-8")
    return target


def _write_plain_english_summary(
    out_dir: Path,
    result: MergeResult,
    artifacts_by_id: Mapping[str, WorkerArtifact],
    scorecards: Sequence[Scorecard],
) -> Path:
    """A one-page, jargon-free summary aimed at the project owner.

    No tables, no schema names — short sentences a human can skim from
    a phone notification and decide whether to look at the rest.
    """
    lines: list[str] = ["# What happened", ""]
    n_workers = len(scorecards)
    if n_workers == 0:
        lines.append("No workers ran. There is nothing to apply.")
    elif result.winner is None:
        lines.append(
            f"{n_workers} worker(s) ran. None of them produced a result "
            "muse was willing to ship — see `final-plan.md` for the "
            "rejection reasons."
        )
    else:
        w = result.winner
        verdict = (
            "needs your eyes before it lands"
            if result.manual_review_required
            else "looks ready to apply"
        )
        lines.append(
            f"{n_workers} worker(s) ran. The plan from "
            f"**{w.worker_id}** (profile `{w.profile}`) {verdict}."
        )
        lines.append("")
        art = artifacts_by_id.get(w.worker_id)
        if art and art.output_md:
            summary = _first_paragraph(art.output_md)
            if summary:
                lines.append(f"> {summary}")
                lines.append("")
        lines.append(
            f"It changed **{w.changed_file_count}** file(s) "
            f"({w.diff_line_count} line(s) of code)."
        )
        if w.touches_high_risk:
            lines.append(
                "It touches sensitive code (auth, billing, migrations, or "
                "similar) — muse only let it through because it added tests."
            )
        if w.adds_tests:
            lines.append("It added or updated tests.")
        if w.tests_passed is True:
            lines.append("Its validation run passed.")
        elif w.tests_passed is False:
            lines.append("Its validation run **failed** — read the report before applying.")
        else:
            lines.append("Its validation outcome is unclear from the captured output.")

    if result.rejected:
        lines.append("")
        lines.append("### Workers muse did not pick")
        for r in result.rejected:
            lines.append(f"- `{r.worker_id}`: {_first_sentence(r.reason)}")

    if result.runners_up:
        lines.append("")
        lines.append("### Other plans worth a look")
        for s in result.runners_up[:3]:
            note = s.notes[0] if s.notes else "no notes from scoring"
            lines.append(f"- `{s.worker_id}` (score {s.weighted_total:.2f}): {note}")

    if result.conflicts:
        lines.append("")
        lines.append(
            f"### Heads up: {len(result.conflicts)} file(s) were touched by "
            "more than one worker"
        )
        lines.append(
            "The merge engine never blends patches automatically. "
            "If you like ideas from another worker, lift them by hand."
        )

    if result.review_reasons:
        lines.append("")
        lines.append("### What still needs checking")
        for reason in result.review_reasons:
            lines.append(f"- {reason}")

    if result.winner is not None:
        lines.append("")
        lines.append(
            "### Next step\n\n"
            "Open `final-plan.md` for the full apply instructions, or "
            "`council-review.md` for the score breakdown across every "
            "worker."
        )

    target = out_dir / "plain-english-summary.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


_HEADING_RE = re.compile(r"^\s*#")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


def _first_paragraph(markdown: str) -> str:
    """Return the first non-heading paragraph of ``markdown``, trimmed.

    Used to pull a short summary out of each worker's ``output.md``.
    """
    chunk: list[str] = []
    for line in markdown.splitlines():
        if _HEADING_RE.match(line):
            if chunk:
                break
            continue
        stripped = line.strip()
        if not stripped:
            if chunk:
                break
            continue
        chunk.append(stripped)
        if len(chunk) >= 4:
            break
    return " ".join(chunk).strip()


def _first_sentence(text: str) -> str:
    """Return the first sentence of ``text`` (or all of it if shorter)."""
    parts = _SENTENCE_END_RE.split(text.strip(), maxsplit=1)
    return parts[0] if parts else text


# ──────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────


def run_merge(
    workers_dir: Path,
    out_dir: Path,
    *,
    artifacts: Optional[Sequence[WorkerArtifact]] = None,
    user_profile: Optional[Mapping[str, Any]] = None,
    decision_ledger: Optional[Sequence[Mapping[str, Any]]] = None,
) -> MergeResult:
    """Score and merge every worker under ``workers_dir``.

    Writes the six canonical merge artifacts into ``out_dir``:

      - ``scorecard.json``
      - ``council-review.md``
      - ``conflict-report.md``
      - ``final-plan.md``
      - ``final-patch.diff``
      - ``plain-english-summary.md``

    Returns a `MergeResult` so callers can branch on whether the run
    requires manual review. ``artifacts`` may be supplied by tests to
    skip the filesystem scan; in production it's None and we discover
    them ourselves. ``user_profile`` and ``decision_ledger`` are
    optional bias inputs passed through to the scoring layer.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    if artifacts is None:
        worker_dirs = discover_workers(workers_dir)
        artifacts = [load_artifact(d) for d in worker_dirs]

    scorecards = [
        score_artifact(
            a,
            user_profile=user_profile,
            decision_ledger=decision_ledger,
        )
        for a in artifacts
    ]
    result = select_winner(artifacts, scorecards)
    result.output_dir = out_dir

    by_id = {a.worker_id: a for a in artifacts}

    _write_scorecard_json(out_dir, result, scorecards)
    _write_council_review(out_dir, result, by_id, scorecards)
    _write_conflict_report(out_dir, result)
    _write_final_plan(out_dir, result, by_id)
    _write_final_patch(out_dir, result, by_id)
    _write_plain_english_summary(out_dir, result, by_id, scorecards)

    return result


__all__ = [
    "FileConflict",
    "HIGH_RISK_TEST_REQUIRED",
    "MANUAL_REVIEW_FLOOR",
    "MergeResult",
    "RejectedWorker",
    "SCORE_FLOOR",
    "SECRETS_SAFETY_FLOOR",
    "run_merge",
    "select_winner",
]
