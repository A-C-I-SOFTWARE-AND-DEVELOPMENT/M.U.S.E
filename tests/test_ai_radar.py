"""Tests for ``hermes_cli/ai_radar.py``.

The radar is a documentation-and-evidence module; these tests pin the
contracts that the skill (``skills/ai-improvement-radar/SKILL.md`` and
``docs/ai-intelligence/ai-improvement-radar.md``) requires:

* The watchlist covers the tools the skill names.
* Confidence levels are exactly the four documented.
* Unverified findings never appear in the policy recommendation.
* The rendered markdown contains every required section, in order.
* The radar never writes outside the directory the caller asked for.
* Weak evidence (single low-confidence source) does not move policy.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from hermes_cli import ai_radar
from hermes_cli.ai_radar import (
    CONFIDENCE_LEVELS,
    RadarFinding,
    RadarReport,
    is_disqualified_source,
    is_official_source,
    mark_unverified,
    recommend_policy_updates,
    render_report_markdown,
    tracked_tool_ids,
    utc_timestamp,
    write_radar_report,
    write_radar_request,
)


# ─── Watchlist contract ────────────────────────────────────────────────────


def test_tracked_tools_cover_the_skill_watchlist():
    """The watchlist must name every tool the skill says we track."""
    ids = set(tracked_tool_ids())
    required = {
        "codex",
        "claude-code",
        "aider",
        "goose",
        "continue",
        "openhands",
        "openclaw-personal-agents",
        "supabase-ai",
        "vercel-ai",
        "android-voice-stt",
    }
    missing = required - ids
    assert not missing, f"watchlist missing required tools: {missing}"


def test_get_tracked_tool_round_trip():
    entry = ai_radar.get_tracked_tool("claude-code")
    assert entry is not None
    assert entry["vendor"] == "Anthropic"
    assert "code.claude.com/docs" in " ".join(entry["official_sources"])


def test_get_tracked_tool_unknown_returns_none():
    assert ai_radar.get_tracked_tool("totally-made-up") is None


# ─── Confidence + source quality ───────────────────────────────────────────


def test_confidence_levels_are_exactly_the_documented_four():
    assert CONFIDENCE_LEVELS == ("high", "medium", "low", "unverified")


def test_is_official_source_recognises_vendor_domains():
    assert is_official_source("https://code.claude.com/docs/overview")
    assert is_official_source("https://github.com/openai/codex")
    assert is_official_source("https://supabase.com/docs")
    assert is_official_source("https://sdk.vercel.ai/docs")


def test_is_official_source_rejects_non_urls():
    assert not is_official_source("")
    assert not is_official_source("not a url")
    assert not is_official_source(None)  # type: ignore[arg-type]


def test_is_disqualified_source_flags_social_and_forums():
    assert is_disqualified_source("https://www.reddit.com/r/foo")
    assert is_disqualified_source("https://twitter.com/somebody/status/123")
    assert is_disqualified_source("https://news.ycombinator.com/item?id=1")
    assert not is_disqualified_source("https://code.claude.com/docs")


def test_radar_finding_high_confidence_requires_official_source():
    """A finding marked ``high`` with a non-official source must be
    downgraded automatically."""
    f = RadarFinding(
        tool="claude-code",
        feature="adds --foo",
        source="https://some-random-blog.example/post",
        confidence="high",
        actionable=True,
    )
    assert f.confidence != "high"
    assert "downgraded" in f.notes


def test_radar_finding_disqualified_source_forces_unverified():
    f = RadarFinding(
        tool="codex",
        feature="ships X",
        source="https://www.reddit.com/r/codex/comments/abc",
        confidence="medium",
        actionable=True,
    )
    assert f.confidence == "unverified"
    assert not f.actionable


def test_radar_finding_rejects_bogus_confidence():
    with pytest.raises(ValueError):
        RadarFinding(
            tool="codex",
            feature="x",
            source="https://github.com/openai/codex",
            confidence="probably",
        )


def test_mark_unverified_sets_confidence_and_clears_actionable():
    f = RadarFinding(
        tool="aider",
        feature="adds --bar",
        source="https://github.com/Aider-AI/aider",
        confidence="medium",
        actionable=True,
    )
    u = mark_unverified(f, reason="conflicting docs")
    assert u.confidence == "unverified"
    assert not u.actionable
    assert "conflicting docs" in u.notes


# ─── Policy recommendation logic ───────────────────────────────────────────


def test_recommend_policy_updates_drops_unverified_findings():
    findings = [
        RadarFinding(
            tool="codex",
            feature="x",
            source="https://www.reddit.com/r/codex/comments/abc",
            confidence="high",  # will be force-downgraded
            actionable=True,
        ),
    ]
    rec = recommend_policy_updates(findings)
    assert rec["model_registry"] == "no"
    assert rec["model_routing_policy"] == "no"
    assert rec["weak_evidence_skipped"] >= 1


def test_recommend_policy_updates_high_confidence_drives_all_three_artifacts():
    findings = [
        RadarFinding(
            tool="claude-code",
            feature="adds --json-schema",
            source="https://code.claude.com/docs",
            confidence="high",
            actionable=True,
        ),
    ]
    rec = recommend_policy_updates(findings)
    assert rec["model_registry"].startswith("yes")
    assert rec["model_routing_policy"].startswith("yes")
    assert rec["tool_capability_matrix"].startswith("yes")
    # The recommendation lists explicit file targets.
    assert any("tool-capability-matrix.md" in c for c in rec["changes"])
    assert any("model-routing-policy.md" in c for c in rec["changes"])
    assert any("model-registry.yaml" in c for c in rec["changes"])


def test_recommend_policy_updates_medium_only_touches_matrix():
    findings = [
        RadarFinding(
            tool="goose",
            feature="adds extension XYZ",
            source="https://github.com/block/goose",
            confidence="medium",
            actionable=True,
        ),
    ]
    rec = recommend_policy_updates(findings)
    assert rec["model_routing_policy"] == "no"
    assert rec["model_registry"] == "no"
    assert rec["tool_capability_matrix"].startswith("yes")


def test_recommend_ignores_non_actionable_findings():
    findings = [
        RadarFinding(
            tool="continue",
            feature="cosmetic UI tweak",
            source="https://github.com/continuedev/continue",
            confidence="high",
            actionable=False,
        ),
    ]
    rec = recommend_policy_updates(findings)
    assert rec["changes"] == []
    assert rec["model_routing_policy"] == "no"


def test_recommend_carries_weak_evidence_rule():
    rec = recommend_policy_updates([])
    assert "weak_evidence_rule" in rec
    assert "do not act" in rec["weak_evidence_rule"]


# ─── Markdown rendering ────────────────────────────────────────────────────


_REQUIRED_SECTIONS = (
    "## Summary",
    "## Tools surveyed",
    "## New features discovered",
    "## Sources checked",
    "## Relevance to Hermes",
    "## Implementation recommendation",
    "## Routing policy update needed",
    "## Confidence level",
    "## Unverified items (do not act on)",
)


def _make_sample_report() -> RadarReport:
    return RadarReport(
        timestamp="2026-05-23T18-30-00Z",
        summary="Two confirmed changes; one rumor that did not meet the bar.",
        tools_surveyed=("claude-code", "codex", "aider"),
        findings=(
            RadarFinding(
                tool="claude-code",
                feature="adds --json-schema",
                source="https://code.claude.com/docs",
                confidence="high",
                actionable=True,
            ),
            RadarFinding(
                tool="codex",
                feature="ships smarter mode",
                source="https://www.reddit.com/r/codex/foo",
                confidence="medium",  # will be force-unverified
                actionable=True,
            ),
        ),
        sources_checked={
            "claude-code": ("https://code.claude.com/docs",),
            "codex": ("https://github.com/openai/codex",),
        },
        overall_confidence="medium",
        notes="One actionable change, one unverified rumor.",
    )


def test_render_markdown_includes_every_required_section_in_order():
    md = render_report_markdown(_make_sample_report())
    # Title first.
    assert md.startswith(
        "# Hermes AI Improvement Radar — 2026-05-23T18-30-00Z"
    )
    # Then sections in the prescribed order.
    last_pos = -1
    for section in _REQUIRED_SECTIONS:
        pos = md.find(section)
        assert pos != -1, f"missing section: {section}"
        assert pos > last_pos, f"section out of order: {section}"
        last_pos = pos


def test_render_markdown_keeps_unverified_out_of_recommendation():
    md = render_report_markdown(_make_sample_report())
    # The reddit-sourced finding must end up in the unverified block.
    unverified_idx = md.find("## Unverified items")
    impl_idx = md.find("## Implementation recommendation")
    routing_idx = md.find("## Routing policy update needed")
    assert "ships smarter mode" not in md[impl_idx:unverified_idx]
    # And the routing-policy "yes" line should only reflect the
    # high-confidence finding.
    routing_block = md[routing_idx:unverified_idx]
    assert "yes" in routing_block  # at least one yes from the verified
    assert "ships smarter mode" not in routing_block


def test_render_markdown_when_no_actionable_findings_says_so():
    report = RadarReport(
        timestamp="2026-05-23T18-30-00Z",
        summary="Nothing moved this cycle.",
        tools_surveyed=("codex",),
        findings=(),
        sources_checked={"codex": ("https://github.com/openai/codex",)},
        overall_confidence="low",
    )
    md = render_report_markdown(report)
    assert "No actionable changes this cycle" in md
    assert "_None._" in md  # unverified section is empty


# ─── I/O ──────────────────────────────────────────────────────────────────


def test_write_radar_report_writes_to_named_directory(tmp_path):
    report = _make_sample_report()
    out = write_radar_report(tmp_path, report)
    assert out.exists()
    assert out.parent == tmp_path
    assert out.name == "2026-05-23T18-30-00Z-radar.md"
    body = out.read_text(encoding="utf-8")
    assert body.startswith("# Hermes AI Improvement Radar")


def test_write_radar_request_writes_companion_json(tmp_path):
    now = datetime(2026, 5, 23, 18, 30, tzinfo=timezone.utc)
    path = write_radar_request(
        tmp_path,
        tools=["claude-code", "codex"],
        since="2026-05-01",
        effort="medium",
        requested_by="jeremiah",
        now=now,
    )
    assert path.exists()
    assert path.suffix == ".json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["tools"] == ["claude-code", "codex"]
    assert payload["since"] == "2026-05-01"
    assert payload["requested_by"] == "jeremiah"
    assert payload["timestamp"] == "2026-05-23T18-30-00Z"


def test_utc_timestamp_is_filesystem_safe():
    ts = utc_timestamp(datetime(2026, 5, 23, 18, 30, 5, tzinfo=timezone.utc))
    # No colons (Windows).
    assert ":" not in ts
    # Ends with Z.
    assert ts.endswith("Z")
    assert ts == "2026-05-23T18-30-05Z"


def test_default_radar_dir_points_under_repo_root(tmp_path):
    d = ai_radar.default_radar_dir(tmp_path)
    assert d == tmp_path / ".hermes-orchestrator" / "ai-radar"


def test_finding_to_dict_round_trips():
    f = RadarFinding(
        tool="aider",
        feature="x",
        source="https://github.com/Aider-AI/aider",
        confidence="high",
        actionable=True,
        notes="note",
    )
    d = ai_radar.finding_to_dict(f)
    assert d["tool"] == "aider"
    assert d["confidence"] == "high"
    assert d["actionable"] is True
