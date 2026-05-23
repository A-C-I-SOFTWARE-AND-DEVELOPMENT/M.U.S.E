"""AI improvement radar — Hermes routing intelligence.

This module is the Python side of the ``ai-improvement-radar`` skill
(see ``skills/ai-improvement-radar/SKILL.md`` and the narrative
companion in ``docs/ai-intelligence/ai-improvement-radar.md``).

What lives here:

* The canonical watchlist of external coding agents Hermes tracks
  (Codex, Claude Code, Aider, Goose, Continue, OpenHands,
  OpenClaw-style personal agents, Supabase AI tools, Vercel AI
  tooling, Android voice/STT tooling, etc.).
* A ``RadarFinding`` dataclass describing one tracked observation —
  tool, feature, source URL, confidence, actionability.
* A ``RadarReport`` builder that renders the fixed-structure markdown
  report defined by the skill.
* A ``recommend_policy_updates`` helper that turns a set of findings
  into a structured recommendation for the three policy artifacts
  (``model-registry.yaml``, ``model-routing-policy.md``,
  ``tool-capability-matrix.md``) — *recommendation only*; this module
  never edits the policy artifacts.

What does NOT live here:

* HTTP fetching, scraping, or any network I/O. The radar is run by a
  human (or by a Hermes worker that has WebFetch/WebSearch). Findings
  are passed *into* this module after they've been collected.
* Auto-application of routing changes. This module produces
  recommendations and reports; promotion is a separate, human-gated
  step.

The module is intentionally dependency-free beyond the stdlib so it
loads in every environment Hermes runs in (Termux, slim Docker, etc.).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence


# ---------------------------------------------------------------------------
# Canonical watchlist
# ---------------------------------------------------------------------------

# Tools the radar tracks by default. New entries require (a) an official
# source URL and (b) a one-line justification of why Hermes might route
# to them — see the skill for the rule.

TRACKED_TOOLS: tuple[dict, ...] = (
    {
        "id": "codex",
        "vendor": "OpenAI",
        "category": "coding-agent",
        "official_sources": (
            "https://github.com/openai/codex",
            "https://platform.openai.com/docs",
        ),
    },
    {
        "id": "claude-code",
        "vendor": "Anthropic",
        "category": "coding-agent",
        "official_sources": (
            "https://code.claude.com/docs",
            "https://www.anthropic.com/news",
        ),
    },
    {
        "id": "aider",
        "vendor": "Aider community",
        "category": "coding-agent",
        "official_sources": (
            "https://github.com/Aider-AI/aider",
            "https://aider.chat",
        ),
    },
    {
        "id": "goose",
        "vendor": "Block",
        "category": "coding-agent",
        "official_sources": (
            "https://github.com/block/goose",
            "https://block.github.io/goose",
        ),
    },
    {
        "id": "continue",
        "vendor": "Continue Dev",
        "category": "coding-agent",
        "official_sources": (
            "https://github.com/continuedev/continue",
            "https://docs.continue.dev",
        ),
    },
    {
        "id": "openhands",
        "vendor": "All-Hands-AI",
        "category": "coding-agent",
        "official_sources": (
            "https://github.com/All-Hands-AI/OpenHands",
            "https://docs.all-hands.dev",
        ),
    },
    {
        "id": "openclaw-personal-agents",
        "vendor": "various",
        "category": "personal-agent",
        "official_sources": (),  # per-project; recorded when tracked
    },
    {
        "id": "supabase-ai",
        "vendor": "Supabase",
        "category": "platform-ai",
        "official_sources": (
            "https://supabase.com/docs",
            "https://github.com/supabase/supabase",
        ),
    },
    {
        "id": "vercel-ai",
        "vendor": "Vercel",
        "category": "platform-ai",
        "official_sources": (
            "https://vercel.com/docs",
            "https://sdk.vercel.ai",
        ),
    },
    {
        "id": "android-voice-stt",
        "vendor": "various (Google, Whisper, Sherpa, etc.)",
        "category": "voice-stt",
        "official_sources": (
            "https://developer.android.com",
            "https://github.com/openai/whisper",
        ),
    },
)


def tracked_tool_ids() -> tuple[str, ...]:
    """Return the stable id of every tool on the default watchlist."""
    return tuple(t["id"] for t in TRACKED_TOOLS)


def get_tracked_tool(tool_id: str) -> Optional[dict]:
    """Return the watchlist entry for ``tool_id``, or ``None``."""
    for entry in TRACKED_TOOLS:
        if entry["id"] == tool_id:
            return dict(entry)
    return None


# ---------------------------------------------------------------------------
# Confidence levels and source quality
# ---------------------------------------------------------------------------

CONFIDENCE_LEVELS: tuple[str, ...] = ("high", "medium", "low", "unverified")


# Hostnames we consider "official" for at least one tracked vendor. The
# check is a soft heuristic — the skill is the authority on what counts —
# but it is enough to flag obvious non-sources (reddit, twitter, hn, etc.)
# as ``unverified``.
_OFFICIAL_DOMAIN_HINTS: tuple[str, ...] = (
    "github.com/openai",
    "github.com/anthropic",
    "github.com/aider-ai",
    "github.com/block",
    "github.com/continuedev",
    "github.com/all-hands-ai",
    "github.com/supabase",
    "github.com/google-gemini",
    "github.com/google",
    "github.com/openai/whisper",
    "openai.com",
    "anthropic.com",
    "claude.com",
    "code.claude.com",
    "aider.chat",
    "block.github.io",
    "continue.dev",
    "all-hands.dev",
    "supabase.com",
    "vercel.com",
    "sdk.vercel.ai",
    "developer.android.com",
    "ai.google.dev",
    "deepmind.google",
)

# Sources we will *never* accept as primary evidence. They may be quoted
# as colour in the "Unverified items" section of the report, but never
# drive a recommendation.
_DISQUALIFIED_DOMAIN_HINTS: tuple[str, ...] = (
    "reddit.com",
    "twitter.com",
    "x.com",
    "news.ycombinator.com",
    "hackernews.com",
    "medium.com",        # personal blogs; not vendor-official
    "substack.com",
    "tiktok.com",
    "youtube.com",       # uploads vary; vendor channels need explicit allow
)


def is_official_source(url: str) -> bool:
    """Return True if ``url`` looks like an official vendor source.

    Heuristic only — see ``_OFFICIAL_DOMAIN_HINTS``. Empty / non-URL
    inputs are False.
    """
    if not url or not isinstance(url, str):
        return False
    lowered = url.lower()
    if not (lowered.startswith("http://") or lowered.startswith("https://")):
        return False
    for hint in _DISQUALIFIED_DOMAIN_HINTS:
        if hint in lowered:
            return False
    for hint in _OFFICIAL_DOMAIN_HINTS:
        if hint in lowered:
            return True
    return False


def is_disqualified_source(url: str) -> bool:
    """Return True if ``url`` is a social / forum / blog source that
    must never drive a recommendation.
    """
    if not url or not isinstance(url, str):
        return False
    lowered = url.lower()
    return any(hint in lowered for hint in _DISQUALIFIED_DOMAIN_HINTS)


# ---------------------------------------------------------------------------
# Finding + report dataclasses
# ---------------------------------------------------------------------------


@dataclass
class RadarFinding:
    """One observation: tool X has feature Y, cited by source Z.

    ``confidence`` must be one of :data:`CONFIDENCE_LEVELS`. The
    ``actionable`` flag answers "would Hermes do anything differently
    if it picked this up?" — items where the answer is "no" should be
    dropped, not merely marked as non-actionable.
    """

    tool: str
    feature: str
    source: str
    confidence: str = "unverified"
    actionable: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(
                f"confidence must be one of {CONFIDENCE_LEVELS}, "
                f"got {self.confidence!r}"
            )
        # Source-quality enforcement: a finding whose only source is
        # disqualified (reddit, twitter, etc.) can never claim better
        # than ``unverified``. This is a guard rail, not a substitute
        # for human judgement.
        if is_disqualified_source(self.source) and self.confidence != "unverified":
            self.confidence = "unverified"
            self.actionable = False
            note = "source is social/forum; forced to unverified"
            self.notes = f"{self.notes}; {note}".strip("; ")
        # A finding without an official source cannot be high-confidence.
        if (
            self.confidence == "high"
            and not is_official_source(self.source)
        ):
            self.confidence = "medium"
            note = "downgraded from high: source not recognised as official"
            self.notes = f"{self.notes}; {note}".strip("; ")

    @property
    def is_unverified(self) -> bool:
        return self.confidence == "unverified"


def mark_unverified(finding: RadarFinding, reason: str = "") -> RadarFinding:
    """Return a copy of ``finding`` forced to ``unverified``."""
    note = "manually marked unverified"
    if reason:
        note = f"{note}: {reason}"
    return RadarFinding(
        tool=finding.tool,
        feature=finding.feature,
        source=finding.source,
        confidence="unverified",
        actionable=False,
        notes=f"{finding.notes}; {note}".strip("; "),
    )


@dataclass
class RadarReport:
    """A complete radar report ready to be rendered to markdown."""

    timestamp: str
    summary: str = ""
    tools_surveyed: tuple[str, ...] = ()
    findings: tuple[RadarFinding, ...] = ()
    sources_checked: Mapping[str, Sequence[str]] = field(default_factory=dict)
    overall_confidence: str = "low"
    notes: str = ""

    @property
    def verified_findings(self) -> tuple[RadarFinding, ...]:
        return tuple(f for f in self.findings if not f.is_unverified)

    @property
    def unverified_findings(self) -> tuple[RadarFinding, ...]:
        return tuple(f for f in self.findings if f.is_unverified)


def utc_timestamp(now: Optional[datetime] = None) -> str:
    """Return a filesystem-safe ISO-ish UTC timestamp.

    Format: ``YYYY-MM-DDTHH-MM-SSZ`` — colons in the time portion are
    swapped for hyphens so the value is safe to use in filenames on
    Windows / NTFS.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.strftime("%Y-%m-%dT%H-%M-%SZ")


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def render_report_markdown(report: RadarReport) -> str:
    """Render ``report`` as the fixed-structure markdown the skill
    requires.

    The section order matches ``skills/ai-improvement-radar/SKILL.md``
    ("Radar report format"). Skipping or reordering sections is a
    defect — that contract is enforced by the tests.
    """
    lines: list[str] = []
    lines.append(f"# Hermes AI Improvement Radar — {report.timestamp}")
    lines.append("")

    lines.append("## Summary")
    lines.append(report.summary.strip() or "_No summary provided._")
    lines.append("")

    lines.append("## Tools surveyed")
    if report.tools_surveyed:
        for t in report.tools_surveyed:
            lines.append(f"- {t}")
    else:
        lines.append("_None this cycle._")
    lines.append("")

    lines.append("## New features discovered")
    lines.append("| Tool | Feature | Source | Confidence | Actionable? |")
    lines.append("|---|---|---|---|---|")
    if report.verified_findings:
        for f in report.verified_findings:
            actionable = "yes" if f.actionable else "no"
            lines.append(
                f"| {f.tool} | {f.feature} | {f.source} | "
                f"{f.confidence} | {actionable} |"
            )
    else:
        lines.append("| _none_ | | | | |")
    lines.append("")

    lines.append("## Sources checked")
    if report.sources_checked:
        for tool, urls in report.sources_checked.items():
            urls_list = list(urls) or ["_no sources reachable this cycle_"]
            lines.append(f"- {tool}: " + ", ".join(urls_list))
    else:
        lines.append("_No sources recorded._")
    lines.append("")

    lines.append("## Relevance to Hermes")
    relevant = [f for f in report.verified_findings if f.actionable]
    if relevant:
        for f in relevant:
            lines.append(
                f"- **{f.tool}** — {f.feature}. "
                "Routing impact: see Implementation recommendation."
            )
    else:
        lines.append(
            "No actionable changes this cycle. Routing policy stays as is."
        )
    lines.append("")

    lines.append("## Implementation recommendation")
    recs = recommend_policy_updates(report.findings)
    if recs["changes"]:
        for i, change in enumerate(recs["changes"], 1):
            lines.append(f"{i}. {change}")
    else:
        lines.append("_No implementation changes recommended this cycle._")
    lines.append("")

    lines.append("## Routing policy update needed")
    for artifact, decision in (
        ("model-registry.yaml", recs["model_registry"]),
        ("model-routing-policy.md", recs["model_routing_policy"]),
        ("tool-capability-matrix.md", recs["tool_capability_matrix"]),
    ):
        lines.append(f"- {artifact}: {decision}")
    lines.append("")

    lines.append("## Confidence level")
    lines.append(
        f"Overall: {report.overall_confidence}. "
        + (report.notes.strip() or "")
    )
    lines.append("")

    lines.append("## Unverified items (do not act on)")
    if report.unverified_findings:
        for f in report.unverified_findings:
            corroborator = "official changelog or vendor docs"
            lines.append(
                f"- {f.tool}: {f.feature} "
                f"(source: {f.source or 'n/a'}). "
                f"Would need: {corroborator}."
            )
    else:
        lines.append("_None._")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Policy-update recommendation
