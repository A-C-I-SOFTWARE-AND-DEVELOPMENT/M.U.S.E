"""Code map — a human/worker-readable repository overview.

Combines the :class:`RepoIndex` and :class:`SymbolGraph` into a compact map
that a reader can use to orient quickly: files grouped by role, with their key
symbols, kept under a size budget.
"""

from __future__ import annotations

from dataclasses import dataclass

from plugins.prime.navigation.repo_index import RepoIndex
from plugins.prime.navigation.symbol_graph import SymbolGraph


@dataclass
class CodeMap:
    index: RepoIndex
    graph: SymbolGraph

    @classmethod
    def build(cls, root) -> "CodeMap":
        index = RepoIndex.build(root)
        graph = SymbolGraph.build(index)
        return cls(index=index, graph=graph)

    def render(self, *, max_files: int = 60, max_symbols_per_file: int = 8) -> str:
        """Render a compact, deterministic repo map."""

        lines: list[str] = []
        summary = self.index.summary()
        lines.append(f"# Repo map: {summary['root']}")
        by_role = summary["by_role"]
        lines.append(
            "files: " + ", ".join(f"{role}={count}" for role, count in by_role.items())  # ty: ignore[unresolved-attribute]  # by_role is a dict
        )
        lines.append("")

        shown = 0
        for f in self.index.source_files:
            if shown >= max_files:
                lines.append(
                    f"... ({len(self.index.source_files) - shown} more source files)"
                )
                break
            syms = sorted(self.graph.file_symbols.get(f.path, set()))
            if syms:
                head = ", ".join(syms[:max_symbols_per_file])
                if len(syms) > max_symbols_per_file:
                    head += f", +{len(syms) - max_symbols_per_file}"
                lines.append(f"{f.path}: {head}")
            else:
                lines.append(f.path)
            shown += 1
        return "\n".join(lines)

    def to_dict(self) -> dict[str, object]:
        return {
            "summary": self.index.summary(),
            "symbol_count": len(self.graph.symbols),
            "files": [f.to_dict() for f in self.index.files],
        }
