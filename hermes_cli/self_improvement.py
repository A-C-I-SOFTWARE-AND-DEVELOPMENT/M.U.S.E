"""Self-improvement loop — post-job learning pass.

Python side of the ``self-improvement-loop`` skill (see
``skills/self-improvement-loop/SKILL.md`` and the orchestration
companion in ``docs/orchestration/self-improvement-loop.md``).

What this module does
---------------------

After every coding job completes, this module reads the job's
artifact directory and produces:

* ``retrospective.md`` — short, human-readable narrative
* ``worker-performance.json`` — per-worker structured rollup
* ``routing-lessons.md`` — what should change about routing next time
* ``user-preference-updates.md`` — what the user told us, explicitly
  or by correction, that should travel forward as a preference
* a set of ``proposals/`` files (one JSON per finding) ready for the
  curator / monitor to promote

What it does NOT do
-------------------

* It does **not** auto-edit ``model-routing-policy.md``, the model
  registry, or any skill prompt directly. Every change rides through
  the curator drafts lane (see ``agent/curator.py``).
* It does **not** keep secrets in retrospectives. The redactor scrubs
  obvious credential patterns before any artifact is written.
* It does **not** promote single-event findings unless the operator
  marked them ``user_confirmed`` — that is the K=3 rule from the
  skill.
* It does **not** overfit to one failed job — see ``filter_overfit``.

The module is intentionally stdlib-only.
"""

from __future__ import annotations

import json
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence


# ---------------------------------------------------------------------------
# Constants — finding kinds, scorecard axes, evidence thresholds
# ---------------------------------------------------------------------------

FINDING_KINDS: tuple[str, ...] = (
    "skill_gap",
    "new_skill",
    "routing_miss",
    "prompt_regression",
    "tool_gap",
    "evidence_gap",
    "mission_drift",
)

# The standing quality scorecard — the same axes the
# ``best-coding-tool-mission`` and ``self-improvement-loop`` skills
# document. Mirrored here so this module is self-contained.
SCORECARD_AXES: tuple[str, ...] = (
    "correctness",
    "maintainability",
    "testability",
    "architecture_fit",
    "developer_experience",
    "ui_ux",
    "speed",
    "cost_efficiency",
    "local_first_fit",
    "jeremiah_fit",
)

# A score this low blocks merge by default (per the mission skill).
BLOCKING_SCORE_THRESHOLD = 4

# K=3 confirmation rule (from the skill): same (kind, target) pair
# must fire across this many consecutive jobs before auto-promotion.
K_CONFIRMATIONS = 3

# A single low score on a single axis on a single job is **not** enough
# to justify a routing change. We require the same problem to repeat,
# OR a strong corroborating signal (validation failure on the same
# worker, explicit user correction, etc.). This is the "do not overfit
# to one failed run" rule.
WEAK_EVIDENCE_THRESHOLD = 1


# ---------------------------------------------------------------------------
# Secret redaction — never put credentials in a retrospective
# ---------------------------------------------------------------------------

# Patterns adapted from agent/redact.py but kept independent so this
# module loads in stripped-down environments (Termux, slim CI images)
# where the full agent package isn't installed.
_SECRET_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),                  # OpenAI / Anthropic
    re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),              # Anthropic explicit
    # GitHub PAT (classic) + OAuth (ghp_/gho_/ghu_/ghs_/ghr_).
    re.compile(r"gh[pousr]_[A-Za-z0-9]{16,255}"),
    # Fine-grained PATs (issued by GitHub since 2022). Format documented at
    # https://github.blog/...: literal prefix ``github_pat_`` followed by
    # two underscore-separated alphanumeric segments. Match defensively
    # — accept lengths from 36 to ~96 so future format tweaks still get
    # redacted.
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    # GitHub Apps refresh tokens.
    re.compile(r"ghr_[A-Za-z0-9_]{20,255}"),
    # GitHub server-to-server tokens.
    re.compile(r"ghs_[A-Za-z0-9_]{20,255}"),
    re.compile(r"glpat-[A-Za-z0-9_-]{16,}"),               # GitLab PAT
    re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"),           # Slack tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),                       # AWS access key
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),                 # Google API key
    re.compile(
        r"(?i)(api[_-]?key|password|secret|token|"
        r"bearer)\s*[:=]\s*['\"]?[A-Za-z0-9_\-+/=]{8,}['\"]?"
    ),
)