# ---------------------------------------------------------------------------


_EVIDENCE_RULE = (
    "weak evidence (single low-confidence source) — do not act"
)


def recommend_policy_updates(
    findings: Iterable[RadarFinding],
) -> dict:
    """Translate a set of findings into recommended policy edits.

    The rules below mirror ``docs/ai-intelligence/ai-improvement-radar.md``
    ("Confidence levels"):

    * ``high``  → may update routing policy, registry, and capability matrix.
    * ``medium`` → may update capability matrix; defer routing-policy change.
    * ``low``   → note in matrix as preview; do not change routing.
    * ``unverified`` → do nothing; corroborate first.

    Returns a dict with these keys::

        {
          "changes": ["touch <file>: <one-line nature of change>", ...],
          "model_registry": "yes — ..." | "no",
          "model_routing_policy": "yes — ..." | "no",
          "tool_capability_matrix": "yes — ..." | "no",
          "weak_evidence_skipped": int,
        }

    Importantly, the helper *never* edits the policy artifacts. It only
    returns the recommendation; promotion is a separate, human-gated
    step (see ``self_improvement.py`` and ``agent/curator.py``).
    """
    changes: list[str] = []
    high_count = 0
    medium_count = 0
    low_count = 0
    weak_skipped = 0

    for f in findings:
        # Unverified findings are always counted as weak-evidence
        # skips, even when the originator marked them non-actionable —
        # that lets the report surface "we saw N rumors and acted on
        # zero of them" without needing extra plumbing.
        if f.confidence == "unverified":
            weak_skipped += 1
            continue
        if not f.actionable:
            continue
        if f.confidence == "high":
            high_count += 1
            changes.append(
                f"touch docs/ai-intelligence/tool-capability-matrix.md: "
                f"record {f.tool} → {f.feature} (high confidence)."
            )
            changes.append(
                f"touch docs/ai-intelligence/model-routing-policy.md: "
                f"consider routing-weight nudge for {f.tool} on "
                f"capabilities that use {f.feature}."
            )
            changes.append(
                f"touch docs/ai-intelligence/model-registry.yaml: "
                f"update {f.tool} entry if version / context / pricing "
                f"changed."
            )
        elif f.confidence == "medium":
            medium_count += 1
            changes.append(
                f"touch docs/ai-intelligence/tool-capability-matrix.md: "
                f"record {f.tool} → {f.feature} (medium confidence; not "
                f"yet field-tested)."
            )
        elif f.confidence == "low":
            low_count += 1
            changes.append(
                f"touch docs/ai-intelligence/tool-capability-matrix.md: "
                f"note {f.tool} → {f.feature} as preview / feature-flagged."
            )
            weak_skipped += 1
        else:
            weak_skipped += 1

    return {
        "changes": changes,
        "model_registry": (
            f"yes — update entries for {high_count} tool(s)"
            if high_count
            else "no"
        ),
        "model_routing_policy": (
            f"yes — consider weight nudges for {high_count} tool(s)"
            if high_count
            else "no"
        ),
        "tool_capability_matrix": (
            f"yes — record {high_count + medium_count + low_count} "
            f"new capability row(s)"
            if (high_count + medium_count + low_count)
            else "no"
        ),
        "weak_evidence_skipped": weak_skipped,
        "weak_evidence_rule": _EVIDENCE_RULE,
    }


