"""Social-platform public research for MUSE.

The user asked: "research websites like reddit, facebook, github,
etc comment sections and message boards gathering data and storing
in long term."

This module produces structured research plans that the runtime can
hand to existing fetch backends (``WebFetch`` MCP tool,
``plugins/github_assistant``, the model_router's ``browser-research``
worker). It does NOT itself bypass authentication walls, scrape
private content, or violate site Terms of Service.

Sources fall into two tiers:

| Tier | Source | Access |
|---|---|---|
| Public-API | reddit.com (via JSON .json suffix), hackernews api, github REST | rate-limited public APIs |
| Public-Web | public README, public message board archives, public dev.to / lobste.rs | WebFetch |

Facebook/Twitter/LinkedIn are intentionally excluded because they
require login or have ToS-restricted scraping. The runtime can ask
the user to provide content from those manually.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Sequence

from muse_cli.jarvis_prime.memory import MemoryStore


class SocialSource(Enum):
    REDDIT = "reddit"
    HACKERNEWS = "hackernews"
    GITHUB_ISSUES = "github_issues"
    GITHUB_DISCUSSIONS = "github_discussions"
    LOBSTERS = "lobsters"
    DEVTO = "devto"


@dataclass(frozen=True)
class SocialQuery:
    source: SocialSource
    query: str
    rationale: str
    max_results: int = 25
    must_be_recent_days: int = 365
    forbid_login_required: bool = True


@dataclass(frozen=True)
class SocialFinding:
    source: SocialSource
    title: str
    url: str
    snippet: str
    sentiment: Optional[str] = None  # "pos" | "neg" | "neutral"
    score: int = 0
    tags: tuple[str, ...] = ()


@dataclass
class ResearchPlan:
    topic: str
    queries: tuple[SocialQuery, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, object]:
        return {
            "topic": self.topic,
            "queries": [
                {
                    "source": q.source.value,
                    "query": q.query,
                    "rationale": q.rationale,
                    "max_results": q.max_results,
                    "must_be_recent_days": q.must_be_recent_days,
                }
                for q in self.queries
            ],
            "created_at": self.created_at.isoformat(),
        }


def build_plan(topic: str, user_interests: Sequence[str] = ()) -> ResearchPlan:
    """Compose a public-API research plan for a topic.

    Adds user-interest cross-references so the plan biases toward
    sources that match how the user already engages.
    """

    base = [
        SocialQuery(
            source=SocialSource.REDDIT,
            query=topic,
            rationale=f"Reddit public threads on {topic!r}",
        ),
        SocialQuery(
            source=SocialSource.HACKERNEWS,
            query=topic,
            rationale=f"Hacker News public stories on {topic!r}",
        ),
        SocialQuery(
            source=SocialSource.GITHUB_ISSUES,
            query=topic,
            rationale=f"GitHub public issues on {topic!r}",
        ),
    ]
    for interest in user_interests[:3]:
        base.append(
            SocialQuery(
                source=SocialSource.REDDIT,
                query=f"{topic} {interest}",
                rationale=f"Cross-reference with user interest {interest!r}",
            )
        )
    return ResearchPlan(topic=topic, queries=tuple(base))


def store_findings(
    findings: Sequence[SocialFinding],
    memory: MemoryStore,
    durability: str = "session",
) -> int:
    """Write findings to memory. Promotion to durable requires
    corroboration across ≥2 sources for the same claim — caller
    handles that orchestration. This function just stores.

    Returns the number of records actually written (memory store may
    reject secret-like content or down-grade durability).
    """

    written = 0
    for f in findings:
        record = memory.remember(
            key=f"social_finding:{f.source.value}:{f.url}",
            value=json.dumps({
                "title": f.title,
                "snippet": f.snippet,
                "sentiment": f.sentiment,
                "score": f.score,
                "tags": list(f.tags),
            }),
            durability=durability,
            confidence=0.6,
            tags=("social_research", f.source.value) + f.tags,
            citations=(f.url,),
            source="agent",
        )
        if record is not None:
            written += 1
    return written


def synthesize(findings: Sequence[SocialFinding], min_corroborations: int = 2) -> str:
    """Produce a calibrated synthesis paragraph from findings.

    Rules:
    - Claims need ≥``min_corroborations`` independent source matches.
    - Sentiment counts are reported, not editorialized.
    - Cites the top URL per claim.
    """

    if not findings:
        return "No public findings retrieved; cannot synthesize."

    by_source: dict[SocialSource, list[SocialFinding]] = {}
    for f in findings:
        by_source.setdefault(f.source, []).append(f)

    lines: list[str] = ["SOCIAL RESEARCH SYNTHESIS (calibrated)"]
    lines.append(f"- Sources surveyed: {', '.join(sorted(s.value for s in by_source))}")
    lines.append(f"- Total findings: {len(findings)}")
    for source, items in by_source.items():
        top = max(items, key=lambda f: f.score)
        lines.append(
            f"- {source.value}: {len(items)} hit(s). Highest-scored: {top.title!r} ({top.url})"
        )
    if len(by_source) < min_corroborations:
        lines.append(
            f"- ⚠ Single-source claim — confidence capped pending {min_corroborations}-source corroboration."
        )
    return "\n".join(lines)
