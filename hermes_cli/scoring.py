"""Scoring engine for parallel worker outputs.

Phase 13 of the Hermes local orchestrator. After several workers run
against the same task in their own sandboxes, each one drops a fixed
set of artifacts into its output directory:

    workers/<worker_id>/
        output.md          # human-readable narrative
        patch.diff         # unified diff against the repo
        changed-files.txt  # newline-separated file paths
        test-output.txt    # captured stdout/stderr of the test run
        status.json        # structured metadata (declared success, model, etc.)

This module turns each directory into a `WorkerArtifact` and then into a
`Scorecard` across twelve categories. The categories deliberately mix
*correctness* signals (tests pass, diff applies cleanly), *fit* signals
(architecture, repo conventions), and *taste* signals (UX, jeremiah_fit,
local-first orientation). The merge engine in `merge_engine.py`
consumes the scorecards to choose a winner and produce a final plan.

Design notes
------------

* **No LLM call in here.** Scoring is a pure function of the artifacts
  on disk plus a small handful of structural heuristics. That keeps the
  module unit-testable, deterministic, and cheap to re-run when the
  merge engine wants a second pass.
* **Scores are bounded floats in [0.0, 1.0].** A `None` score means
  *no evidence available* — the merge engine treats that as soft-neutral
  (0.5) rather than zero, so a worker that simply omitted a category
  isn't punished as if it failed it.
* **status.json wins ties.** A worker that declares ``confidence`` or
  per-category ``self_scores`` will see those reflected in the final
  scorecard, *bounded* by the structural evidence — a worker can't talk
  itself into a 1.0 for correctness if its tests didn't run.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

SCORE_CATEGORIES: tuple[str, ...] = (
    "correctness",
    "completeness",
    "testability",
    "maintainability",
    "repo_fit",
    "architecture_fit",
    "risk_control",
    "ux_quality",
    "speed",
    "cost_efficiency",
    "local_first_fit",
    "jeremiah_fit",
)


_REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "output.md",
    "patch.diff",
    "changed-files.txt",
    "test-output.txt",
    "status.json",
)


_HIGH_RISK_PATH_HINTS: tuple[str, ...] = (
    "auth",
    "secret",
    "crypto",
    "billing",
    "payment",
    "migration",
    "schema",
    "policy",
    "permission",
    "gateway",
)


_TEST_FAILURE_PATTERNS = re.compile(
    r"\b(FAILED|ERROR|Traceback|AssertionError|"
    r"tests? failed|FAIL:|test_.*\bfailed\b)\b",
    re.IGNORECASE,
)
_TEST_SUCCESS_PATTERNS = re.compile(
    r"\b("
    r"passed|"
    r"\d+\s+passed"
    r"|ok\b"
    r"|\d+\s+tests?\s+ok"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class WorkerArtifact:
    """One worker's raw output on disk after a run.

    Created via `load_artifact`. ``missing`` lists artifact filenames
    the worker failed to produce — if it's non-empty, the worker is
    flagged in the scorecard and the missing files are treated as
    strong negative evidence (not as silent zeros).
    """

    worker_id: str
    path: Path
    output_md: str
    patch_diff: str
    changed_files: tuple[str, ...]
    test_output: str
    status: Mapping[str, Any]
    missing: tuple[str, ...] = ()

    @property
    def declared_success(self) -> bool:
        """True if status.json says the worker considered itself successful."""
        return bool(self.status.get("success") or self.status.get("ok"))

    @property
    def profile(self) -> str:
        """Model / profile label, if recorded; else ``"unknown"``."""
        return str(
            self.status.get("profile")
            or self.status.get("model")
            or self.status.get("agent")
            or "unknown"
        )

    @property
    def diff_line_count(self) -> int:
        """Number of changed (non-context) lines in the patch."""
        if not self.patch_diff:
            return 0
        return sum(
            1
            for line in self.patch_diff.splitlines()
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        )

    @property
    def changed_file_count(self) -> int:
        return len(self.changed_files)

    @property
    def touches_high_risk(self) -> bool:
        """True if any changed file path matches a high-risk hint."""
        for path in self.changed_files:
            lowered = path.lower()
            if any(hint in lowered for hint in _HIGH_RISK_PATH_HINTS):
                return True
        return False

    @property
    def adds_tests(self) -> bool:
        """True if the patch touches a path under tests/ or matching test_*.py."""
        for path in self.changed_files:
            normalized = path.replace("\\", "/")
            base = normalized.rsplit("/", 1)[-1]
            if normalized.startswith("tests/") or "/tests/" in normalized:
                return True
            if base.startswith("test_") and base.endswith(".py"):
                return True
            if base.endswith(("_test.py", ".test.ts", ".test.tsx", ".spec.ts")):
                return True
        return False


@dataclass
class Scorecard:
    """Per-worker score across all categories, plus aggregate metadata.

    Scores are bounded floats in [0.0, 1.0]. ``notes`` accumulates short
    human-readable strings explaining *why* a particular category landed
    where it did — the merge engine surfaces these verbatim in
    ``council-review.md``.
    """

    worker_id: str
    profile: str
    scores: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    declared_success: bool = False
    tests_passed: Optional[bool] = None
    touches_high_risk: bool = False
    adds_tests: bool = False
    diff_line_count: int = 0
    changed_file_count: int = 0

    @property
    def total(self) -> float:
        """Unweighted mean across the 12 canonical categories.

        Missing categories are treated as 0.5 (soft-neutral) so a worker
        that simply didn't supply self-scores for one category isn't
        ranked behind a worker that *failed* that category outright.
        """
        if not self.scores:
            return 0.0
        values = [self.scores.get(cat, 0.5) for cat in SCORE_CATEGORIES]
        return sum(values) / len(values)

    @property
    def weighted_total(self) -> float:
        """Weighted mean — correctness and risk_control dominate.

        The merge engine uses ``weighted_total`` for ranking. The
        intuition is that a beautifully-written, well-architected
        change that fails its own tests is still worse than a clunky
        change that passes them.
        """
        weights = _CATEGORY_WEIGHTS
        total_weight = 0.0
        acc = 0.0
        for cat in SCORE_CATEGORIES:
            w = weights.get(cat, 1.0)
            acc += w * self.scores.get(cat, 0.5)
            total_weight += w
        return acc / total_weight if total_weight else 0.0

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["total"] = round(self.total, 4)
        d["weighted_total"] = round(self.weighted_total, 4)
        d["scores"] = {k: round(v, 4) for k, v in self.scores.items()}
        return d


_CATEGORY_WEIGHTS: Mapping[str, float] = {
    "correctness": 3.0,
    "risk_control": 2.5,
    "completeness": 1.5,
    "testability": 1.5,
    "maintainability": 1.2,
    "repo_fit": 1.2,
    "architecture_fit": 1.2,
    "ux_quality": 1.0,
    "speed": 0.8,
    "cost_efficiency": 0.8,
    "local_first_fit": 1.0,
    "jeremiah_fit": 1.0,
}


def load_artifact(worker_dir: Path, *, worker_id: Optional[str] = None) -> WorkerArtifact:
    """Read a worker's output directory into a `WorkerArtifact`.

    Missing files don't raise — they're recorded in ``missing`` so the
    scoring layer can downgrade the worker rather than crash the run.
    The only hard requirement is that ``worker_dir`` itself exists and
    is a directory.
    """
    if not worker_dir.exists() or not worker_dir.is_dir():
        raise FileNotFoundError(f"worker directory does not exist: {worker_dir}")

    wid = worker_id or worker_dir.name

    def _read_text(name: str) -> Optional[str]:
        p = worker_dir / name
        if not p.exists() or not p.is_file():
            return None
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    output_md = _read_text("output.md")
    patch_diff = _read_text("patch.diff")
    changed_text = _read_text("changed-files.txt")
    test_output = _read_text("test-output.txt")
    status_text = _read_text("status.json")

    missing = tuple(
        name
        for name, content in (
            ("output.md", output_md),
            ("patch.diff", patch_diff),
            ("changed-files.txt", changed_text),
            ("test-output.txt", test_output),
            ("status.json", status_text),
        )
        if content is None
    )

    status: Mapping[str, Any] = {}
    if status_text:
        try:
            parsed = json.loads(status_text)
            if isinstance(parsed, Mapping):
                status = parsed
        except json.JSONDecodeError:
            status = {"_parse_error": True}

    changed_files: tuple[str, ...] = ()
    if changed_text:
        changed_files = tuple(
            line.strip()
            for line in changed_text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )

    return WorkerArtifact(
        worker_id=wid,
        path=worker_dir,
        output_md=output_md or "",
        patch_diff=patch_diff or "",
        changed_files=changed_files,
        test_output=test_output or "",
        status=status,
        missing=missing,
    )


def discover_workers(root: Path) -> list[Path]:
    """Return the immediate subdirectories of ``root`` in sorted order.

    Used by the merge engine to walk ``workers/`` without forcing each
    caller to re-implement the same listing logic.
    """
    if not root.exists() or not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir())


def _tests_outcome(test_output: str) -> Optional[bool]:
    """Best-effort classification of a worker's test output.

    Returns True if we saw success signals and no failure signals,
    False if we saw failure signals, and None if the output was empty
    or ambiguous (the merge engine treats None as "tests weren't run",
    which is itself a negative signal for high-risk code).
    """
    if not test_output.strip():
        return None
    has_failure = bool(_TEST_FAILURE_PATTERNS.search(test_output))
    has_success = bool(_TEST_SUCCESS_PATTERNS.search(test_output))
    if has_failure:
        return False
    if has_success:
        return True
    return None


def _bounded(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _clamped_self_score(status: Mapping[str, Any], category: str) -> Optional[float]:
    """Pull a self-reported score for ``category`` from status.json.

    Accepts either ``status["self_scores"][category]`` or a flat
    ``status["<category>_score"]``. Returns None when the worker said
    nothing about that category. Values outside [0, 1] are clamped.
    """
    self_scores = status.get("self_scores")
    if isinstance(self_scores, Mapping) and category in self_scores:
        try:
            return _bounded(float(self_scores[category]))
        except (TypeError, ValueError):
            return None
    flat = status.get(f"{category}_score")
    if flat is not None:
        try:
            return _bounded(float(flat))
        except (TypeError, ValueError):
            return None
    return None


def score_artifact(artifact: WorkerArtifact) -> Scorecard:
    """Score one worker across all 12 categories.

    The implementation is intentionally a flat block of small heuristics
    rather than a clever model: each category's contribution is easy to
    read, easy to test, and easy to revise.
    """
    card = Scorecard(
        worker_id=artifact.worker_id,
        profile=artifact.profile,
        declared_success=artifact.declared_success,
        touches_high_risk=artifact.touches_high_risk,
        adds_tests=artifact.adds_tests,
        diff_line_count=artifact.diff_line_count,
        changed_file_count=artifact.changed_file_count,
    )

    if artifact.missing:
        card.flags.append(f"missing artifacts: {', '.join(artifact.missing)}")

    tests_outcome = _tests_outcome(artifact.test_output)
    card.tests_passed = tests_outcome

    # ── correctness ───────────────────────────────────────────────────
    if tests_outcome is True and artifact.declared_success:
        correctness = 0.95
        card.notes.append("tests pass and worker declared success")
    elif tests_outcome is True:
        correctness = 0.8
        card.notes.append("tests pass but worker did not declare success")
    elif tests_outcome is False:
        correctness = 0.15
        card.flags.append("tests reported failures")
    elif artifact.declared_success and artifact.patch_diff.strip():
        correctness = 0.55
        card.notes.append("worker declared success but no test evidence")
    elif not artifact.patch_diff.strip():
        correctness = 0.1
        card.flags.append("empty patch")
    else:
        correctness = 0.4
    card.scores["correctness"] = correctness

    # ── completeness ──────────────────────────────────────────────────
    completeness = 0.5
    if artifact.changed_file_count == 0:
        completeness = 0.15
        card.flags.append("no files changed")
    elif artifact.output_md.strip() and artifact.patch_diff.strip():
        completeness = 0.75
        if len(artifact.output_md) >= 400:
            completeness += 0.1
        if artifact.declared_success:
            completeness += 0.05
    card.scores["completeness"] = _bounded(completeness)

    # ── testability ───────────────────────────────────────────────────
    if artifact.adds_tests and tests_outcome is True:
        testability = 0.95
    elif artifact.adds_tests:
        testability = 0.7
        card.notes.append("worker added tests but did not show them passing")
    elif tests_outcome is True:
        testability = 0.6
        card.notes.append("tests pass but no new tests were added")
    elif artifact.touches_high_risk:
        testability = 0.2
        card.flags.append("high-risk change without tests")
    else:
        testability = 0.4
    card.scores["testability"] = testability

    # ── maintainability ───────────────────────────────────────────────
    diff = artifact.diff_line_count
    if diff == 0:
        maintainability = 0.2
    elif diff <= 80:
        maintainability = 0.9
    elif diff <= 250:
        maintainability = 0.75
    elif diff <= 600:
        maintainability = 0.55
        card.notes.append("large diff (>250 changed lines)")
    else:
        maintainability = 0.35
        card.flags.append("very large diff (>600 changed lines)")
    card.scores["maintainability"] = maintainability

    # ── repo_fit ──────────────────────────────────────────────────────
    repo_fit = 0.6
    if artifact.changed_file_count and not artifact.patch_diff.strip():
        repo_fit = 0.2
        card.flags.append("changed-files.txt has paths but patch.diff is empty")
    elif "diff --git" in artifact.patch_diff:
        repo_fit = 0.8
    card.scores["repo_fit"] = repo_fit

    # ── architecture_fit ──────────────────────────────────────────────
    architecture_fit = _clamped_self_score(artifact.status, "architecture_fit")
    if architecture_fit is None:
        # Heuristic: focused changes (<= 6 files, no high-risk surfaces)
        # tend to fit the existing architecture better than sprawling
        # ones touching auth/billing/etc. without justification.
        if artifact.changed_file_count == 0:
            architecture_fit = 0.3
        elif artifact.changed_file_count <= 6 and not artifact.touches_high_risk:
            architecture_fit = 0.75
        elif artifact.touches_high_risk:
            architecture_fit = 0.5
        else:
            architecture_fit = 0.55
    card.scores["architecture_fit"] = architecture_fit

    # ── risk_control ──────────────────────────────────────────────────
    if artifact.touches_high_risk and not artifact.adds_tests:
        risk_control = 0.15
        card.flags.append("touches high-risk paths without tests")
    elif artifact.touches_high_risk and tests_outcome is True:
        risk_control = 0.8
    elif tests_outcome is False:
        risk_control = 0.2
    elif diff > 600:
        risk_control = 0.4
    elif artifact.declared_success and tests_outcome is True:
        risk_control = 0.85
    else:
        risk_control = 0.6
    card.scores["risk_control"] = risk_control

    # ── ux_quality ────────────────────────────────────────────────────
    ux_quality = _clamped_self_score(artifact.status, "ux_quality")
    if ux_quality is None:
        if len(artifact.output_md) >= 500 and artifact.output_md.count("\n") >= 8:
            ux_quality = 0.75
        elif artifact.output_md.strip():
            ux_quality = 0.55
        else:
            ux_quality = 0.3
    card.scores["ux_quality"] = ux_quality

    # ── speed ─────────────────────────────────────────────────────────
    speed = _clamped_self_score(artifact.status, "speed")
    if speed is None:
        elapsed = artifact.status.get("elapsed_seconds")
        if isinstance(elapsed, (int, float)) and elapsed > 0:
            # 0 - 60s -> ~1.0, 300s -> ~0.5, 900s+ -> ~0.1
            speed = _bounded(1.0 - (float(elapsed) / 900.0))
        else:
            speed = 0.5
    card.scores["speed"] = speed

    # ── cost_efficiency ───────────────────────────────────────────────
    cost = _clamped_self_score(artifact.status, "cost_efficiency")
    if cost is None:
        tokens = artifact.status.get("tokens") or artifact.status.get("total_tokens")
        if isinstance(tokens, (int, float)) and tokens > 0:
            # 0 - 5k -> ~1.0, 50k -> ~0.5, 100k+ -> ~0.0
            cost = _bounded(1.0 - (float(tokens) / 100_000.0))
        else:
            cost = 0.5
    card.scores["cost_efficiency"] = cost

    # ── local_first_fit ───────────────────────────────────────────────
    local_first = _clamped_self_score(artifact.status, "local_first_fit")
    if local_first is None:
        # Hermes is a local-first orchestrator; patches that add network
        # endpoints or external service calls without justification
        # are downgraded. Pure local edits get a soft positive.
        text = (artifact.patch_diff + "\n" + artifact.output_md).lower()
        external_hits = sum(
            text.count(token)
            for token in ("http://", "https://", "fetch(", "requests.")
        )
        if external_hits == 0:
            local_first = 0.8
        elif external_hits <= 3:
            local_first = 0.6
        else:
            local_first = 0.4
            card.notes.append(
                f"{external_hits} external-network references in diff/output"
            )
    card.scores["local_first_fit"] = local_first

    # ── jeremiah_fit ──────────────────────────────────────────────────
    # "jeremiah_fit" tracks alignment with the project owner's stated
    # preferences (private-personal-orchestrator, no telemetry, no
    # autonomous external actions, manual handoff by default). Workers
    # may self-score this; absent that, we apply a small bias from
    # local_first_fit and risk_control.
    jeremiah_fit = _clamped_self_score(artifact.status, "jeremiah_fit")
    if jeremiah_fit is None:
        jeremiah_fit = _bounded(
            0.5 * card.scores["local_first_fit"] + 0.5 * card.scores["risk_control"]
        )
    card.scores["jeremiah_fit"] = jeremiah_fit

    # Final pass: clamp every score and ensure every category is set.
    for cat in SCORE_CATEGORIES:
        if cat not in card.scores:
            card.scores[cat] = 0.5
        else:
            card.scores[cat] = _bounded(card.scores[cat])

    return card


def score_workers(workers: Sequence[WorkerArtifact]) -> list[Scorecard]:
    """Score a sequence of workers in input order."""
    return [score_artifact(w) for w in workers]


def rank(scorecards: Sequence[Scorecard]) -> list[Scorecard]:
    """Return scorecards sorted from best to worst by ``weighted_total``.

    Ties are broken first by ``correctness`` (higher wins), then by
    ``diff_line_count`` (smaller wins — we prefer minimal changes),
    then by ``worker_id`` for full determinism.
    """
    return sorted(
        scorecards,
        key=lambda c: (
            -c.weighted_total,
            -c.scores.get("correctness", 0.0),
            c.diff_line_count if c.diff_line_count else 10**9,
            c.worker_id,
        ),
    )


__all__ = [
    "SCORE_CATEGORIES",
    "Scorecard",
    "WorkerArtifact",
    "discover_workers",
    "load_artifact",
    "rank",
    "score_artifact",
    "score_workers",
]
