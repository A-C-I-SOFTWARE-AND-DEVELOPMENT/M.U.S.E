"""TokenJuice — a deterministic context compiler.

Packs task-relevant material (mission, memory tree, research vault, explicit
repo snippets) into an ordered, token-bounded prompt packet. Output is fully
deterministic for a given input so it is testable and reproducible.

Guarantees:

* Honors a hard token budget: sections are dropped whole, never truncated
  mid-source, once the budget is exhausted — the mission section included, so
  a budget smaller than the mission yields no mission section. (``render``
  still echoes the mission in the packet header, where it is not counted; the
  budget governs ``sections`` / ``used_tokens``.)
* Always carries provenance (source URIs) for memory/research material.
* Deprioritizes stale and contested memory.
* Never includes secrets — it relies on the upstream Memory Tree write
  policy and additionally re-screens snippet text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

from plugins.prime.memory_tree import (
    MemoryTreeStore,
    MemoryWritePolicy,
    estimate_tokens,
)


@dataclass(frozen=True)
class ContextSection:
    kind: str  # mission | memory | research | repo
    title: str
    body: str
    sources: tuple[str, ...] = ()
    tokens: int = 0
    priority: int = 0  # higher = packed first

    def render(self) -> str:
        head = f"### [{self.kind}] {self.title}"
        src = (
            "\n  sources: " + ", ".join(s for s in self.sources if s)
            if any(self.sources)
            else ""
        )
        return f"{head}\n{self.body}{src}"

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "title": self.title,
            "body": self.body,
            "sources": list(self.sources),
            "tokens": self.tokens,
            "priority": self.priority,
        }


@dataclass
class CompiledContext:
    mission: str
    token_budget: int
    sections: list[ContextSection] = field(default_factory=list)
    used_tokens: int = 0
    dropped: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            f"# Context — {self.mission}",
            f"# budget: {self.used_tokens}/{self.token_budget} tokens, "
            f"{len(self.sections)} section(s), {len(self.dropped)} dropped",
            "",
        ]
        for sec in self.sections:
            lines.append(sec.render())
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def to_dict(self) -> dict[str, object]:
        return {
            "mission": self.mission,
            "token_budget": self.token_budget,
            "used_tokens": self.used_tokens,
            "dropped": list(self.dropped),
            "sections": [s.to_dict() for s in self.sections],
        }


@dataclass
class TokenJuiceCompiler:
    policy: MemoryWritePolicy = field(default_factory=MemoryWritePolicy)

    def _screen(self, text: str) -> str:
        """Drop any snippet that trips the secret detector."""

        if self.policy.detect_secret(text):
            return "[redacted: secret-like content removed by TokenJuice]"
        return text

    def compile(
        self,
        mission: str,
        token_budget: int,
        *,
        memory_store: Optional[MemoryTreeStore] = None,
        memory_query: Optional[str] = None,
        memory_namespaces: Optional[Iterable[str]] = None,
        research_artifacts: Sequence[object] = (),
        repo_snippets: Sequence[tuple[str, str]] = (),  # (path, text)
        include_contested: bool = False,
    ) -> CompiledContext:
        ctx = CompiledContext(mission=mission, token_budget=token_budget)
        candidates: list[ContextSection] = []

        # 1. Mission — highest priority, so it is packed first whenever it
        #    fits at all.
        candidates.append(
            ContextSection(
                kind="mission",
                title="mission",
                body=mission.strip(),
                tokens=estimate_tokens(mission),
                priority=100,
            )
        )

        # 2. Memory tree — ranked, stale/contested deprioritized by search.
        if memory_store is not None:
            q = memory_query or mission
            hits = memory_store.search(
                q,
                namespaces=memory_namespaces,
                include_contested=include_contested,
                limit=50,
            )
            for rank, hit in enumerate(hits):
                node = hit.node
                body = self._screen(node.summary or node.text)
                srcs = (node.source_uri,) if node.source_uri else ()
                candidates.append(
                    ContextSection(
                        kind="memory",
                        title=f"{node.namespace}: {node.title}",
                        body=body,
                        sources=srcs,
                        tokens=estimate_tokens(body) + estimate_tokens(node.title),
                        priority=70 - rank,  # preserve search ranking
                    )
                )

        # 3. Research artifacts.
        for rank, art in enumerate(research_artifacts):
            title = getattr(art, "title", "research")
            summary = getattr(art, "summary", "") or getattr(art, "excerpt", "")
            uri = getattr(art, "source_uri", "")
            body = self._screen(summary)
            candidates.append(
                ContextSection(
                    kind="research",
                    title=title,
                    body=body,
                    sources=(uri,) if uri else (),
                    tokens=estimate_tokens(body) + estimate_tokens(title),
                    priority=50 - rank,
                )
            )

        # 4. Explicit repo snippets.
        for rank, (path, text) in enumerate(repo_snippets):
            body = self._screen(text)
            candidates.append(
                ContextSection(
                    kind="repo",
                    title=path,
                    body=body,
                    sources=(path,),
                    tokens=estimate_tokens(body),
                    priority=40 - rank,
                )
            )

        # Stable, deterministic ordering: priority desc, then title.
        candidates.sort(key=lambda s: (-s.priority, s.kind, s.title))

        for sec in candidates:
            if ctx.used_tokens + sec.tokens <= token_budget:
                ctx.sections.append(sec)
                ctx.used_tokens += sec.tokens
            else:
                ctx.dropped.append(f"{sec.kind}:{sec.title}")
        return ctx