def redact_secrets(text: str) -> str:
    """Return ``text`` with any obvious credential patterns masked.

    The replacement is the literal string ``"[REDACTED]"``. The intent
    is to keep secrets out of retrospectives and routing notes that may
    be checked into git or sent to a cloud curator. This is a guard
    rail — for *known* secret storage, use ``agent/redact.py``.
    """
    if not text:
        return text
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


# ---------------------------------------------------------------------------
# Proposal dataclass — same shape as the skill describes
# ---------------------------------------------------------------------------


@dataclass
class Proposal:
    """One self-improvement proposal — the JSON shape the skill defines.

    Mirrors ``skills/self-improvement-loop/SKILL.md``. ``kind`` must be
    one of :data:`FINDING_KINDS`. ``evidence_event_count`` starts at 1
    on first sighting and gets bumped by the consecutive-jobs tracker.
    """

    kind: str
    target: str
    summary: str
    rationale: str
    evidence: tuple[str, ...] = ()
    evidence_event_count: int = 1
    proposed_change: str = ""
    scorecard_delta_expected: Mapping[str, str] = field(default_factory=dict)
    principles: tuple[str, ...] = ()
    reversible: bool = True
    extra: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in FINDING_KINDS:
            raise ValueError(
                f"kind must be one of {FINDING_KINDS}, got {self.kind!r}"
            )
        if self.evidence_event_count < 1:
            raise ValueError("evidence_event_count must be >= 1")

    def as_dict(self) -> dict:
        d = asdict(self)
        # Sanitize text fields — never leak a secret into a draft.
        for f in ("summary", "rationale", "proposed_change"):
            if isinstance(d.get(f), str):
                d[f] = redact_secrets(d[f])
        return d


# ---------------------------------------------------------------------------
# Promotion policy — apply / promote / defer
# ---------------------------------------------------------------------------


def promotion_decision(proposal: Proposal) -> str:
    """Return one of ``"apply"``, ``"promote"``, ``"defer"``.

    The rules are the ones the skill documents:

    * ``apply`` — additive, reversible, low-blast-radius changes:
      tag-only edits, additive routing-weight nudges by one notch.
      The proposal must (a) be reversible and (b) carry an
      ``extra.previous_value`` so the change can be undone.
    * ``promote`` — anything that changes a prompt, adds/removes a
      skill, reclassifies risk, or makes a non-trivial routing change.
      These ride through the curator drafts lane.
    * ``defer`` — single-event findings without
      ``extra.user_confirmed``, OR findings whose kind is unknown to
      the auto-promoter.
    """
    extra = dict(proposal.extra or {})
    user_confirmed = bool(extra.get("user_confirmed"))

    # K=3 confirmation rule + weak-evidence rule.
    if (
        proposal.evidence_event_count < K_CONFIRMATIONS
        and not user_confirmed
    ):
        return "defer"

    if proposal.kind in {"new_skill", "prompt_regression"}:
        # Always rides through the curator — never auto-applied.
        return "promote"

    if proposal.kind == "mission_drift":
        # High-priority but still human-gated — curator surfaces it
        # immediately, but we do not auto-apply mission-related
        # changes.
        return "promote"

    if proposal.kind in {"skill_gap", "tool_gap", "evidence_gap"}:
        # Need the curator to evaluate against the broader skill /
        # plugin layout.
        return "promote"

    if proposal.kind == "routing_miss":
        # Only an additive nudge with *meaningful* rollback metadata
        # can be applied directly. Anything bigger goes to the curator.
        # "Meaningful" means: the proposal records both
        #   - the previous value of whatever it nudges, AND
        #   - the exact size of the nudge (so the curator / monitor
        #     can verify the change is really one notch).
        # A placeholder like ``"unchanged"`` or ``None`` is *not*
        # rollback metadata; without it we cannot revert (Principle 7),
        # so we refuse to auto-apply and route to the curator instead.
        is_additive_nudge = bool(extra.get("additive_nudge"))
        previous_value = extra.get("previous_value")
        has_meaningful_previous = (
            "previous_value" in extra
            and previous_value is not None
            and not (
                isinstance(previous_value, str)
                and previous_value.strip().lower() in {"", "unchanged", "n/a", "none"}
            )
        )
        has_nudge_size = "nudge_delta" in extra or "weight_delta" in extra
        if (
            proposal.reversible
            and is_additive_nudge
            and has_meaningful_previous
            and has_nudge_size
        ):
            return "apply"
        return "promote"

    return "defer"


