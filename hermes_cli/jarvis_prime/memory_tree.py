"""Minimal Memory Tree for JARVIS Prime.

This clean-room module groups source-backed notes by namespace and topic. It is
small on purpose: no external services, no automatic promotion into durable
recall, and no side effects beyond the caller-provided object.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class MemoryChunk:
    namespace: str
    title: str
    text: str
    source_uri: str = "manual"
    confidence: float = 0.5
    tags: tuple[str, ...] = ()
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def id(self) -> str:
        raw = f"{self.namespace}|{self.title}|{self.source_uri}|{self.text}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "namespace": self.namespace,
            "title": self.title,
            "text": self.text,
            "source_uri": self.source_uri,
            "confidence": self.confidence,
            "tags": list(self.tags),
            "created_at": self.created_at,
        }


@dataclass
class MemoryTree:
    chunks: list[MemoryChunk] = field(default_factory=list)

    def add(
        self,
        text: str,
        *,
        namespace: str,
        title: str,
        source_uri: str = "manual",
        confidence: float = 0.5,
        tags: tuple[str, ...] = (),
    ) -> MemoryChunk | None:
        cleaned = " ".join(text.split())
        if not cleaned:
            return None
        chunk = MemoryChunk(
            namespace=namespace,
            title=title.strip() or "Untitled",
            text=cleaned,
            source_uri=source_uri,
            confidence=max(0.0, min(1.0, confidence)),
            tags=tags,
        )
        self.chunks.append(chunk)
        return chunk

    def search(self, query: str, *, namespace: str | None = None, limit: int = 5) -> list[MemoryChunk]:
        query_terms = _terms(query)
        scored: list[tuple[int, MemoryChunk]] = []
        for chunk in self.chunks:
            if namespace and chunk.namespace != namespace:
                continue
            haystack = _terms(" ".join((chunk.title, chunk.text, " ".join(chunk.tags))))
            score = len(query_terms & haystack)
            if score:
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:limit]]

    def outline(self) -> str:
        grouped: dict[str, list[MemoryChunk]] = {}
        for chunk in self.chunks:
            grouped.setdefault(chunk.namespace, []).append(chunk)
        lines: list[str] = []
        for namespace in sorted(grouped):
            lines.append(f"- {namespace}")
            for chunk in grouped[namespace]:
                lines.append(f"  - {chunk.title} ({chunk.source_uri})")
        return "\n".join(lines)


def _terms(text: str) -> set[str]:
    return {term for term in re.split(r"\W+", text.lower()) if len(term) > 2}