# ---------------------------------------------------------------------------
# I/O — writing the report + companion request file
# ---------------------------------------------------------------------------


def default_radar_dir(repo_root: Optional[Path] = None) -> Path:
    """Default output directory for radar artifacts.

    Per the skill: ``.hermes-orchestrator/ai-radar/`` under the current
    repo (or under ``repo_root`` if supplied).
    """
    base = Path(repo_root) if repo_root else Path.cwd()
    return base / ".hermes-orchestrator" / "ai-radar"


def write_radar_request(
    out_dir: Path,
    *,
    tools: Sequence[str],
    since: Optional[str] = None,
    effort: str = "medium",
    requested_by: str = "unknown",
    now: Optional[datetime] = None,
) -> Path:
    """Write a ``<timestamp>-request.json`` file under ``out_dir``.

    This is what ``scripts/hermes-ai-radar.sh`` produces when the user
    triggers a radar. The skill reads the file when it runs.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = utc_timestamp(now)
    payload = {
        "timestamp": ts,
        "requested_by": requested_by,
        "tools": list(tools),
        "since": since,
        "effort": effort,
    }
    path = out_dir / f"{ts}-request.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def write_radar_report(
    out_dir: Path,
    report: RadarReport,
) -> Path:
    """Render ``report`` as markdown and write it under ``out_dir``.

    Returns the path written. The filename is
    ``<report.timestamp>-radar.md``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{report.timestamp}-radar.md"
    path.write_text(render_report_markdown(report), encoding="utf-8")
    return path


def finding_to_dict(f: RadarFinding) -> dict:
    """Public helper — render a finding as a plain dict (for JSON)."""
    return asdict(f)


__all__ = [
    "TRACKED_TOOLS",
    "CONFIDENCE_LEVELS",
    "RadarFinding",
    "RadarReport",
    "default_radar_dir",
    "finding_to_dict",
    "get_tracked_tool",
    "is_disqualified_source",
    "is_official_source",
    "mark_unverified",
    "recommend_policy_updates",
    "render_report_markdown",
    "tracked_tool_ids",
    "utc_timestamp",
    "write_radar_report",
    "write_radar_request",
]