# ---------------------------------------------------------------------------
# Reading job artifacts
# ---------------------------------------------------------------------------


@dataclass
class JobContext:
    """Everything the loop needs from one job, normalised.

    Build this with :func:`load_job_context`. ``scorecards`` maps a
    worker id to its score dict.
    """

    job_id: str
    job_dir: Path
    goal: str = ""
    selected_workers: tuple[str, ...] = ()
    winning_worker: Optional[str] = None
    failed_workers: tuple[str, ...] = ()
    validation_failures: tuple[str, ...] = ()
    user_corrections: tuple[str, ...] = ()
    scorecards: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    routing_notes: str = ""
    publish_actions: tuple[str, ...] = ()


def _read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _normalise_corrections(value: object) -> tuple[str, ...]:
    """Coerce ``value`` into a clean tuple of correction strings.

    Accepts every realistic shape a worker / human might write into
    ``user-corrections.json``:

    * a list of strings → kept as-is
    * a list mixing strings and dicts (``{"text": "..."}`` /
      ``{"correction": "..."}`` / ``{"message": "..."}``) → values are
      pulled out by key
    * a single string → wrapped in a 1-tuple. **Crucially**, we do not
      iterate the string — ``tuple("hello")`` produces
      ``("h", "e", "l", "l", "o")`` which would emit one bogus
      proposal per character.
    * ``None`` / empty → empty tuple

    Unknown shapes are dropped silently.
    """
    if value is None:
        return ()
    if isinstance(value, str):
        s = value.strip()
        return (s,) if s else ()
    if isinstance(value, dict):
        # A single correction object at the top level.
        for key in ("text", "correction", "message", "body"):
            inner = value.get(key)
            if isinstance(inner, str) and inner.strip():
                return (inner.strip(),)
        return ()
    if not hasattr(value, "__iter__"):
        return ()
    out: list[str] = []
    for item in value:  # ty: ignore[not-iterable]  # hasattr __iter__ checked above
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s)
            continue
        if isinstance(item, dict):
            for key in ("text", "correction", "message", "body"):
                inner = item.get(key)
                if isinstance(inner, str) and inner.strip():
                    out.append(inner.strip())
                    break
            continue
        # Drop anything else (ints, booleans, nested lists) rather
        # than letting it become a one-character splat downstream.
    return tuple(out)


def load_job_context(job_dir: Path) -> JobContext:
    """Read everything we care about from ``job_dir`` into a
    :class:`JobContext`.

    Missing files are tolerated — the loop will emit ``mission_drift``
    proposals for the ones that are required but missing.
    """
    job_dir = Path(job_dir)
    job_id = job_dir.name

    goal = _read_text(job_dir / "goal.txt").strip()
    routing_md = _read_text(job_dir / "routing.md")

    scorecard_path = job_dir / "scorecard.json"
    scorecard_raw = _read_json(scorecard_path) or {}

    # Two supported shapes:
    #   {"workers": {"<id>": {"correctness": 7, ...}, ...}}
    #   {"<id>": {"correctness": 7, ...}, ...}   (flat)
    if "workers" in scorecard_raw and isinstance(scorecard_raw["workers"], dict):
        scorecards = scorecard_raw["workers"]
    else:
        scorecards = {
            k: v for k, v in scorecard_raw.items() if isinstance(v, dict)
        }

    selected = tuple(sorted(scorecards.keys()))

    # Failed workers — any whose self-reported `status` is "fail" /
    # "error" / "failed" in the scorecard.
    failed: list[str] = []
    for wid, sc in scorecards.items():
        status = str(sc.get("status", "")).lower()
        if status in {"fail", "error", "failed", "rejected"}:
            failed.append(wid)

    winning = scorecard_raw.get("winner") if isinstance(scorecard_raw, dict) else None

    validation_failures_raw = _read_json(job_dir / "validation.json") or {}
    validation_failures = tuple(
        validation_failures_raw.get("failures", [])
    )

    corrections_raw = _read_json(job_dir / "user-corrections.json") or {}
    user_corrections = _normalise_corrections(
        corrections_raw.get("corrections")
        if isinstance(corrections_raw, dict)
        else corrections_raw
    )

    publish_md = _read_text(job_dir / "publish.md")
    publish_actions: tuple[str, ...] = tuple(
        line.strip("- ").strip()
        for line in publish_md.splitlines()
        if line.strip().startswith("-")
    )

    return JobContext(
        job_id=job_id,
        job_dir=job_dir,
        goal=goal,
        selected_workers=selected,
        winning_worker=winning,
        failed_workers=tuple(failed),
        validation_failures=validation_failures,
        user_corrections=user_corrections,
        scorecards={k: dict(v) for k, v in scorecards.items()},
        routing_notes=routing_md,
        publish_actions=publish_actions,
    )


