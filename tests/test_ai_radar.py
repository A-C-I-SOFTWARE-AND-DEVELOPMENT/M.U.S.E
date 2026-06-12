"""Tests for ``muse_cli/ai_radar.py``.

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

from muse_cli import ai_radar
from muse_cli.ai_radar import (
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
    assert not is_official_source(None)


def test_is_disqualified_source_flags_social_and_forums():
    assert is_disqualified_source("https://www.reddit.com/r/foo")
    assert is_disqualified_source("https://twitter.com/somebody/status/123")
    assert is_disqualified_source("https://news.ycombinator.com/item?id=1")
    assert not is_disqualified_source("https://code.claude.com/docs")


def test_is_official_source_uses_parsed_host_not_substring():
    """A URL that only *mentions* an official domain in its query
    string or path must not be treated as official."""
    # Domain hidden in the query string.
    assert not is_official_source(
        "https://evil.example.com/?redirect=https://github.com/openai/codex"
    )
    # Domain hidden in the fragment.
    assert not is_official_source(
        "https://evil.example.com/#anthropic.com"
    )
    # Domain hidden in a path that just happens to contain the literal.
    assert not is_official_source(
        "https://evil.example.com/anthropic.com/foo"
    )


def test_is_official_source_requires_path_prefix_for_github_orgs():
    """``github.com`` alone is not enough — we need a real path under
    a tracked org."""
    # Bare github.com is not "official" — it's just GitHub itself.
    assert not is_official_source("https://github.com")
    # A different org is not official.
    assert not is_official_source("https://github.com/somebody-else/codex")
    # ``/openaifoo`` is *not* a prefix match for ``/openai``.
    assert not is_official_source("https://github.com/openaifoo/bar")
    # ``/openai/codex`` is.
    assert is_official_source("https://github.com/openai/codex")


def test_is_disqualified_source_uses_parsed_host_not_substring():
    """A URL whose query string mentions reddit must not be flagged
    if the *real* host is something else — and vice versa, a real
    reddit URL must still be flagged regardless of path."""
    # Real reddit host → disqualified.
    assert is_disqualified_source("https://old.reddit.com/r/foo")
    assert is_disqualified_source("https://www.reddit.com/")
    # Substring smuggling → NOT disqualified (the real host is the
    # vendor domain).
    assert not is_disqualified_source(
        "https://code.claude.com/docs?ref=reddit.com"
    )


def test_is_official_source_blocks_disqualified_host_first():
    """If the parsed host is on the social/forum blocklist, no path
    can resurrect it as official."""
    # Adversarial: a reddit URL whose path is `/openai`.
    assert not is_official_source("https://www.reddit.com/openai")
    assert is_disqualified_source("https://www.reddit.com/openai")


def test_url_parsing_handles_malformed_input():
    # ``ftp://`` is not http(s).
    assert not is_official_source("ftp://github.com/openai/codex")
    # No scheme at all.
    assert not is_official_source("github.com/openai/codex")
    # Empty host.
    assert not is_official_source("https:///foo")
    # Non-strings.
    assert not is_official_source(123)
    assert not is_official_source({"url": "https://github.com/openai/codex"})
    assert not is_disqualified_source(123)


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


def test_write_radar_report_sanitises_malicious_timestamp(tmp_path):
    """A malformed timestamp must not be able to escape ``out_dir``."""
    report = RadarReport(
        timestamp="../../etc/passwd",
        summary="adversarial",
        tools_surveyed=(),
        findings=(),
        sources_checked={},
        overall_confidence="low",
    )
    out = write_radar_report(tmp_path, report)
    # The written file must live under tmp_path, not somewhere up the tree.
    assert out.parent.resolve() == tmp_path.resolve()
    # And the unsafe characters are gone from the filename.
    assert ".." not in out.name
    assert "/" not in out.name
    assert out.name.endswith("-radar.md")


def test_write_radar_report_sanitises_path_separators_in_timestamp(tmp_path):
    report = RadarReport(
        timestamp="2026-05-23T18:30:00Z",  # colons — not the canonical shape
        summary="",
        findings=(),
    )
    out = write_radar_report(tmp_path, report)
    assert ":" not in out.name
    assert out.parent.resolve() == tmp_path.resolve()


def test_write_radar_report_keeps_canonical_timestamps_unchanged(tmp_path):
    report = RadarReport(
        timestamp="2026-05-23T18-30-00Z",
        summary="",
        findings=(),
    )
    out = write_radar_report(tmp_path, report)
    assert out.name == "2026-05-23T18-30-00Z-radar.md"


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
