"""Five validation gates for Hermes orchestration artifacts.

Every merged artifact must pass all five gates before it can be published.
The gates are intentionally stdlib-only and deterministic.

Gates:
1. ``structure`` — artifact has the documented header markers.
2. ``size`` — body length within bounds (not empty, not pathological).
3. ``secrets`` — body contains no credential-shaped strings.
4. ``unicode`` — body is valid UTF-8 with no NUL bytes or stray BOMs.
5. ``policy`` — artifact does not assert it took destructive actions.
"""

from __future__ import annotations

import dataclasses
import re
from typing import Callable

from hermes_cli.merge_engine import MergeArtifact


@dataclasses.dataclass(frozen=True)
class GateReport:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclasses.dataclass(frozen=True)
class ValidationReport:
    artifact_title: str
    gates: list[GateReport]

    @property
    def passed(self) -> bool:
        return all(g.passed for g in self.gates)

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_title": self.artifact_title,
            "passed": self.passed,
            "gates": [g.to_dict() for g in self.gates],
        }


# ── Gate implementations ─────────────────────────────────────────────


def gate_structure(artifact: MergeArtifact) -> GateReport:
    if artifact.is_draw:
        required = ("Arbiter flagged a draw",)
    else:
        required = ("**Worker:**", "**Role:**", "## Summary")
    missing = [m for m in required if m not in artifact.body]
    return GateReport(
        name="structure",
        passed=not missing,
        detail="ok" if not missing else f"missing markers: {missing}",
    )


def gate_size(artifact: MergeArtifact, *, min_chars: int = 40, max_chars: int = 50_000) -> GateReport:
    n = len(artifact.body)
    if n < min_chars:
        return GateReport(name="size", passed=False, detail=f"body too short: {n} < {min_chars}")
    if n > max_chars:
        return GateReport(name="size", passed=False, detail=f"body too long: {n} > {max_chars}")
    return GateReport(name="size", passed=True, detail=f"{n} chars")


_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"AKIA[0-9A-Z]{16}"),            # AWS access key
    re.compile(r"sk-[A-Za-z0-9]{20,}"),         # OpenAI-style secret
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),        # GitHub PAT
    re.compile(r"xox[abp]-[A-Za-z0-9-]{10,}"),  # Slack token
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),
)


def gate_secrets(artifact: MergeArtifact) -> GateReport:
    hits: list[str] = []
    for pat in _SECRET_PATTERNS:
        if pat.search(artifact.body):
            hits.append(pat.pattern)
    return GateReport(
        name="secrets",
        passed=not hits,
        detail="ok" if not hits else f"matched patterns: {hits}",
    )


def gate_unicode(artifact: MergeArtifact) -> GateReport:
    body = artifact.body
    if "\x00" in body:
        return GateReport(name="unicode", passed=False, detail="contains NUL byte")
    if body.startswith("﻿"):
        return GateReport(name="unicode", passed=False, detail="stray UTF-8 BOM at start")
    try:
        body.encode("utf-8")
    except UnicodeEncodeError as exc:
        return GateReport(name="unicode", passed=False, detail=f"encode failed: {exc}")
    return GateReport(name="unicode", passed=True, detail="ok")


_DESTRUCTIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\brm\s+-rf\s+/(?!tmp|var)"),
    re.compile(r"\bgit\s+push\s+--force\b"),
    re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE),
)


def gate_policy(artifact: MergeArtifact) -> GateReport:
    hits = [p.pattern for p in _DESTRUCTIVE_PATTERNS if p.search(artifact.body)]
    return GateReport(
        name="policy",
        passed=not hits,
        detail="ok" if not hits else f"destructive patterns: {hits}",
    )


GATES: tuple[Callable[[MergeArtifact], GateReport], ...] = (
    gate_structure,
    gate_size,
    gate_secrets,
    gate_unicode,
    gate_policy,
)


def run_gates(artifact: MergeArtifact) -> ValidationReport:
    return ValidationReport(
        artifact_title=artifact.title,
        gates=[gate(artifact) for gate in GATES],
    )
