"""Tests for muse_cli.jarvis_prime.social_research — public-API research plans."""

from __future__ import annotations

from pathlib import Path

import pytest

from muse_cli.jarvis_prime.memory import MemoryStore
from muse_cli.jarvis_prime.social_research import (
    SocialFinding,
    SocialSource,
    build_plan,
    store_findings,
    synthesize,
)


def test_build_plan_includes_three_default_sources() -> None:
    plan = build_plan("kanban orchestration")
    sources = {q.source for q in plan.queries}
    assert SocialSource.REDDIT in sources
    assert SocialSource.HACKERNEWS in sources
    assert SocialSource.GITHUB_ISSUES in sources


def test_build_plan_with_user_interests_adds_cross_refs() -> None:
    plan = build_plan("ai agents", user_interests=["python", "rust", "kotlin", "should-be-ignored"])
    # 3 interests + 3 default sources = 6 queries
    assert len(plan.queries) == 6
    # cross-ref queries use the interest in the query string
    cross_queries = [q.query for q in plan.queries if " " in q.query and any(i in q.query for i in ("python", "rust", "kotlin"))]
    assert len(cross_queries) == 3


def test_plan_serializes() -> None:
    plan = build_plan("x")
    payload = plan.to_dict()
    assert "queries" in payload
    assert "topic" in payload


def test_store_findings_writes_to_memory(tmp_path: Path) -> None:
    store = MemoryStore(journal_path=tmp_path / "mem.jsonl")
    findings = [
        SocialFinding(
            source=SocialSource.REDDIT,
            title="best python kanban tool",
            url="https://reddit.com/r/python/comments/abc",
            snippet="we use foo bar",
            score=42,
        ),
        SocialFinding(
            source=SocialSource.HACKERNEWS,
            title="kanban for AI agents",
            url="https://news.ycombinator.com/item?id=123",
            snippet="discussion thread",
            score=89,
        ),
    ]
    written = store_findings(findings, store)
    assert written == 2
    keys = {r.key for r in store.session}
    assert any("social_finding:reddit" in k for k in keys)
    assert any("social_finding:hackernews" in k for k in keys)


def test_synthesize_no_findings_explicit() -> None:
    out = synthesize([])
    assert "cannot synthesize" in out.lower()


def test_synthesize_single_source_caps_confidence() -> None:
    findings = [
        SocialFinding(
            source=SocialSource.REDDIT,
            title=f"thread {i}",
            url=f"https://reddit.com/r/x/{i}",
            snippet="s",
            score=i,
        )
        for i in range(3)
    ]
    out = synthesize(findings)
    assert "Single-source" in out


def test_synthesize_multi_source_passes() -> None:
    findings = [
        SocialFinding(SocialSource.REDDIT, "r1", "https://reddit.com/1", "s", score=5),
        SocialFinding(SocialSource.HACKERNEWS, "h1", "https://news.ycombinator.com/2", "s", score=10),
    ]
    out = synthesize(findings)
    assert "Single-source" not in out
    assert "reddit" in out
    assert "hackernews" in out