# ---------------------------------------------------------------------------
# Bucketing — turn a job context into proposals
# ---------------------------------------------------------------------------


def _axis_below_threshold(
    scores: Mapping[str, float],
) -> list[tuple[str, float]]:
    """Return (axis, score) for every axis at or below the blocking
    threshold."""
    out: list[tuple[str, float]] = []
    for axis in SCORECARD_AXES:
        if axis in scores:
            val = scores[axis]
            try:
                fval = float(val)
            except (TypeError, ValueError):
                continue
            if fval <= BLOCKING_SCORE_THRESHOLD:
                out.append((axis, fval))
    return out


def bucket_findings(job: JobContext) -> tuple[Proposal, ...]:
    """Turn a job's context into a tuple of :class:`Proposal` objects.

    Findings emitted:

    * ``mission_drift`` if ``goal.txt`` or ``scorecard.json`` was missing
      (per the orchestration doc's "failure modes" table).
    * ``prompt_regression`` for each worker that had at least one
      scorecard axis at or below the blocking threshold.
    * ``routing_miss`` if a worker failed outright or validation failed
      against the winning worker.
    * ``skill_gap`` for each explicit user correction (one per
      correction line — the curator will dedupe).
    """
    proposals: list[Proposal] = []

    if not job.goal:
        proposals.append(
            Proposal(
                kind="mission_drift",
                target="goal.txt",
                summary="Job dispatched without a recorded goal.",
                rationale=(
                    "Principle 1 requires every job to start from a "
                    "concrete prompt. The orchestrator should refuse "
                    "to dispatch without one."
                ),
                evidence=(f"{job.job_id}/goal.txt (missing)",),
                principles=("P1",),
                proposed_change=(
                    "Have the orchestrator require a non-empty "
                    "goal.txt before any worker is dispatched."
                ),
                reversible=True,
            )
        )

    if not job.scorecards:
        proposals.append(
            Proposal(
                kind="mission_drift",
                target="scorecard.json",
                summary="Job ended without any worker scorecard.",
                rationale=(
                    "Principle 5 requires every worker output to be "
                    "scored. A missing scorecard makes the job "
                    "un-auditable."
                ),
                evidence=(f"{job.job_id}/scorecard.json (missing)",),
                principles=("P5",),
                proposed_change=(
                    "Reviewer must emit scorecard.json before the "
                    "orchestrator marks the job complete."
                ),
                reversible=True,
            )
        )

    for wid, scores in job.scorecards.items():
        low_axes = _axis_below_threshold(scores)
        if not low_axes:
            continue
        axes_str = ", ".join(f"{a}={int(v)}" for a, v in low_axes)
        proposals.append(
            Proposal(
                kind="prompt_regression",
                target=f"workers/{wid}",
                summary=(
                    f"Worker {wid} produced output with blocking axes: "
                    f"{axes_str}."
                ),
                rationale=(
                    "Scorecard axes at or below the blocking threshold "
                    f"({BLOCKING_SCORE_THRESHOLD}) indicate the worker "
                    "was either asked the wrong question or picked for "
                    "the wrong job. Inspect the prompt and routing."
                ),
                evidence=(
                    f"{job.job_id}/scorecard.json#{wid}",
                    f"{job.job_id}/transcripts/{wid}.md",
                ),
                scorecard_delta_expected={
                    a: f"+{max(1, BLOCKING_SCORE_THRESHOLD - int(v))}"
                    for a, v in low_axes
                },
                principles=("P2", "P5"),
                reversible=True,
            )
        )

    for failed in job.failed_workers:
        proposals.append(
            Proposal(
                kind="routing_miss",
                target="docs/ai-intelligence/model-routing-policy.md",
                summary=(
                    f"Worker {failed} was selected but failed on this job."
                ),
                rationale=(
                    "Repeated failures from the same worker on this "
                    "task class are a signal to lower its routing "
                    "weight. Single failures are not — see the K=3 rule."
                ),
                evidence=(
                    f"{job.job_id}/scorecard.json#{failed}",
                    f"{job.job_id}/transcripts/{failed}.md",
                ),
                principles=("P2", "P9"),
                proposed_change=(
                    f"Consider a one-notch routing-weight reduction "
                    f"for {failed} on this task class, after K=3 "
                    f"consecutive failures."
                ),
                extra={"additive_nudge": True, "previous_value": "unchanged"},
                reversible=True,
            )
        )

    if job.validation_failures and job.winning_worker:
        details = "; ".join(job.validation_failures)
        proposals.append(
            Proposal(
                kind="evidence_gap",
                target="validation.json",
                summary=(
                    f"Validation failed for winning worker "
                    f"{job.winning_worker}: {details}."
                ),
                rationale=(
                    "Validation gates exist so a passing scorecard "
                    "alone is not enough to ship. A failed validation "
                    "against the winning worker means either the gate "
                    "is too strict, the worker output is wrong, or the "
                    "test harness is misconfigured."
                ),
                evidence=(f"{job.job_id}/validation.json",),
                principles=("P3", "P5"),
                reversible=True,
            )
        )

    for correction in job.user_corrections:
        proposals.append(
            Proposal(
                kind="skill_gap",
                target="skills/",
                summary=(
                    f"User correction captured: "
                    f"{redact_secrets(correction)[:120]}"
                ),
                rationale=(
                    "Explicit user corrections are first-class signal. "
                    "The curator should propose a skill or prompt "
                    "update that prevents the same correction next "
                    "time."
                ),
                evidence=(f"{job.job_id}/user-corrections.json",),
                # The user telling us something carries weight even on
                # the first occurrence — mark it user_confirmed so the
                # K=3 rule doesn't defer it.
                extra={"user_confirmed": True},
                principles=("P8",),
                reversible=True,
            )
        )

    return tuple(proposals)


