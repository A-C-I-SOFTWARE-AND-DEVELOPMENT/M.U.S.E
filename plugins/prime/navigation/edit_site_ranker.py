"""Edit-site ranker — turn localized files into worker-ready edit packets.

Given a ranked set of candidate files (from :class:`IssueLocalizer`), produce
*edit-site packets* that can be acted on without re-deriving context:

- the target file,
- the symbols/regions most likely to need changes,
- the tests that should be run to verify,
- a plain-language rationale (the signals that put it on the list),
- the blast radius (dependents) so the worker knows what it might break.

No edits are performed here — this only *plans* where edits should go.
"""

from __future__ import annotations

from dataclasses import dataclass

from plugins.prime.navigation.dependency_trace import DependencyTracer
from plugins.prime.navigation.issue_localizer import (
    IssueLocalizer,
    Localization,
)
from plugins.prime.navigation.symbol_graph import SymbolGraph


@dataclass(frozen=True)
class EditSite:
    path: str
    rank: int
    confidence: float  # normalized 0..1 within this result set
    symbols: tuple[str, ...]
    suggested_tests: tuple[str, ...]
    dependents: tuple[str, ...]
    rationale: str
    signals: dict[str, float]

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "rank": self.rank,
            "confidence": round(self.confidence, 4),
            "symbols": list(self.symbols),
            "suggested_tests": list(self.suggested_tests),
            "dependents": list(self.dependents),
            "rationale": self.rationale,
            "signals": {k: round(v, 4) for k, v in self.signals.items()},
        }


@dataclass
class EditSiteRanker:
    localizer: IssueLocalizer
    graph: SymbolGraph
    tracer: DependencyTracer

    def from_localizations(
        self, localized: list[Localization], *, max_dependents: int = 8
    ) -> list[EditSite]:
        return self._to_sites(localized, max_dependents=max_dependents)

    def _to_sites(
        self, localized: list[Localization], *, max_dependents: int
    ) -> list[EditSite]:
        if not localized:
            return []
        top = localized[0].score or 1.0
        sites: list[EditSite] = []
        for rank, loc in enumerate(localized, start=1):
            indexed = self.localizer.index.get(loc.path)
            symbols = sorted(self.graph.file_symbols.get(loc.path, set()))
            tests = (
                [t.test_path for t in self.tracer.trace_tests(indexed)]
                if indexed is not None
                else []
            )
            deps = (
                sorted(self.tracer.dependents(loc.path))[:max_dependents]
                if indexed
                else []
            )
            confidence = max(0.0, min(1.0, loc.score / top))
            sites.append(
                EditSite(
                    path=loc.path,
                    rank=rank,
                    confidence=confidence,
                    symbols=tuple(symbols[:12]),
                    suggested_tests=tuple(tests),
                    dependents=tuple(deps),
                    rationale=_rationale(loc),
                    signals=loc.signals,
                )
            )
        return sites


def _rationale(loc: Localization) -> str:
    active = [
        name
        for name, value in sorted(loc.signals.items(), key=lambda kv: -kv[1])
        if value > 0
    ]
    pieces: list[str] = []
    if "path" in active:
        pieces.append("path explicitly referenced")
    if "symbol" in active:
        pieces.append("defines a matching symbol")
    if "lexical" in active:
        terms = ", ".join(loc.matched_terms[:4])
        pieces.append(f"lexical match ({terms})" if terms else "lexical match")
    if "git" in active:
        pieces.append("recently changed")
    if "test" in active:
        pieces.append("test file relevant to request")
    return "; ".join(pieces) or "weak lexical signal only"
