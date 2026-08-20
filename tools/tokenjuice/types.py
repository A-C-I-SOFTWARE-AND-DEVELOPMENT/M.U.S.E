"""TokenJuice type definitions.

Clean-room Python reimplementation of the TokenJuice rule schema and reducer
I/O types. The schema mirrors the public MIT upstream ``vincentkoc/tokenjuice``
``JsonRule`` shape so the upstream MIT rule JSON loads without modification.

No GPL-licensed source is copied; only the public behavior and the MIT-licensed
rule data are reused. See ``THIRD_PARTY_NOTICES.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class RuleMatch:
    """Matching criteria for a rule (camelCase keys in JSON)."""

    tool_names: Optional[list[str]] = None
    argv0: Optional[list[str]] = None
    argv_includes: Optional[list[list[str]]] = None
    argv_includes_any: Optional[list[list[str]]] = None
    command_includes: Optional[list[str]] = None
    command_includes_any: Optional[list[str]] = None


@dataclass(frozen=True)
class RuleFilters:
    skip_patterns: Optional[list[str]] = None
    keep_patterns: Optional[list[str]] = None


@dataclass(frozen=True)
class RuleTransforms:
    strip_ansi: Optional[bool] = None
    trim_empty_edges: Optional[bool] = None
    dedupe_adjacent: Optional[bool] = None
    pretty_print_json: Optional[bool] = None


@dataclass(frozen=True)
class RuleSummarize:
    head: Optional[int] = None
    tail: Optional[int] = None


@dataclass(frozen=True)
class RuleCounter:
    name: str
    pattern: str
    flags: Optional[str] = None


@dataclass(frozen=True)
class RuleOutputMatch:
    pattern: str
    message: str
    flags: Optional[str] = None


@dataclass(frozen=True)
class RuleFailure:
    preserve_on_failure: Optional[bool] = None
    head: Optional[int] = None
    tail: Optional[int] = None


@dataclass(frozen=True)
class JsonRule:
    """A rule parsed from a JSON file (upstream ``JsonRule``)."""

    id: str
    family: str
    match: RuleMatch = field(default_factory=RuleMatch)
    description: Optional[str] = None
    priority: int = 0
    on_empty: Optional[str] = None
    match_output: Optional[list[RuleOutputMatch]] = None
    counter_source: str = "postKeep"  # or "preKeep"
    filters: Optional[RuleFilters] = None
    transforms: Optional[RuleTransforms] = None
    summarize: Optional[RuleSummarize] = None
    counters: Optional[list[RuleCounter]] = None
    failure: Optional[RuleFailure] = None
    origin: str = "builtin"  # builtin | user | project

    # ── JSON loading ─────────────────────────────────────────────────────
    @staticmethod
    def from_dict(data: dict[str, Any], origin: str = "builtin") -> "JsonRule":
        m = data.get("match") or {}
        match = RuleMatch(
            tool_names=m.get("toolNames"),
            argv0=m.get("argv0"),
            argv_includes=m.get("argvIncludes"),
            argv_includes_any=m.get("argvIncludesAny"),
            command_includes=m.get("commandIncludes"),
            command_includes_any=m.get("commandIncludesAny"),
        )
        f = data.get("filters")
        filters = (
            RuleFilters(skip_patterns=f.get("skipPatterns"), keep_patterns=f.get("keepPatterns"))
            if f
            else None
        )
        t = data.get("transforms")
        transforms = (
            RuleTransforms(
                strip_ansi=t.get("stripAnsi"),
                trim_empty_edges=t.get("trimEmptyEdges"),
                dedupe_adjacent=t.get("dedupeAdjacent"),
                pretty_print_json=t.get("prettyPrintJson"),
            )
            if t
            else None
        )
        s = data.get("summarize")
        summarize = RuleSummarize(head=s.get("head"), tail=s.get("tail")) if s else None
        counters = (
            [RuleCounter(name=c["name"], pattern=c["pattern"], flags=c.get("flags")) for c in data["counters"]]
            if data.get("counters")
            else None
        )
        match_output = (
            [
                RuleOutputMatch(pattern=o["pattern"], message=o["message"], flags=o.get("flags"))
                for o in data["matchOutput"]
            ]
            if data.get("matchOutput")
            else None
        )
        fa = data.get("failure")
        failure = (
            RuleFailure(
                preserve_on_failure=fa.get("preserveOnFailure"),
                head=fa.get("head"),
                tail=fa.get("tail"),
            )
            if fa
            else None
        )
        return JsonRule(
            id=data["id"],
            family=data.get("family", "generic"),
            match=match,
            description=data.get("description"),
            priority=int(data.get("priority", 0) or 0),
            on_empty=data.get("onEmpty"),
            match_output=match_output,
            counter_source=data.get("counterSource", "postKeep"),
            filters=filters,
            transforms=transforms,
            summarize=summarize,
            counters=counters,
            failure=failure,
            origin=origin,
        )


@dataclass(frozen=True)
class ToolExecutionInput:
    tool_name: str
    command: Optional[str] = None
    argv: Optional[list[str]] = None
    stdout: Optional[str] = None
    exit_code: Optional[int] = None


@dataclass(frozen=True)
class ReduceOptions:
    """Per-call reduction options (failure window sizes etc.)."""

    compact_failures: bool = True
    failure_head_lines: int = 80
    failure_tail_lines: int = 120


@dataclass(frozen=True)
class CompactionStats:
    tool_name: str
    rule_id: str
    original_chars: int
    compacted_chars: int
    applied: bool
    duration_ms: float = 0.0
    command: Optional[str] = None
    exit_code: Optional[int] = None
    raw_persisted: bool = False
    raw_ref: Optional[str] = None

    @property
    def ratio(self) -> float:
        if self.original_chars == 0:
            return 1.0
        return self.compacted_chars / self.original_chars