# ---------------------------------------------------------------------------
# Overfit guard — do not over-react to one bad job
# ---------------------------------------------------------------------------


def filter_overfit(
    proposals: Iterable[Proposal],
    *,
    history: Optional[Mapping[tuple[str, str], int]] = None,
) -> tuple[Proposal, ...]:
    """Drop proposals that look like overfitting to one failed run.

    ``history`` maps ``(kind, target)`` to the count of how many
    consecutive prior jobs this same finding has fired. If the new
    proposal would be its first sighting and it does not carry
    ``extra.user_confirmed``, we lower the auto-promotion bar by
    keeping the proposal but resetting ``evidence_event_count`` to 1
    — the K=3 rule then naturally defers it.

    Routing-policy proposals get an extra guard: a single
    ``routing_miss`` without supporting prior history is downgraded to
    "needs corroboration" via the ``extra.needs_corroboration`` flag.
    The curator surfaces these as a single-line summary instead of
    promoting them.
    """
    history = dict(history or {})
    out: list[Proposal] = []
    for p in proposals:
        key = (p.kind, p.target)
        prior = history.get(key, 0)
        new_count = prior + 1
        user_confirmed = bool((p.extra or {}).get("user_confirmed"))

        if (
            p.kind == "routing_miss"
            and new_count <= WEAK_EVIDENCE_THRESHOLD
            and not user_confirmed
        ):
            extra = dict(p.extra or {})
            extra["needs_corroboration"] = True
            extra["weak_evidence_reason"] = (
                "single-job failure; routing changes require K=3 or "
                "explicit user confirmation"
            )
            out.append(
                Proposal(
                    kind=p.kind,
                    target=p.target,
                    summary=p.summary,
                    rationale=p.rationale,
                    evidence=p.evidence,
                    evidence_event_count=new_count,
                    proposed_change=p.proposed_change,
                    scorecard_delta_expected=p.scorecard_delta_expected,
                    principles=p.principles,
                    reversible=p.reversible,
                    extra=extra,
                )
            )
            continue

        # Bump the count from history so downstream sees the real
        # consecutive-jobs total.
        out.append(
            Proposal(
                kind=p.kind,
                target=p.target,
                summary=p.summary,
                rationale=p.rationale,
                evidence=p.evidence,
                evidence_event_count=new_count,
                proposed_change=p.proposed_change,
                scorecard_delta_expected=p.scorecard_delta_expected,
                principles=p.principles,
                reversible=p.reversible,
                extra=dict(p.extra or {}),
            )
        )
    return tuple(out)


