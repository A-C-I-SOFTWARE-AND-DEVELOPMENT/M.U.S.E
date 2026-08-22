"""Dependency tracing — find tests and dependents for a source file.

Two questions a navigator must answer before dispatching an edit:

1. *Which tests likely cover this file?* — so the worker runs the right
   verification and the repair loop has a target.
2. *Which files depend on this one?* — so we estimate blast radius.

Both answers combine multiple deterministic signals (naming convention,
mirrored test path, symbol references, import edges) rather than guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from plugins.prime.navigation.repo_index import IndexedFile, RepoIndex
from plugins.prime.navigation.symbol_graph import SymbolGraph


@dataclass(frozen=True)
class TestLink:
    test_path: str
    score: float
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "test_path": self.test_path,
            "score": round(self.score, 4),
            "reasons": list(self.reasons),
        }


@dataclass
class DependencyTracer:
    index: RepoIndex
    graph: SymbolGraph
    _test_token_cache: dict[str, set[str]] = field(default_factory=dict)

    def trace_tests(
        self, source: IndexedFile | str, *, limit: int = 5
    ) -> list[TestLink]:
        path = source.path if isinstance(source, IndexedFile) else source
        src = self.index.get(path)
        stem = Path(path).stem
        symbols = self.graph.file_symbols.get(path, set())
        links: list[TestLink] = []
        for test in self.index.test_files:
            reasons: list[str] = []
            score = 0.0
            test_name = Path(test.path).name.lower()
            test_stem_l = Path(test.path).stem.lower()

            # 1. Naming convention: test_<stem>.py / <stem>_test.* / *.spec.*
            if (
                test_stem_l == f"test_{stem.lower()}"
                or test_stem_l == f"{stem.lower()}_test"
                or test_name.startswith(f"{stem.lower()}.")
                and (".test." in test_name or ".spec." in test_name)
            ):
                score += 3.0
                reasons.append("name-convention")
            elif stem.lower() and stem.lower() in test_stem_l:
                score += 1.0
                reasons.append("name-substring")

            # 2. Mirrored path: tests/<same relative dirs>/...
            if src is not None and _mirrors_path(path, test.path):
                score += 1.5
                reasons.append("mirrored-path")

            # 3. Symbol references: test imports/uses a symbol defined here.
            if symbols:
                tokens = self._tokens(test)
                hit = symbols & tokens
                if hit:
                    score += min(2.0, 0.5 * len(hit))
                    reasons.append(f"symbol-ref:{','.join(sorted(hit)[:3])}")

            # 4. Import edge: test imports this module.
            if src is not None and test.path in self.graph.importers_of(src):
                score += 2.0
                reasons.append("import-edge")

            if score > 0:
                links.append(
                    TestLink(test_path=test.path, score=score, reasons=tuple(reasons))
                )

        links.sort(key=lambda t: (-t.score, t.test_path))
        return links[:limit]

    def dependents(self, source: IndexedFile | str) -> set[str]:
        """Files that import the given source file."""

        return self.graph.importers_of(source)

    def blast_radius(self, source: IndexedFile | str) -> dict[str, object]:
        deps = self.dependents(source)
        tests = self.trace_tests(source)
        return {
            "dependents": sorted(deps),
            "dependent_count": len(deps),
            "tests": [t.to_dict() for t in tests],
        }

    def _tokens(self, f: IndexedFile) -> set[str]:
        if f.path in self._test_token_cache:
            return self._test_token_cache[f.path]
        text = ""
        try:
            text = (self.index.root / f.path).read_text(
                encoding="utf-8", errors="ignore"
            )
        except OSError:
            pass
        toks = set(re.split(r"\W+", text))
        self._test_token_cache[f.path] = toks
        return toks


def _mirrors_path(source_path: str, test_path: str) -> bool:
    """True if the test path mirrors the source dir structure under tests/."""

    src_parts = Path(source_path).with_suffix("").parts
    test_parts = [
        p
        for p in Path(test_path).with_suffix("").parts
        if p.lower() not in {"tests", "test"}
    ]
    if not src_parts or not test_parts:
        return False
    # Compare the meaningful directory components (ignore the file stems).
    src_dirs = [p.lower() for p in src_parts[:-1]]
    test_dirs = [p.lower() for p in test_parts[:-1]]
    if not src_dirs:
        return False
    return all(d in test_dirs for d in src_dirs)
