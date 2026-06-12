"""Tests for ``muse_cli/self_improvement.py``.

The loop is bound by four rules from the skill / mission docs:

* Do not auto-update routing policy from weak evidence.
* Do not store secrets in retrospectives.
* Do not overfit to one failed run.
* Explain changes in plain English.

Every test in this file pins one of those rules, or pins a structural
invariant the skill describes (proposal shape, K=3, four artifact
files, trailer format).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from muse_cli import self_improvement as si
from muse_cli.self_improvement import (
    BLOCKING_SCORE_THRESHOLD,
    FINDING_KINDS,
    JobContext,
    K_CONFIRMATIONS,
    Proposal,
    SCORECARD_AXES,
    bucket_findings,
    build_worker_performance,
    filter_overfit,
    format_trailer,
    load_job_context,
    promotion_decision,
    redact_secrets,
    render_retrospective_md,
    render_routing_lessons_md,
    render_user_preference_updates_md,
    write_retrospective,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────


def _write_job(tmp_path: Path, **overrides) -> Path:
    """Lay down a synthetic job directory under ``tmp_path``."""
    job_dir = tmp_path / "2026-05-23" / "job-abc123"
    job_dir.mkdir(parents=True)

    (job_dir / "goal.txt").write_text(
        overrides.get("goal", "Add native GitHub PR review gate.")
        + "\n",
        encoding="utf-8",
    )
    (job_dir / "routing.md").write_text(
        overrides.get(
            "routing", "Used claude-code for builder, hermes-local for reviewer."
        )
        + "\n",
        encoding="utf-8",
    )
    (job_dir / "scorecard.json").write_text(
        json.dumps(overrides.get("scorecard", _default_scorecard())),
        encoding="utf-8",
    )
    if "validation" in overrides:
        (job_dir / "validation.json").write_text(
            json.dumps(overrides["validation"]), encoding="utf-8"
        )
    if "corrections" in overrides:
        (job_dir / "user-corrections.json").write_text(
            json.dumps({"corrections": overrides["corrections"]}),
            encoding="utf-8",
        )
    (job_dir / "publish.md").write_text(
        overrides.get(
            "publish_md",
            "- git push to feature branch (undo: git push --delete origin <branch>)\n",
        ),
        encoding="utf-8",
    )
    return job_dir


def _default_scorecard() -> dict:
    return {
        "winner": "claude-code-builder",
        "workers": {
            "claude-code-builder": {
                "correctness": 8,
                "maintainability": 7,
                "testability": 6,
                "architecture_fit": 8,
                "developer_experience": 7,
                "ui_ux": 7,
                "speed": 6,
                "cost_efficiency": 5,
                "local_first_fit": 5,
                "jeremiah_fit": 8,
                "status": "ok",
            },
            "codex-builder": {
                "correctness": 3,
                "maintainability": 4,
                "testability": 4,
                "architecture_fit": 6,
                "developer_experience": 7,
                "ui_ux": 6,
                "speed": 7,
                "cost_efficiency": 6,
                "local_first_fit": 5,
                "jeremiah_fit": 5,
                "status": "fail",
            },
        },
    }


# ─── Constants + dataclass invariants ──────────────────────────────────────


def test_finding_kinds_match_the_skill():
    assert FINDING_KINDS == (
        "skill_gap",
        "new_skill",
        "routing_miss",
        "prompt_regression",
        "tool_gap",
        "evidence_gap",
        "mission_drift",
    )


def test_scorecard_axes_match_the_mission():
    # The 10 axes the mission + loop skills both name.
    assert set(SCORECARD_AXES) == {
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
    }


def test_proposal_rejects_unknown_kind():
    with pytest.raises(ValueError):
        Proposal(
            kind="vibes",
            target="skills/foo",
            summary="x",
            rationale="y",
        )


def test_proposal_rejects_zero_event_count():
    with pytest.raises(ValueError):
        Proposal(
            kind="routing_miss",
            target="docs/foo",
            summary="x",
            rationale="y",
            evidence_event_count=0,
        )


# ─── Secret redaction ─────────────────────────────────────────────────────


def test_redact_secrets_masks_known_patterns():
    raw = "Use api_key=sk-abcdef1234567890 and gho_AAAAAAAAAAAAAAAAAA"
    out = redact_secrets(raw)
    assert "sk-abcdef" not in out
    assert "gho_AAAAAA" not in out
    assert "[REDACTED]" in out


def test_redact_secrets_idempotent_on_clean_text():
    raw = "Nothing sensitive here, just plain English."
    assert redact_secrets(raw) == raw


def test_redact_secrets_handles_modern_github_token_formats():
    """Fine-grained PATs, server-to-server, refresh, and OAuth all
    redacted. Pinning this so a regex regression cannot leak fresh
    GitHub credentials into a checked-in retrospective."""
    samples = {
        "ghp_classic": "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "gho_oauth": "gho_BBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        "ghu_userserver": "ghu_CCCCCCCCCCCCCCCCCCCCCCCCC",
        "ghs_server": "ghs_DDDDDDDDDDDDDDDDDDDDDDDDD",
        "ghr_refresh": "ghr_EEEEEEEEEEEEEEEEEEEEEEEEE",
        "github_pat_fine_grained": (
            "github_pat_11AAAAAAA0AaAaAaAaAaAaA_"
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        ),
    }
    for label, token in samples.items():
        raw = f"token={token} ({label})"
        out = redact_secrets(raw)
        assert token not in out, (
            f"token format {label} survived redaction: {out!r}"
        )
        assert "[REDACTED]" in out


def test_redact_secrets_does_not_eat_unrelated_token_words():
    """The word "token" appearing in prose with no value attached
    must not be replaced — otherwise retrospectives become useless."""
    raw = "The reviewer asked us to mint a new token next week."
    out = redact_secrets(raw)
    assert "mint a new token" in out


def test_retrospective_does_not_contain_visible_secret(tmp_path):
    """The "do not store secrets in retrospectives" rule, end-to-end."""
    job_dir = _write_job(
        tmp_path,
        corrections=[
            "Stop committing OPENAI_API_KEY=sk-abcdef1234567890 to repo.",
        ],
    )
    job = load_job_context(job_dir)
    proposals = bucket_findings(job)
    bundle = write_retrospective(job, proposals)
    for path in (
        bundle.retrospective_md,
        bundle.routing_lessons_md,
        bundle.user_preference_updates_md,
    ):
        body = path.read_text(encoding="utf-8")
        assert "sk-abcdef1234567890" not in body
        assert "[REDACTED]" in body or "sk-abcdef" not in body


# ─── Promotion policy ─────────────────────────────────────────────────────


def test_single_event_routing_miss_is_deferred_without_user_confirmation():
    """The "do not auto-update routing from weak evidence" rule."""
    p = Proposal(
        kind="routing_miss",
        target="docs/ai-intelligence/model-routing-policy.md",
        summary="codex failed this run",
        rationale="single failure",
        evidence_event_count=1,
        extra={"additive_nudge": True, "previous_value": "0.5"},
    )
    assert promotion_decision(p) == "defer"


def test_routing_miss_with_user_confirmed_is_applied_if_nudge_recorded():
    p = Proposal(
        kind="routing_miss",
        target="docs/ai-intelligence/model-routing-policy.md",
        summary="reviewer should prefer hermes-local for <200 LOC refactors",
        rationale="user explicitly asked for this",
        evidence_event_count=1,
        extra={
            "additive_nudge": True,
            "previous_value": "0.5",
            "nudge_delta": "+0.1",
            "user_confirmed": True,
        },
    )
    assert promotion_decision(p) == "apply"


def test_routing_miss_without_recorded_previous_value_is_promoted_not_applied():
    """Even with K=3, we will not auto-apply a routing change that
    cannot be reverted because no previous_value is on file."""
    p = Proposal(
        kind="routing_miss",
        target="docs/ai-intelligence/model-routing-policy.md",
        summary="lower weight for codex",
        rationale="three consecutive failures",
        evidence_event_count=K_CONFIRMATIONS,
        # No previous_value!
        extra={"additive_nudge": True, "nudge_delta": "-0.1"},
    )
    assert promotion_decision(p) == "promote"


@pytest.mark.parametrize(
    "previous_value",
    ["unchanged", "N/A", "none", "", None, "  UNCHANGED  "],
)
def test_routing_miss_with_placeholder_previous_value_is_not_auto_applied(
    previous_value,
):
    """The "meaningful rollback metadata" rule: a placeholder
    ``previous_value`` is not enough to auto-apply a routing change."""
    p = Proposal(
        kind="routing_miss",
        target="docs/ai-intelligence/model-routing-policy.md",
        summary="x",
        rationale="y",
        extra={
            "additive_nudge": True,
            "previous_value": previous_value,
            "nudge_delta": "+0.1",
            "user_confirmed": True,
        },
    )
    assert promotion_decision(p) == "promote"


def test_routing_miss_without_recorded_nudge_size_is_not_auto_applied():
    """We also need to know *how big* the nudge is — without a
    recorded delta the change is not really an additive nudge."""
    p = Proposal(
        kind="routing_miss",
        target="docs/ai-intelligence/model-routing-policy.md",
        summary="x",
        rationale="y",
        extra={
            "additive_nudge": True,
            "previous_value": "0.5",
            # No nudge_delta / weight_delta.
            "user_confirmed": True,
        },
    )
    assert promotion_decision(p) == "promote"


def test_routing_miss_with_weight_delta_also_auto_applies():
    """``weight_delta`` is an accepted alias for ``nudge_delta``."""
    p = Proposal(
        kind="routing_miss",
        target="docs/ai-intelligence/model-routing-policy.md",
        summary="x",
        rationale="y",
        extra={
            "additive_nudge": True,
            "previous_value": "0.5",
            "weight_delta": "-0.1",
            "user_confirmed": True,
        },
    )
    assert promotion_decision(p) == "apply"


def test_prompt_regression_always_routes_to_curator():
    p = Proposal(
        kind="prompt_regression",
        target="workers/codex-builder",
        summary="bad output on testability",
        rationale="scored 3",
        evidence_event_count=K_CONFIRMATIONS,
        extra={"user_confirmed": True},
    )
    assert promotion_decision(p) == "promote"


def test_mission_drift_always_routes_to_curator():
    p = Proposal(
        kind="mission_drift",
        target="goal.txt",
        summary="missing goal",
        rationale="P1",
        evidence_event_count=K_CONFIRMATIONS,
        extra={"user_confirmed": True},
    )
    # mission_drift is always human-gated — even when confirmed, it
    # rides through the curator rather than being applied directly.
    assert promotion_decision(p) == "promote"


# ─── Overfit guard ────────────────────────────────────────────────────────


def test_filter_overfit_flags_single_routing_miss_as_needing_corroboration():
    """The "do not overfit to one failed run" rule."""
    p = Proposal(
        kind="routing_miss",
        target="docs/ai-intelligence/model-routing-policy.md",
        summary="codex failed once",
        rationale="single occurrence",
        extra={"additive_nudge": True, "previous_value": "0.5"},
    )
    filtered = filter_overfit([p], history={})
    assert len(filtered) == 1
    assert filtered[0].extra.get("needs_corroboration") is True
    assert "weak_evidence_reason" in filtered[0].extra


def test_filter_overfit_bumps_event_count_from_history():
    p = Proposal(
        kind="prompt_regression",
        target="workers/foo",
        summary="x",
        rationale="y",
    )
    filtered = filter_overfit(
        [p], history={("prompt_regression", "workers/foo"): 2}
    )
    assert filtered[0].evidence_event_count == 3
    # And now the K=3 rule kicks in — decision would no longer be defer.
    assert promotion_decision(filtered[0]) == "promote"


def test_filter_overfit_passes_user_confirmed_routing_miss_through():
    p = Proposal(
        kind="routing_miss",
        target="docs/foo.md",
        summary="x",
        rationale="y",
        extra={"user_confirmed": True, "additive_nudge": True, "previous_value": "0.5"},
    )
    filtered = filter_overfit([p])
    assert filtered[0].extra.get("needs_corroboration") is not True


# ─── Job loading + bucketing ──────────────────────────────────────────────


def test_user_corrections_string_value_does_not_split_into_chars(tmp_path):
    """The "do not split user-corrections strings into one character
    per correction" rule. A malformed shape where the file stores a
    plain string (not a list) must be normalised, not iterated."""
    job_dir = _write_job(tmp_path)
    # Overwrite user-corrections.json with a string value at the
    # ``corrections`` key.
    (job_dir / "user-corrections.json").write_text(
        json.dumps({"corrections": "please prefer pathlib"}),
        encoding="utf-8",
    )
    job = load_job_context(job_dir)
    assert job.user_corrections == ("please prefer pathlib",)


def test_user_corrections_at_top_level_string(tmp_path):
    """Some workers write the bare value, not wrapped in an object."""
    job_dir = _write_job(tmp_path)
    (job_dir / "user-corrections.json").write_text(
        json.dumps("please prefer pathlib"),
        encoding="utf-8",
    )
    job = load_job_context(job_dir)
    assert job.user_corrections == ("please prefer pathlib",)


def test_user_corrections_list_of_dicts_extracted_by_key(tmp_path):
    job_dir = _write_job(tmp_path)
    (job_dir / "user-corrections.json").write_text(
        json.dumps(
            {
                "corrections": [
                    {"text": "prefer pathlib"},
                    {"correction": "no os.path"},
                    {"message": "explain decisions in the PR body"},
                ]
            }
        ),
        encoding="utf-8",
    )
    job = load_job_context(job_dir)
    assert job.user_corrections == (
        "prefer pathlib",
        "no os.path",
        "explain decisions in the PR body",
    )


def test_user_corrections_drops_unknown_shapes(tmp_path):
    job_dir = _write_job(tmp_path)
    (job_dir / "user-corrections.json").write_text(
        json.dumps(
            {
                "corrections": [
                    "real correction",
                    42,  # dropped
                    None,  # dropped
                    {"unknown_key": "ignored"},  # dropped
                    "",  # dropped (empty)
                ]
            }
        ),
        encoding="utf-8",
    )
    job = load_job_context(job_dir)
    assert job.user_corrections == ("real correction",)


def test_user_corrections_missing_file_is_empty(tmp_path):
    job_dir = _write_job(tmp_path)
    job = load_job_context(job_dir)
    assert job.user_corrections == ()


def test_load_job_context_reads_every_artifact(tmp_path):
    job_dir = _write_job(
        tmp_path,
        validation={"failures": ["pytest tests/test_x.py::test_y failed"]},
        corrections=["please prefer pathlib over os.path"],
    )
    job = load_job_context(job_dir)
    assert job.job_id == "job-abc123"
    assert job.goal.startswith("Add native GitHub PR review gate")
    assert set(job.selected_workers) == {"claude-code-builder", "codex-builder"}
    assert job.winning_worker == "claude-code-builder"
    assert job.failed_workers == ("codex-builder",)
    assert "pytest" in job.validation_failures[0]
    assert "pathlib" in job.user_corrections[0]
    assert job.publish_actions  # parsed from publish.md


def test_bucket_findings_creates_routing_miss_for_failed_worker(tmp_path):
    job_dir = _write_job(tmp_path)
    job = load_job_context(job_dir)
    proposals = bucket_findings(job)
    kinds = {p.kind for p in proposals}
    assert "routing_miss" in kinds
    # codex-builder had correctness=3 ≤ threshold, so a prompt_regression
    # finding is also emitted.
    assert "prompt_regression" in kinds


def test_bucket_findings_creates_mission_drift_when_goal_missing(tmp_path):
    job_dir = _write_job(tmp_path, goal="")
    job = load_job_context(job_dir)
    proposals = bucket_findings(job)
    drift = [p for p in proposals if p.kind == "mission_drift"]
    assert any(p.target == "goal.txt" for p in drift)
    assert any("P1" in p.principles for p in drift)


def test_bucket_findings_creates_evidence_gap_when_validation_fails(tmp_path):
    job_dir = _write_job(
        tmp_path,
        validation={"failures": ["smoke test exited 1"]},
    )
    job = load_job_context(job_dir)
    proposals = bucket_findings(job)
    assert any(p.kind == "evidence_gap" for p in proposals)


def test_bucket_findings_marks_user_correction_as_user_confirmed(tmp_path):
    job_dir = _write_job(
        tmp_path,
        corrections=["please prefer pathlib over os.path"],
    )
    job = load_job_context(job_dir)
    proposals = bucket_findings(job)
    skill_gap = [p for p in proposals if p.kind == "skill_gap"]
    assert skill_gap
    assert all(p.extra.get("user_confirmed") for p in skill_gap)


# ─── Retrospective artifacts ──────────────────────────────────────────────


def test_write_retrospective_emits_four_named_artifacts(tmp_path):
    job_dir = _write_job(tmp_path)
    job = load_job_context(job_dir)
    proposals = bucket_findings(job)
    bundle = write_retrospective(job, proposals)
    assert bundle.retrospective_md.name == "retrospective.md"
    assert bundle.worker_performance_json.name == "worker-performance.json"
    assert bundle.routing_lessons_md.name == "routing-lessons.md"
    assert bundle.user_preference_updates_md.name == "user-preference-updates.md"
    for path in (
        bundle.retrospective_md,
        bundle.worker_performance_json,
        bundle.routing_lessons_md,
        bundle.user_preference_updates_md,
    ):
        assert path.exists() and path.read_text(encoding="utf-8")
    # And every proposal lands as its own JSON file.
    assert len(bundle.proposal_paths) == len(proposals)
    for p_path in bundle.proposal_paths:
        assert p_path.exists()
        json.loads(p_path.read_text(encoding="utf-8"))


def test_worker_performance_json_has_expected_shape(tmp_path):
    job_dir = _write_job(tmp_path)
    job = load_job_context(job_dir)
    perf = build_worker_performance(job)
    assert perf["job_id"] == "job-abc123"
    assert perf["winner"] == "claude-code-builder"
    assert "claude-code-builder" in perf["workers"]
    cb = perf["workers"]["codex-builder"]
    assert cb["failed"] is True
    assert "correctness" in cb["blocking_axes"]
    # Selected count + failed count line up.
    assert perf["selected_count"] == 2
    assert perf["failed_count"] == 1


def test_retrospective_md_explains_changes_in_plain_english(tmp_path):
    """The "explain changes in plain English" rule.

    A reader should be able to skim the retrospective and know what
    will change next time, without opening a single proposal JSON.
    """
    job_dir = _write_job(tmp_path)
    job = load_job_context(job_dir)
    proposals = bucket_findings(job)
    md = render_retrospective_md(job, proposals)
    assert "## What changes (in plain English)" in md
    # No raw JSON in the body.
    assert "{" not in md
    # The kind names are translated, not surfaced verbatim.
    assert "routing_miss" not in md.split("## Proposed updates")[1].split(
        "## What changes"
    )[1]


def test_routing_lessons_md_calls_out_weak_evidence(tmp_path):
    job_dir = _write_job(tmp_path)
    job = load_job_context(job_dir)
    raw = bucket_findings(job)
    proposals = filter_overfit(raw, history={})
    md = render_routing_lessons_md(job, proposals)
    # The routing-lessons file must explicitly state the rule.
    assert "K=3" in md or f"K={K_CONFIRMATIONS}" in md
    # If there are routing-miss proposals, weak-evidence ones are
    # marked.
    if any(p.kind == "routing_miss" for p in proposals):
        assert "weak evidence" in md.lower() or "corroboration" in md.lower()


def test_user_preference_updates_md_handles_no_corrections(tmp_path):
    job_dir = _write_job(tmp_path)
    job = load_job_context(job_dir)
    md = render_user_preference_updates_md(job)
    assert "No explicit user corrections" in md


def test_user_preference_updates_md_lists_corrections(tmp_path):
    job_dir = _write_job(
        tmp_path,
        corrections=[
            "prefer pathlib",
            "do not add type ignore comments",
        ],
    )
    job = load_job_context(job_dir)
    md = render_user_preference_updates_md(job)
    assert "prefer pathlib" in md
    assert "do not add type ignore comments" in md


# ─── Trailer ──────────────────────────────────────────────────────────────


def test_trailer_has_every_required_line(tmp_path):
    job_dir = _write_job(tmp_path)
    job = load_job_context(job_dir)
    proposals = bucket_findings(job)
    trailer = format_trailer(job, proposals)
    assert "Self-improvement loop complete." in trailer
    assert f"Job: {job.job_id}" in trailer
    assert "Proposals:" in trailer
    assert f"K={K_CONFIRMATIONS} promotions this run:" in trailer
    assert "Routing updates:" in trailer
    assert "Next prompt should be:" in trailer


def test_trailer_when_no_proposals_says_routing_held_up(tmp_path):
    job_dir = _write_job(
        tmp_path,
        scorecard={
            "winner": "claude-code-builder",
            "workers": {
                "claude-code-builder": {
                    "correctness": 9,
                    "maintainability": 9,
                    "testability": 9,
                    "architecture_fit": 9,
                    "developer_experience": 9,
                    "ui_ux": 9,
                    "speed": 8,
                    "cost_efficiency": 8,
                    "local_first_fit": 9,
                    "jeremiah_fit": 9,
                    "status": "ok",
                },
            },
        },
    )
    job = load_job_context(job_dir)
    proposals = bucket_findings(job)
    assert proposals == ()
    trailer = format_trailer(job, proposals)
    assert "held up" in trailer