# ---------------------------------------------------------------------------
# Retrospective artifacts
# ---------------------------------------------------------------------------


def build_worker_performance(job: JobContext) -> dict:
    """Roll up per-worker performance into a JSON-friendly dict.

    Shape::

        {
          "job_id": "<id>",
          "winner": "<worker>",
          "workers": {
            "<worker>": {
              "scores": {...},
              "average": <float 0..10>,
              "blocking_axes": ["<axis>", ...],
              "selected": true,
              "failed": false
            },
            ...
          },
          "selected_count": <int>,
          "failed_count": <int>
        }
    """
    workers: dict[str, dict] = {}
    for wid, scores in job.scorecards.items():
        clean_scores = {
            axis: float(scores[axis])
            for axis in SCORECARD_AXES
            if axis in scores
            and isinstance(scores[axis], (int, float))
        }
        avg = (
            sum(clean_scores.values()) / len(clean_scores)
            if clean_scores
            else 0.0
        )
        workers[wid] = {
            "scores": clean_scores,
            "average": round(avg, 2),
            "blocking_axes": [
                axis
                for axis, val in clean_scores.items()
                if val <= BLOCKING_SCORE_THRESHOLD
            ],
            "selected": wid in job.selected_workers,
            "failed": wid in job.failed_workers,
        }

    return {
        "job_id": job.job_id,
        "winner": job.winning_worker,
        "workers": workers,
        "selected_count": len(job.selected_workers),
        "failed_count": len(job.failed_workers),
    }


def render_retrospective_md(
    job: JobContext,
    proposals: Sequence[Proposal],
) -> str:
    """Render a plain-English retrospective for the operator.

    Follows ``templates/orchestration/job-retrospective.md``. Plain
    English — every change is explained in one or two sentences. No
    jargon-only sections.
    """
    lines: list[str] = []
    lines.append(f"# muse Job Retrospective — {job.job_id}")
    lines.append("")
    lines.append("## Outcome")
    if job.winning_worker:
        lines.append(f"- Winning worker: `{job.winning_worker}`.")
    else:
        lines.append("- No winning worker recorded.")
    lines.append(f"- Selected workers: {', '.join(job.selected_workers) or 'none'}.")
    lines.append(
        f"- Failed workers: {', '.join(job.failed_workers) or 'none'}."
    )
    lines.append(
        f"- Validation failures: {len(job.validation_failures)}."
    )
    lines.append(
        f"- User corrections recorded: {len(job.user_corrections)}."
    )
    lines.append("")

    lines.append("## Mistakes to avoid next time")
    mistake_lines: list[str] = []
    for axis_failures in _job_axis_breakdown(job):
        worker, axis, val = axis_failures
        mistake_lines.append(
            f"- `{worker}` scored {val:.0f} on `{axis}` — at or below "
            f"the blocking threshold of {BLOCKING_SCORE_THRESHOLD}."
        )
    for failed in job.failed_workers:
        mistake_lines.append(
            f"- `{failed}` was selected but failed outright."
        )
    for vf in job.validation_failures:
        mistake_lines.append(
            f"- Validation failed: {redact_secrets(vf)}."
        )
    for c in job.user_corrections:
        mistake_lines.append(
            f"- User corrected us: {redact_secrets(c)[:200]}"
        )
    if not mistake_lines:
        mistake_lines.append("- None recorded.")
    lines.extend(mistake_lines)
    lines.append("")

    lines.append("## Proposed updates")
    if not proposals:
        lines.append("- None this cycle.")
    for p in proposals:
        lines.append(
            f"- **{p.kind}** → `{p.target}`. {redact_secrets(p.summary)}"
        )
    lines.append("")

    lines.append("## What changes (in plain English)")
    if proposals:
        for p in proposals:
            lines.append(f"- {_plain_english(p)}")
    else:
        lines.append(
            "- Nothing to change. This cycle ran cleanly and the "
            "current routing and skills held up."
        )
    lines.append("")

    return "\n".join(lines)


def _job_axis_breakdown(
    job: JobContext,
) -> list[tuple[str, str, float]]:
    out: list[tuple[str, str, float]] = []
    for wid, scores in job.scorecards.items():
        for axis, val in _axis_below_threshold(scores):
            out.append((wid, axis, val))
    return out


