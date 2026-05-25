"""Scoring engine for parallel worker outputs.

Phase 14 of the Hermes local orchestrator. After several workers run
against the same task in their own sandboxes, each one drops a fixed
set of artifacts into its output directory:

    workers/<worker_id>/
        output.md              # human-readable narrative
        patch.diff             # unified diff against the repo
        changed-files.txt      # newline-separated file paths
        validation-output.txt  # captured stdout/stderr of validation/test run
        status.json            # structured metadata (declared success, model, etc.)

This module turns each directory into a `WorkerArtifact` and then into a
`Scorecard` across the sixteen Phase 14 categories. The categories
deliberately mix *correctness* signals (tests pass, diff applies
cleanly), *fit* signals (architecture, repo conventions, mobile, voice,
remote execution), *safety* signals (security, secrets), and *taste*
signals (UX, developer experience, jeremiah_fit). The merge engine in
`merge_engine.py` consumes the scorecards to choose a winner and
produce a final plan.

Design notes
------------

* **No LLM call in here.** Scoring is a pure function of the artifacts
  on disk plus a small handful of structural heuristics. That keeps the
  module unit-testable, deterministic, and cheap to re-run when the
  merge engine wants a second pass.
* **Scores are bounded floats in [0.0, 1.0].** A missing self-score
  resolves to 0.5 (soft-neutral) so a worker that simply omitted a
  category isn't punished as if it failed it.
* **status.json wins ties.** A worker that declares ``confidence`` or
  per-category ``self_scores`` will see those reflected in the final
  scorecard, *bounded* by the structural evidence — a worker can't talk
  itself into a 1.0 for correctness if its tests didn't run.
* **Optional user_profile** lets the orchestrator bias ``jeremiah_fit``
  and a few other taste categories toward the project owner's stated
  preferences without hard-coding them.
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
    "maintainability",
    "testability",
    "architecture_fit",
    "repo_fit",
    "security",
    "secrets_safety",
    "mobile_fit",
    "voice_fit",
    "remote_execution_fit",
    "developer_experience",
    "ui_ux",
    "speed",
    "cost_efficiency",
    "jeremiah_fit",
)


# Filenames the worker is expected to drop into its directory.
# ``validation-output.txt`` is the Phase 14 name; ``test-output.txt`` is
# accepted as a legacy alias so older workers keep working.
_VALIDATION_FILENAMES: tuple[str, ...] = (
    "validation-output.txt",
    "test-output.txt",
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


_MOBILE_PATH_HINTS: tuple[str, ...] = (
    "android",
    "termux",
    "apps/android",
    "ios",
    "/mobile",
    "react-native",
)


_VOICE_PATH_HINTS: tuple[str, ...] = (
    "voice",
    "tts",
    "stt",
    "whisper",
    "speech",
    "audio",
)


_DEV_EX_HINTS: tuple[str, ...] = (
    "cli",
    "docs/",
    "readme",
    "help",
    "error",
)


_VALIDATION_FAILURE_PATTERNS = re.compile(
    r"\b(FAILED|ERROR|Traceback|AssertionError|"
    r"tests? failed|FAIL:|test_.*\bfailed\b)\b",
    re.IGNORECASE,
)
_VALIDATION_SUCCESS_PATTERNS = re.compile(
    r"\b("
    r"passed|"
    r"\d+\s+passed"
    r"|ok\b"
    r"|\d+\s+tests?\s+ok"
    r")\b",
    re.IGNORECASE,
)


# Heuristic patterns that suggest a secret was committed by accident.
# These run against patch.diff *additions* (lines starting with "+").
# We deliberately keep the list short and high-precision — false
# positives here block merges, so we'd rather miss a clever exfil than
# flood every patch with "looks suspicious" notes.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"AKIA[0-9A-Z]{16}"),                   # AWS access key id
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),            # Google API key
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),               # GitHub personal token
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),       # GitHub fine-grained PAT
    re.compile(r"sk-[A-Za-z0-9]{20,}"),                # OpenAI / Anthropic style
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),       # Slack tokens
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), # PEM private keys
    re.compile(
        r"(?i)\b(?:api[_-]?key|secret|password|passwd|access[_-]?token)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"
    ),
)


# Patterns that hint at remote-execution unfriendliness (TTY-only,
# localhost-only, hard-coded user paths, etc.).
_REMOTE_UNFRIENDLY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bos\.isatty\b"),
    re.compile(r"\brequires?[_-]?tty\b", re.IGNORECASE),
    re.compile(r"127\.0\.0\.1|localhost"),
    re.compile(r"/home/[a-zA-Z0-9_-]+/"),
    re.compile(r"open(?:\s*\(|s\s+).*['\"]/(?:tmp|var)/[^'\"]+['\"]"),
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
    validation_output: str
    status: Mapping[str, Any]
    missing: tuple[str, ...] = ()

    # Legacy alias — older callers used ``test_output`` for what is now
    # ``validation_output``. Both names point at the same string.
    @property
    def test_output(self) -> str:
        return self.validation_output

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
    def diff_added_text(self) -> str:
        """Concatenation of all "+" lines in the diff, for content scans."""
        return "\n".join(
            line[1:]
            for line in self.patch_diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
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
    def touches_mobile(self) -> bool:
        for path in self.changed_files:
            lowered = path.lower()
            if any(hint in lowered for hint in _MOBILE_PATH_HINTS):
                return True
        return False

    @property
    def touches_voice(self) -> bool:
        for path in self.changed_files:
            lowered = path.lower()
            if any(hint in lowered for hint in _VOICE_PATH_HINTS):
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

    @property
    def adds_docs(self) -> bool:
        for path in self.changed_files:
            normalized = path.replace("\\", "/").lower()
            base = normalized.rsplit("/", 1)[-1]
            if normalized.startswith("docs/") or "/docs/" in normalized:
                return True
            if base in ("readme.md", "changelog.md") or base.endswith(".rst"):
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
        """Unweighted mean across the canonical categories.

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
        """Weighted mean — correctness and safety dominate.

        The merge engine uses ``weighted_total`` for ranking. The
        intuition is that a beautifully-written, well-architected
        change that fails its own tests is still worse than a clunky
        change that passes them — and a change that leaks a secret is
        unshippable no matter how good it looks otherwise.
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
    "secrets_safety": 2.5,
    "security": 2.2,
    "completeness": 1.5,
    "testability": 1.5,
    "maintainability": 1.2,
    "repo_fit": 1.2,
    "architecture_fit": 1.2,
    "ui_ux": 1.0,
    "developer_experience": 1.0,
    "remote_execution_fit": 1.0,
    "mobile_fit": 0.9,
    "voice_fit": 0.7,
    "speed": 0.8,
    "cost_efficiency": 0.8,
    "jeremiah_fit": 1.0,
}


def _resolve_validation_path(worker_dir: Path) -> Optional[Path]:
    """Return the validation-output path the worker actually wrote, if any."""
    for name in _VALIDATION_FILENAMES:
        candidate = worker_dir / name
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


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
    status_text = _read_text("status.json")

    validation_path = _resolve_validation_path(worker_dir)
    validation_text: Optional[str] = None
    if validation_path is not None:
        try:
            validation_text = validation_path.read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            validation_text = None

    missing_names: list[str] = []
    for name, content in (
        ("output.md", output_md),
        ("patch.diff", patch_diff),
        ("changed-files.txt", changed_text),
        ("status.json", status_text),
    ):
        if content is None:
            missing_names.append(name)
    if validation_text is None:
        # Report under the canonical name; the legacy alias is a
        # convenience for old workers and shouldn't shape the missing
        # list.
        missing_names.append("validation-output.txt")

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
        validation_output=validation_text or "",
        status=status,
        missing=tuple(missing_names),
    )


def discover_workers(root: Path) -> list[Path]:
    """Return the immediate subdirectories of ``root`` in sorted order.

    Used by the merge engine to walk ``workers/`` without forcing each
    caller to re-implement the same listing logic.
    """
    if not root.exists() or not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir())


def _validation_outcome(text: str) -> Optional[bool]:
    """Best-effort classification of a worker's validation output.

    Returns True if we saw success signals and no failure signals,
    False if we saw failure signals, and None if the output was empty
    or ambiguous (the merge engine treats None as "validation wasn't
    run", which is itself a negative signal for high-risk code).
    """
    if not text.strip():
        return None
    has_failure = bool(_VALIDATION_FAILURE_PATTERNS.search(text))
    has_success = bool(_VALIDATION_SUCCESS_PATTERNS.search(text))
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


def _scan_secrets(diff_added_text: str) -> list[str]:
    """Return human-readable hits for any secret-like pattern in the diff."""
    hits: list[str] = []
    seen: set[str] = set()
    for pattern in _SECRET_PATTERNS:
        for match in pattern.finditer(diff_added_text):
            snippet = match.group(0)
            # Don't leak the actual secret into the scorecard — just
            # show enough to make the pattern recognisable.
            redacted = snippet[:6] + "…" if len(snippet) > 6 else snippet
            label = f"{pattern.pattern[:40]} → {redacted}"
            if label in seen:
                continue
            seen.add(label)
            hits.append(label)
    return hits


def _scan_remote_unfriendly(text: str) -> int:
    """Count remote-execution-unfriendly patterns in the supplied text."""
    return sum(1 for p in _REMOTE_UNFRIENDLY_PATTERNS if p.search(text))


def _profile_score(user_profile: Optional[Mapping[str, Any]], category: str) -> Optional[float]:
    """Pull a per-category override from the user profile, if present.

    The user profile is an open-ended dict supplied by the orchestrator;
    its ``category_preferences`` key, if a mapping, can boost or
    suppress specific categories on a per-worker basis. Anything not
    found returns None.
    """
    if not isinstance(user_profile, Mapping):
        return None
    prefs = user_profile.get("category_preferences")
    if not isinstance(prefs, Mapping):
        return None
    raw = prefs.get(category)
    if raw is None:
        return None
    try:
        return _bounded(float(raw))
    except (TypeError, ValueError):
        return None


def score_artifact(
    artifact: WorkerArtifact,
    *,
    user_profile: Optional[Mapping[str, Any]] = None,
    decision_ledger: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Scorecard:
    """Score one worker across all 16 categories.

    The implementation is intentionally a flat block of small heuristics
    rather than a clever model: each category's contribution is easy to
    read, easy to test, and easy to revise.

    ``user_profile`` (optional) lets the caller bias category outcomes
    toward the project owner's stated preferences. ``decision_ledger``
    (optional) is a sequence of prior decision entries — currently only
    used to surface a note when the same worker has been rejected
    before for the same reason.
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

    validation_outcome = _validation_outcome(artifact.validation_output)
    card.tests_passed = validation_outcome
    diff_added_text = artifact.diff_added_text

    if decision_ledger:
        prior_rejections = sum(
            1
            for entry in decision_ledger
            if isinstance(entry, Mapping)
            and entry.get("worker_id") == artifact.worker_id
            and entry.get("outcome") == "rejected"
        )
        if prior_rejections:
            card.notes.append(
                f"worker has {prior_rejections} prior rejection(s) on the ledger"
            )

    # ── correctness ───────────────────────────────────────────────────
    if validation_outcome is True and artifact.declared_success:
        correctness = 0.95
        card.notes.append("validation passed and worker declared success")
    elif validation_outcome is True:
        correctness = 0.8
        card.notes.append("validation passed but worker did not declare success")
    elif validation_outcome is False:
        correctness = 0.15
        card.flags.append("validation reported failures")
    elif artifact.declared_success and artifact.patch_diff.strip():
        correctness = 0.55
        card.notes.append("worker declared success but no validation evidence")
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

    # ── testability ───────────────────────────────────────────────────
    if artifact.adds_tests and validation_outcome is True:
        testability = 0.95
    elif artifact.adds_tests:
        testability = 0.7
        card.notes.append("worker added tests but did not show them passing")
    elif validation_outcome is True:
        testability = 0.6
        card.notes.append("validation passed but no new tests were added")
    elif artifact.touches_high_risk:
        testability = 0.2
        card.flags.append("high-risk change without tests")
    else:
        testability = 0.4
    card.scores["testability"] = testability

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

    # ── repo_fit ──────────────────────────────────────────────────────
    repo_fit = 0.6
    if artifact.changed_file_count and not artifact.patch_diff.strip():
        repo_fit = 0.2
        card.flags.append("changed-files.txt has paths but patch.diff is empty")
    elif "diff --git" in artifact.patch_diff:
        repo_fit = 0.8
    card.scores["repo_fit"] = repo_fit

    # ── security ──────────────────────────────────────────────────────
    security = _clamped_self_score(artifact.status, "security")
    if security is None:
        if artifact.touches_high_risk and not artifact.adds_tests:
            security = 0.15
            card.flags.append("touches high-risk paths without tests")
        elif artifact.touches_high_risk and validation_outcome is True:
            security = 0.8
        elif validation_outcome is False:
            security = 0.25
        elif diff > 600:
            security = 0.45
        elif artifact.declared_success and validation_outcome is True:
            security = 0.85
        else:
            security = 0.6
    card.scores["security"] = security

    # ── secrets_safety ────────────────────────────────────────────────
    secret_hits = _scan_secrets(diff_added_text)
    if secret_hits:
        secrets_safety = 0.0
        card.flags.append(
            f"possible secret(s) in diff: {'; '.join(secret_hits[:3])}"
        )
    else:
        secrets_safety = _clamped_self_score(artifact.status, "secrets_safety")
        if secrets_safety is None:
            # No suspicious additions and no claim from the worker — treat
            # as soft-positive, but only if there's *something* to score.
            if artifact.patch_diff.strip():
                secrets_safety = 0.9
            else:
                secrets_safety = 0.5
    card.scores["secrets_safety"] = secrets_safety

    # ── mobile_fit ────────────────────────────────────────────────────
    mobile_fit = _clamped_self_score(artifact.status, "mobile_fit")
    if mobile_fit is None:
        if artifact.touches_mobile and validation_outcome is True:
            mobile_fit = 0.85
        elif artifact.touches_mobile:
            mobile_fit = 0.65
            card.notes.append("touches mobile paths without validation")
        elif artifact.patch_diff.strip():
            # Doesn't touch mobile surfaces at all — neutral, on the
            # principle that "didn't break what it didn't touch".
            mobile_fit = 0.6
        else:
            mobile_fit = 0.5
    card.scores["mobile_fit"] = mobile_fit

    # ── voice_fit ─────────────────────────────────────────────────────
    voice_fit = _clamped_self_score(artifact.status, "voice_fit")
    if voice_fit is None:
        if artifact.touches_voice and validation_outcome is True:
            voice_fit = 0.85
        elif artifact.touches_voice:
            voice_fit = 0.6
            card.notes.append("touches voice paths without validation")
        elif artifact.patch_diff.strip():
            voice_fit = 0.6
        else:
            voice_fit = 0.5
    card.scores["voice_fit"] = voice_fit

    # ── remote_execution_fit ──────────────────────────────────────────
    remote_execution_fit = _clamped_self_score(artifact.status, "remote_execution_fit")
    if remote_execution_fit is None:
        unfriendly = _scan_remote_unfriendly(artifact.patch_diff)
        if unfriendly == 0:
            remote_execution_fit = 0.85
        elif unfriendly <= 2:
            remote_execution_fit = 0.6
        else:
            remote_execution_fit = 0.4
            card.notes.append(
                f"{unfriendly} remote-unfriendly pattern(s) in diff "
                "(tty / localhost / hard-coded user paths)"
            )
    card.scores["remote_execution_fit"] = remote_execution_fit

    # ── developer_experience ──────────────────────────────────────────
    dev_ex = _clamped_self_score(artifact.status, "developer_experience")
    if dev_ex is None:
        score = 0.5
        if len(artifact.output_md) >= 600 and artifact.output_md.count("\n") >= 10:
            score = 0.8
        elif artifact.output_md.strip():
            score = 0.6
        if artifact.adds_docs:
            score = min(1.0, score + 0.1)
            card.notes.append("worker added or updated documentation")
        if any(
            hint in path.lower() for path in artifact.changed_files for hint in _DEV_EX_HINTS
        ):
            score = min(1.0, score + 0.05)
        dev_ex = score
    card.scores["developer_experience"] = dev_ex

    # ── ui_ux ─────────────────────────────────────────────────────────
    ui_ux = _clamped_self_score(artifact.status, "ui_ux")
    if ui_ux is None:
        # Look back at ux_quality for legacy self-scores so old workers
        # don't lose all signal in this category.
        ui_ux = _clamped_self_score(artifact.status, "ux_quality")
    if ui_ux is None:
        if len(artifact.output_md) >= 500 and artifact.output_md.count("\n") >= 8:
            ui_ux = 0.75
        elif artifact.output_md.strip():
            ui_ux = 0.55
        else:
            ui_ux = 0.3
    card.scores["ui_ux"] = ui_ux

    # ── speed ─────────────────────────────────────────────────────────
    speed = _clamped_self_score(artifact.status, "speed")
    if speed is None:
        elapsed = artifact.status.get("elapsed_seconds")
        if isinstance(elapsed, (int, float)) and elapsed > 0:
            # 0 - 60s -> ~1.0, 300s -> ~0.67, 900s+ -> ~0.0
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

    # ── jeremiah_fit ──────────────────────────────────────────────────
    # "jeremiah_fit" tracks alignment with the project owner's stated
    # preferences (private-personal-orchestrator, no telemetry, no
    # autonomous external actions, manual handoff by default). Workers
    # may self-score this; absent that, we apply a small bias from
    # secrets_safety / security / remote_execution_fit and let the
    # user_profile (if present) override.
    jeremiah_fit = _profile_score(user_profile, "jeremiah_fit")
    if jeremiah_fit is None:
        jeremiah_fit = _clamped_self_score(artifact.status, "jeremiah_fit")
    if jeremiah_fit is None:
        jeremiah_fit = _bounded(
            0.4 * card.scores["secrets_safety"]
            + 0.3 * card.scores["security"]
            + 0.3 * card.scores["remote_execution_fit"]
        )
    card.scores["jeremiah_fit"] = jeremiah_fit

    # Profile-driven overrides for any other category.
    if isinstance(user_profile, Mapping):
        for cat in SCORE_CATEGORIES:
            override = _profile_score(user_profile, cat)
            if override is not None and cat != "jeremiah_fit":
                card.scores[cat] = override

    # Final pass: clamp every score and ensure every category is set.
    for cat in SCORE_CATEGORIES:
        if cat not in card.scores:
            card.scores[cat] = 0.5
        else:
            card.scores[cat] = _bounded(card.scores[cat])

    return card


def score_workers(
    workers: Sequence[WorkerArtifact],
    *,
    user_profile: Optional[Mapping[str, Any]] = None,
    decision_ledger: Optional[Sequence[Mapping[str, Any]]] = None,
) -> list[Scorecard]:
    """Score a sequence of workers in input order."""
    return [
        score_artifact(w, user_profile=user_profile, decision_ledger=decision_ledger)
        for w in workers
    ]


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
