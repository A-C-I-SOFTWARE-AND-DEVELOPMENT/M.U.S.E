"""Navigator — the public entry point for repo navigation.

Wires the index, symbol graph, localizer, tracer, and edit-site ranker into a
single object the orchestrator (or a CLI lane) calls *before* dispatching a
coding worker. It answers three questions and packages them so the decision is
recorded in the job ledger and the worker gets a focused packet instead of the
whole repo.

Typical flow::

    nav = Navigator.for_repo(".")
    result = nav.navigate("fix the timeout in the issue localizer")
    packet = result.worker_packet()        # hand to Claude Code / Codex / Aider
    ledger_record = result.to_ledger_record(job_id="job-123")

Nothing here mutates the repo or the ledger; callers own persistence. This
keeps the navigator pure and unit-testable, and lets the orchestrator decide
how to record the decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from muse_cli.jarvis_prime.navigation.code_map import CodeMap
from muse_cli.jarvis_prime.navigation.dependency_trace import DependencyTracer
from muse_cli.jarvis_prime.navigation.edit_site_ranker import EditSite, EditSiteRanker
from muse_cli.jarvis_prime.navigation.issue_localizer import (
    IssueLocalizer,
    Localization,
)
from muse_cli.jarvis_prime.navigation.repo_index import RepoIndex
from muse_cli.jarvis_prime.navigation.symbol_graph import SymbolGraph


@dataclass(frozen=True)
class NavigationResult:
    issue: str
    localizations: tuple[Localization, ...]
    edit_sites: tuple[EditSite, ...]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def top_files(self) -> list[str]:
        return [s.path for s in self.edit_sites]

    def worker_packet(self, *, max_sites: int = 5) -> dict[str, object]:
        """A compact, worker-agnostic edit packet.

        Suitable for Claude Code / Codex / Aider / Goose / local model workers.
        Lists candidate files in priority order with the tests to run and the
        dependents to watch — exactly what a Prompt → Patch → Test loop needs.
        """

        sites = list(self.edit_sites)[:max_sites]
        tests: list[str] = []
        for s in sites:
            for t in s.suggested_tests:
                if t not in tests:
                    tests.append(t)
        return {
            "objective": self.issue,
            "candidate_files": [s.path for s in sites],
            "edit_sites": [s.to_dict() for s in sites],
            "verify_with": tests,
            "navigation_method": "lexical+path+symbol+test+git (deterministic, no LLM localization)",
        }

    def to_ledger_record(self, *, job_id: str | None = None) -> dict[str, object]:
        """A decision-ledger-compatible record of this navigation decision."""

        return {
            "kind": "navigation_decision",
            "job_id": job_id,
            "created_at": self.created_at,
            "objective": self.issue,
            "ranked_files": [
                {
                    "path": s.path,
                    "rank": s.rank,
                    "confidence": round(s.confidence, 4),
                    "rationale": s.rationale,
                    "signals": {k: round(v, 4) for k, v in s.signals.items()},
                }
                for s in self.edit_sites
            ],
            "verify_with": self.worker_packet()["verify_with"],
            "method": "deterministic-multi-signal",
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "issue": self.issue,
            "created_at": self.created_at,
            "localizations": [loc.to_dict() for loc in self.localizations],
            "edit_sites": [s.to_dict() for s in self.edit_sites],
        }


@dataclass
class Navigator:
    code_map: CodeMap
    localizer: IssueLocalizer
    tracer: DependencyTracer
    ranker: EditSiteRanker

    @classmethod
    def for_repo(cls, root: str | Path, *, use_git: bool = True) -> "Navigator":
        index = RepoIndex.build(root)
        graph = SymbolGraph.build(index)
        code_map = CodeMap(index=index, graph=graph)
        localizer = IssueLocalizer.build(index, graph, use_git=use_git)
        tracer = DependencyTracer(index=index, graph=graph)
        ranker = EditSiteRanker(localizer=localizer, graph=graph, tracer=tracer)
        return cls(code_map=code_map, localizer=localizer, tracer=tracer, ranker=ranker)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def localize(self, issue: str, *, limit: int = 8) -> list[Localization]:
        return self.localizer.localize(issue, limit=limit)

    def trace_tests(self, source: str, *, limit: int = 5):
        return self.tracer.trace_tests(source, limit=limit)

    def edit_sites(self, issue: str, *, limit: int = 5) -> list[EditSite]:
        return self.ranker.rank(issue, limit=limit)

    def navigate(self, issue: str, *, limit: int = 5) -> NavigationResult:
        localized = self.localizer.localize(issue, limit=max(limit, 8))
        sites = self.ranker.from_localizations(localized[:limit])
        return NavigationResult(
            issue=issue,
            localizations=tuple(localized),
            edit_sites=tuple(sites),
        )

    def repo_map(self) -> str:
        return self.code_map.render()