def _plain_english(p: Proposal) -> str:
    """Translate a Proposal into one plain-English sentence.

    Rule: a reader who has never opened the proposal JSON should still
    understand *what* would change and *why*.
    """
    kind_phrases = {
        "skill_gap": "update a skill so this kind of correction is not needed next time",
        "new_skill": "draft a new skill — we hit a recurring need that no skill covers yet",
        "routing_miss": "consider routing this kind of work to a different worker",
        "prompt_regression": "rework the worker prompt — the output was below the bar on at least one axis",
        "tool_gap": "add or wire up a tool the worker needed and did not have",
        "evidence_gap": "tighten the eval / validation step so we can verify changes like this cheaply",
        "mission_drift": "restore a mission principle the job drifted away from",
    }
    base = kind_phrases.get(p.kind, "review this finding")
    confirmed = "yes, immediately" if (
        (p.extra or {}).get("user_confirmed")
    ) else (
        f"after K={K_CONFIRMATIONS} consecutive occurrences"
    )
    return (
        f"{base.capitalize()} ({p.target}). "
        f"Auto-promote? {confirmed}."
    )


def render_routing_lessons_md(
    job: JobContext,
    proposals: Sequence[Proposal],
) -> str:
    """Render the routing-lessons artifact — what we'd change about
    routing next time.

    Only ``routing_miss`` proposals make it into this file. Everything
    else is described in the retrospective.
    """
    lines: list[str] = []
    lines.append(f"# Routing lessons — {job.job_id}")
    lines.append("")
    routing = [p for p in proposals if p.kind == "routing_miss"]
    if not routing:
        lines.append(
            "_No routing changes proposed this cycle._ "
            "Current routing policy stays as is."
        )
        return "\n".join(lines) + "\n"

    lines.append(
        f"Selected workers this job: "
        f"{', '.join(job.selected_workers) or 'none'}."
    )
    lines.append(
        f"Winning worker: `{job.winning_worker or 'none'}`."
    )
    lines.append(
        f"Failed workers: "
        f"{', '.join(job.failed_workers) or 'none'}."
    )
    lines.append("")
    lines.append("## Proposed routing updates")
    for p in routing:
        weak = (p.extra or {}).get("needs_corroboration")
        suffix = (
            "  _(weak evidence — needs corroboration; not auto-applied)_"
            if weak
            else ""
        )
        lines.append(
            f"- `{p.target}`: {redact_secrets(p.summary)}{suffix}"
        )
        if p.proposed_change:
            lines.append(
                f"  - Proposed: {redact_secrets(p.proposed_change)}"
            )
    lines.append("")
    lines.append(
        "_Rule: do not auto-apply routing-policy changes from a "
        f"single job. Require K={K_CONFIRMATIONS} consecutive "
        "occurrences or an explicit user confirmation._"
    )
    return "\n".join(lines) + "\n"


def render_user_preference_updates_md(
    job: JobContext,
) -> str:
    """Render the user-preference-updates artifact.

    Captures explicit user corrections so the next prompt can avoid
    repeating the mistake. Corrections are redacted before being
    written.
    """
    lines: list[str] = []
    lines.append(f"# User preference updates — {job.job_id}")
    lines.append("")
    if not job.user_corrections:
        lines.append("_No explicit user corrections this cycle._")
        return "\n".join(lines) + "\n"

    lines.append("## Corrections captured")
    for c in job.user_corrections:
        lines.append(f"- {redact_secrets(c)}")
    lines.append("")
    lines.append(
        "_These will be surfaced to the curator drafts lane so the "
        "next run starts with the preference applied._"
    )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Disk I/O — write the retrospective bundle
# ---------------------------------------------------------------------------


@dataclass
class RetrospectiveBundle:
    """Paths of the four artifacts written by :func:`write_retrospective`."""

    retrospective_md: Path
    worker_performance_json: Path
    routing_lessons_md: Path
    user_preference_updates_md: Path
    proposals_dir: Path
    proposal_paths: tuple[Path, ...]


