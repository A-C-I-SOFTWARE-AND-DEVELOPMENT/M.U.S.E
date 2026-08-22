"""Navigator — the public entry point for repo navigation.

Wires the index, symbol graph, localizer, tracer, and edit-site ranker into a
single object a caller (``hermes navigate``, or any driver) uses *before*
editing. It answers three questions and packages them so the ranking is
auditable and the caller gets a focused packet instead of the whole repo.

Typical flow::

    nav = Navigator.for_repo(".")
    result = nav.navigate("fix the timeout in the issue localizer")
    packet = result.worker_packet()        # hand to whatever makes the edit

Nothing here mutates the repo or writes any record; callers own persistence.
This keeps the navigator pure and unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from plugins.prime.navigation.code_map import CodeMap
from plugins.prime.navigation.dependency_trace import DependencyTracer
from plugins.prime.navigation.edit_site_ranker import EditSiteRanker
from plugins.prime.navigation.issue_localizer import (
    IssueLocalizer,
    Localization,
)
from plugins.prime.navigation.repo_index import RepoIndex
from plugins.prime.navigation.symbol_graph import SymbolGraph


@dataclass(frozen=True)
class NavigationResult:
    issue: str
    localizations: tuple[Localization, ...]
    edit_sites: tuple[EditSite, ...]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def worker_packet(self, *, max_sites: int = 5) -> dict[str, object]:
        """A compact, worker-agnostic edit packet.

        Lists candidate files in priority order with the tests to run and the
        dependents to watch — what an edit → patch → test loop needs.
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

    def navigate(self, issue: str, *, limit: int = 5) -> NavigationResult:
        localized = self.localizer.localize(issue, limit=max(limit, 8))
        sites = self.ranker.from_localizations(localized[:limit])
        return NavigationResult(
            issue=issue,
            localizations=tuple(localized),
            edit_sites=tuple(sites),
        )
