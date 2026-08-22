"""Issue localizer — rank likely files for a natural-language request.

This is the heart of the navigator. It deliberately does
**not** rely on an LLM to guess file paths. Instead it fuses five cheap,
deterministic signals and exposes the per-signal breakdown so every ranking
is explainable (and auditable after the fact):

1. **lexical** — overlap between issue terms and a file's path + symbols.
2. **path** — explicit file/dir/symbol names quoted in the issue.
3. **symbol** — issue terms that match a defined symbol name.
4. **test** — small boost so test files surface when the issue is about tests.
5. **git** — recency of changes (files touched recently rank slightly higher).

Weights are constants so behaviour is reproducible and unit-testable.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from plugins.prime.navigation.repo_index import IndexedFile, RepoIndex
from plugins.prime.navigation.symbol_graph import SymbolGraph

# Signal weights. Tuned so an explicit path mention dominates, but lexical and
# symbol evidence can still surface the right file without one.
WEIGHTS = {
    "lexical": 1.0,
    "path": 4.0,
    "symbol": 2.5,
    "test": 0.4,
    "git": 0.8,
}

_STOPWORDS = frozenset({
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "when",
    "where",
    "fix",
    "bug",
    "add",
    "make",
    "should",
    "does",
    "doesn",
    "not",
    "use",
    "used",
    "using",
    "code",
    "file",
    "files",
    "function",
    "method",
    "class",
    "test",
    "tests",
    "error",
    "issue",
    "please",
    "need",
    "want",
})


@dataclass(frozen=True)
class Localization:
    path: str
    score: float
    signals: dict[str, float]
    matched_terms: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "score": round(self.score, 4),
            "signals": {k: round(v, 4) for k, v in self.signals.items()},
            "matched_terms": list(self.matched_terms),
        }


@dataclass
class IssueLocalizer:
    index: RepoIndex
    graph: SymbolGraph
    git_recent: dict[str, float] = field(default_factory=dict)

    @classmethod
    def build(
        cls, index: RepoIndex, graph: SymbolGraph, *, use_git: bool = True
    ) -> "IssueLocalizer":
        recent = _git_recency(index.root) if use_git else {}
        return cls(index=index, graph=graph, git_recent=recent)

    def localize(
        self, issue: str, *, limit: int = 8, roles=("source", "test", "config")
    ) -> list[Localization]:
        terms = _terms(issue)
        quoted = _quoted_path_tokens(issue)
        results: list[Localization] = []
        for f in self.index.files:
            if f.role not in roles:
                continue
            signals = self._score_file(f, terms, quoted)
            total = sum(WEIGHTS[name] * value for name, value in signals.items())
            if total <= 0:
                continue
            matched = self._matched_terms(f, terms)
            results.append(
                Localization(
                    path=f.path,
                    score=total,
                    signals=signals,
                    matched_terms=tuple(sorted(matched)),
                )
            )
        results.sort(key=lambda r: (-r.score, r.path))
        return results[:limit]

    # ------------------------------------------------------------------
    def _score_file(
        self, f: IndexedFile, terms: set[str], quoted: set[str]
    ) -> dict[str, float]:
        path_tokens = _path_tokens(f.path)
        symbols = {s.lower() for s in self.graph.file_symbols.get(f.path, set())}

        lexical = len(terms & path_tokens)

        path_signal = 0.0
        name_l = f.name.lower()
        stem_l = f.stem.lower()
        for q in quoted:
            ql = q.lower()
            if ql == name_l or ql == stem_l or ql == f.path.lower():
                path_signal += 2.0
            elif ql in f.path.lower():
                path_signal += 1.0

        symbol_signal = 0.0
        matched_syms = terms & symbols
        symbol_signal += len(matched_syms)
        # Also match camelCase/snake variants quoted explicitly.
        for q in quoted:
            if q.lower() in symbols:
                symbol_signal += 1.0

        test_signal = (
            1.0 if f.role == "test" and ("test" in terms or "tests" in terms) else 0.0
        )

        git_signal = self.git_recent.get(f.path, 0.0)

        return {
            "lexical": float(lexical),
            "path": float(path_signal),
            "symbol": float(symbol_signal),
            "test": float(test_signal),
            "git": float(git_signal),
        }

    def _matched_terms(self, f: IndexedFile, terms: set[str]) -> set[str]:
        path_tokens = _path_tokens(f.path)
        symbols = {s.lower() for s in self.graph.file_symbols.get(f.path, set())}
        return (terms & path_tokens) | (terms & symbols)


def _terms(text: str) -> set[str]:
    raw = re.split(r"\W+", text.lower())
    out: set[str] = set()
    for t in raw:
        if len(t) <= 2 or t in _STOPWORDS:
            continue
        out.add(t)
        # Split snake_case / camelCase compounds into parts too.
    # camelCase split on the original tokens
    for t in re.findall(r"[A-Za-z][a-z]+|[A-Z]+(?![a-z])", text):
        tl = t.lower()
        if len(tl) > 2 and tl not in _STOPWORDS:
            out.add(tl)
    return out


def _path_tokens(path: str) -> set[str]:
    parts = re.split(r"\W+|_", path.lower())
    return {p for p in parts if len(p) > 2}


def _quoted_path_tokens(issue: str) -> set[str]:
    """Pull out things that look like file names / identifiers from the issue."""

    out: set[str] = set()
    # Backtick or quoted spans.
    for m in re.findall(r"[`'\"]([^`'\"]+)[`'\"]", issue):
        out.add(m.strip())
    # Tokens that look like paths or filenames (contain / or a known suffix).
    for m in re.findall(
        r"[\w./-]+\.(?:py|js|ts|tsx|kt|java|go|rs|yaml|yml|toml|md)\b", issue
    ):
        out.add(m)
        out.add(Path(m).name)
    # snake_case or dotted identifiers of length >= 4.
    for m in re.findall(r"\b[a-z][a-z0-9_]{3,}(?:_[a-z0-9]+)+\b", issue):
        out.add(m)
    return {t for t in out if t}


def _git_recency(root: Path) -> dict[str, float]:
    """Map repo-relative path -> recency weight in [0, 1] from recent commits.

    Best-effort: returns ``{}`` if not a git repo or git is unavailable. Most
    recently touched files get the highest weight, decaying linearly.
    """

    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "log",
                "-n",
                "150",
                "--name-only",
                "--pretty=format:",
            ],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if proc.returncode != 0:
        return {}
    seen: dict[str, int] = {}
    order = 0
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if line not in seen:
            seen[line] = order
            order += 1
    if not seen:
        return {}
    total = max(1, len(seen))
    # Earliest-seen (most recent) -> weight near 1.0.
    return {path: 1.0 - (rank / total) for path, rank in seen.items()}