def write_retrospective(
    job: JobContext,
    proposals: Sequence[Proposal],
    *,
    out_dir: Optional[Path] = None,
) -> RetrospectiveBundle:
    """Write every retrospective artifact under ``out_dir``.

    ``out_dir`` defaults to ``<job.job_dir>``. Returns a
    :class:`RetrospectiveBundle` naming every path written. Each
    proposal becomes a JSON file under ``<out_dir>/proposals/`` with
    an 8-hex-char id (matching the skill's storage convention).
    """
    if out_dir is None:
        out_dir = job.job_dir
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    retro_md = out_dir / "retrospective.md"
    retro_md.write_text(
        redact_secrets(render_retrospective_md(job, proposals)),
        encoding="utf-8",
    )

    perf_json = out_dir / "worker-performance.json"
    perf_json.write_text(
        json.dumps(build_worker_performance(job), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    routing_md = out_dir / "routing-lessons.md"
    routing_md.write_text(
        redact_secrets(render_routing_lessons_md(job, proposals)),
        encoding="utf-8",
    )

    prefs_md = out_dir / "user-preference-updates.md"
    prefs_md.write_text(
        redact_secrets(render_user_preference_updates_md(job)),
        encoding="utf-8",
    )

    proposals_dir = out_dir / "proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for p in proposals:
        pid = uuid.uuid4().hex[:8]
        path = proposals_dir / f"prop-{pid}.json"
        path.write_text(
            json.dumps(p.as_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        paths.append(path)

    return RetrospectiveBundle(
        retrospective_md=retro_md,
        worker_performance_json=perf_json,
        routing_lessons_md=routing_md,
        user_preference_updates_md=prefs_md,
        proposals_dir=proposals_dir,
        proposal_paths=tuple(paths),
    )


# ---------------------------------------------------------------------------
# Trailer — the line the user reads to know the loop actually closed
# ---------------------------------------------------------------------------


def format_trailer(
    job: JobContext,
    proposals: Sequence[Proposal],
) -> str:
    """Return the human-readable trailer described by the skill."""
    decisions = Counter(promotion_decision(p) for p in proposals)
    applied = decisions.get("apply", 0)
    promoted = decisions.get("promote", 0)
    deferred = decisions.get("defer", 0)

    k3 = sum(
        1
        for p in proposals
        if p.evidence_event_count >= K_CONFIRMATIONS
        and promotion_decision(p) == "promote"
    )

    routing_props = [p for p in proposals if p.kind == "routing_miss"]
    if routing_props:
        routing_line = (
            f"{len(routing_props)} routing change(s) proposed"
        )
    else:
        routing_line = "none"

    next_prompt = _suggest_next_prompt_hint(job, proposals)

    return (
        "Self-improvement loop complete.\n"
        f"Job: {job.job_id}\n"
        f"Proposals: {len(proposals)} total "
        f"({applied} applied, {promoted} promoted, {deferred} deferred)\n"
        f"K={K_CONFIRMATIONS} promotions this run: {k3}\n"
        f"Routing updates: {routing_line}\n"
        f"Next prompt should be: {next_prompt}"
    )


def _suggest_next_prompt_hint(
    job: JobContext,
    proposals: Sequence[Proposal],
) -> str:
    """Pick one short line of guidance for the next prompt."""
    if not proposals:
        return (
            "same as this one — current routing and skills held up."
        )
    by_kind: dict[str, int] = defaultdict(int)
    for p in proposals:
        by_kind[p.kind] += 1
    top = max(by_kind.items(), key=lambda kv: kv[1])[0]
    suggestions = {
        "routing_miss": "consider a different worker for this task class.",
        "prompt_regression": "rework the worker prompt before re-running.",
        "skill_gap": "load (or write) a skill that covers this case.",
        "new_skill": "let the curator draft a new skill before re-running.",
        "tool_gap": "wire up the missing tool first.",
        "evidence_gap": "tighten the validation harness first.",
        "mission_drift": "restore the missing artifact before dispatching.",
    }
    return suggestions.get(top, "review the proposals in the retrospective.")


__all__ = [
    "BLOCKING_SCORE_THRESHOLD",
    "FINDING_KINDS",
    "JobContext",
    "K_CONFIRMATIONS",
    "Proposal",
    "RetrospectiveBundle",
    "SCORECARD_AXES",
    "WEAK_EVIDENCE_THRESHOLD",
    "build_worker_performance",
    "bucket_findings",
    "filter_overfit",
    "format_trailer",
    "load_job_context",
    "promotion_decision",
    "redact_secrets",
    "render_retrospective_md",
    "render_routing_lessons_md",
    "render_user_preference_updates_md",
    "write_retrospective",
]
