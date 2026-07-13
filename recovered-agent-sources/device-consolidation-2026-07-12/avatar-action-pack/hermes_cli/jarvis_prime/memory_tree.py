"""Clean-room Memory Tree primitives for JARVIS Prime.

This module is intentionally stdlib-only and does not copy OpenHuman code.
It implements the architecture pattern JARVIS needs: canonical chunks,
hierarchical summaries, provenance, confidence, search, and compact context
export. The durable storage format is simple JSONL so it can be reviewed,
backed up, and migrated later to SQLite without changing the public contract.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(api[_ -]?key|secret|password|token|bearer)\s*[:=]\s*\S+"),
    re.compile(r"(?i)sk-[a-zA-Z0-9_-]{20,}"),
    re.compile(r"(?i)ghp_[a-zA-Z0-9]{20,}"),
    re.compile(r"(?i)xox[a-z]-[a-zA-Z0-9-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|DSA|PGP|ENCRYPTED) PRIVATE KEY-----"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
)


@dataclass(frozen=True)
class MemoryChunk:
    """A canonical, bounded, source-backed memory unit."""

    id: str
    namespace: str
    title: str
    text: str
    source_uri: str
    trust_tier: str = "unverified"
    confidence: float = 0.5
    token_estimate: int = 0
    created_at: str = field(default_factory=lambda: _now())
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "chunk",
            "id": self.id,
            "namespace": self.namespace,
            "title": self.title,
            "text": self.text,
            "source_uri": self.source_uri,
            "trust_tier": self.trust_tier,
            "confidence": self.confidence,
            "token_estimate": self.token_estimate,
            "created_at": self.created_at,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "MemoryChunk":
        return cls(
            id=str(data.get("id", "")),
            namespace=str(data.get("namespace", "general")),
            title=str(data.get("title", "Untitled")),
            text=str(data.get("text", "")),
            source_uri=str(data.get("source_uri", "manual")),
            trust_tier=str(data.get("trust_tier", "unverified")),
            confidence=float(data.get("confidence", 0.5)),
            token_estimate=int(data.get("token_estimate", 0)),
            created_at=str(data.get("created_at") or _now()),
            tags=tuple(data.get("tags") or ()),
        )


@dataclass
class MemoryTreeNode:
    """A hierarchical summary node over one or more chunks."""

    id: str
    namespace: str
    title: str
    summary: str
    parent_id: Optional[str] = None
    children: list[str] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)
    confidence: float = 0.5
    updated_at: str = field(default_factory=lambda: _now())

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "node",
            "id": self.id,
            "namespace": self.namespace,
            "title": self.title,
            "summary": self.summary,
            "parent_id": self.parent_id,
            "children": list(self.children),
            "chunk_ids": list(self.chunk_ids),
            "confidence": self.confidence,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "MemoryTreeNode":
        parent = data.get("parent_id")
        return cls(
            id=str(data.get("id", "")),
            namespace=str(data.get("namespace", "general")),
            title=str(data.get("title", "Untitled")),
            summary=str(data.get("summary", "")),
            parent_id=str(parent) if parent else None,
            children=list(data.get("children") or []),
            chunk_ids=list(data.get("chunk_ids") or []),
            confidence=float(data.get("confidence", 0.5)),
            updated_at=str(data.get("updated_at") or _now()),
        )


@dataclass
class MemoryTreeStore:
    """Reviewable Memory Tree store with JSONL persistence."""

    journal_path: Path = field(
        default_factory=lambda: Path(
            os.path.expanduser("~/.hermes/jarvis_prime/memory_tree.jsonl")
        )
    )
    chunks: dict[str, MemoryChunk] = field(default_factory=dict)
    nodes: dict[str, MemoryTreeNode] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._load()

    def ingest_text(
        self,
        text: str,
        *,
        namespace: str,
        title: str,
        source_uri: str = "manual",
        trust_tier: str = "user-approved",
        confidence: float = 0.8,
        tags: Iterable[str] = (),
        max_tokens: int = 3000,
    ) -> Optional[MemoryChunk]:
        """Canonicalize and store text as a bounded, source-backed chunk."""

        cleaned = _normalize_text(text)
        if not cleaned or _contains_secret(cleaned):
            return None
        bounded = _truncate_to_token_estimate(cleaned, max_tokens=max_tokens)
        chunk = MemoryChunk(
            id=_stable_id(namespace, title, source_uri, bounded),
            namespace=namespace,
            title=title.strip()[:120] or "Untitled",
            text=bounded,
            source_uri=source_uri,
            trust_tier=trust_tier,
            confidence=max(0.0, min(1.0, confidence)),
            token_estimate=estimate_tokens(bounded),
            tags=tuple(tags),
        )
        self.chunks[chunk.id] = chunk
        self._fold_chunk(chunk)
        self._persist()
        return chunk

    def search(self, query: str, *, namespace: Optional[str] = None, limit: int = 8) -> list[MemoryChunk]:
        """Return chunks ranked by term overlap, trust, confidence, and freshness proxy."""

        q_terms = _tokenize(query)
        if not q_terms:
            return []
        scored: list[tuple[float, MemoryChunk]] = []
        for chunk in self.chunks.values():
            if namespace and chunk.namespace != namespace:
                continue
            c_terms = _tokenize(" ".join((chunk.title, chunk.text, " ".join(chunk.tags))))
            overlap = len(q_terms & c_terms)
            if overlap == 0:
                continue
            trust = {"source-of-truth": 1.4, "user-approved": 1.25, "official": 1.2}.get(
                chunk.trust_tier, 1.0
            )
            density = overlap / max(1, len(q_terms))
            score = density * trust * (0.4 + chunk.confidence)
            scored.append((score, chunk))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [chunk for _, chunk in scored[:limit]]

    def context_pack(
        self,
        query: str,
        *,
        namespace: Optional[str] = None,
        token_budget: int = 1800,
    ) -> str:
        """Compile a compact context block for LLM/tool handoff."""

        lines: list[str] = []
        used = 0
        for chunk in self.search(query, namespace=namespace, limit=12):
            header = f"- [{chunk.namespace}] {chunk.title} ({chunk.trust_tier}, conf={chunk.confidence:.2f})"
            body = _truncate_to_token_estimate(chunk.text, max_tokens=max(80, token_budget - used))
            item = f"{header}\n  Source: {chunk.source_uri}\n  {body}"
            item_tokens = estimate_tokens(item)
            if used + item_tokens > token_budget and lines:
                break
            lines.append(item)
            used += item_tokens
        return "\n".join(lines)

    def outline(self, namespace: Optional[str] = None) -> str:
        """Render the current Memory Tree as a human-reviewable outline."""

        roots = [n for n in self.nodes.values() if n.parent_id is None]
        if namespace:
            roots = [n for n in roots if n.namespace == namespace]
        roots.sort(key=lambda n: (n.namespace, n.title))
        lines: list[str] = []
        for root in roots:
            self._render_node(root, lines, level=0)
        return "\n".join(lines)

    def _render_node(self, node: MemoryTreeNode, lines: list[str], level: int) -> None:
        prefix = "  " * level
        lines.append(f"{prefix}- {node.title} [{node.namespace}] conf={node.confidence:.2f}")
        if node.summary:
            lines.append(f"{prefix}  {node.summary[:240]}")
        for child_id in sorted(node.children):
            child = self.nodes.get(child_id)
            if child is not None:
                self._render_node(child, lines, level + 1)

    def _fold_chunk(self, chunk: MemoryChunk) -> None:
        root_id = _stable_id("root", chunk.namespace)
        root = self.nodes.get(root_id)
        if root is None:
            root = MemoryTreeNode(
                id=root_id,
                namespace=chunk.namespace,
                title=chunk.namespace,
                summary=f"Root memory namespace for {chunk.namespace}.",
                confidence=chunk.confidence,
            )
            self.nodes[root.id] = root

        topic = _topic_for(chunk)
        topic_id = _stable_id("topic", chunk.namespace, topic)
        node = self.nodes.get(topic_id)
        if node is None:
            node = MemoryTreeNode(
                id=topic_id,
                namespace=chunk.namespace,
                title=topic,
                summary=_summary_sentence(chunk.text),
                parent_id=root.id,
                confidence=chunk.confidence,
            )
            self.nodes[node.id] = node
            if node.id not in root.children:
                root.children.append(node.id)
        if chunk.id not in node.chunk_ids:
            node.chunk_ids.append(chunk.id)
        node.summary = _merge_summaries(node.summary, _summary_sentence(chunk.text))
        node.confidence = max(node.confidence, chunk.confidence)
        node.updated_at = _now()

    def _load(self) -> None:
        if not self.journal_path.is_file():
            return
        try:
            for line in self.journal_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                data = json.loads(line)
                if data.get("kind") == "chunk":
                    chunk = MemoryChunk.from_dict(data)
                    self.chunks[chunk.id] = chunk
                elif data.get("kind") == "node":
                    node = MemoryTreeNode.from_dict(data)
                    self.nodes[node.id] = node
        except Exception:
            self.chunks = {}
            self.nodes = {}

    def _persist(self) -> None:
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.journal_path.with_suffix(self.journal_path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for node in self.nodes.values():
                fh.write(json.dumps(node.to_dict(), ensure_ascii=False) + "\n")
            for chunk in self.chunks.values():
                fh.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")
        os.replace(tmp, self.journal_path)
        try:
            os.chmod(self.journal_path, 0o600)
        except OSError:
            pass


def estimate_tokens(text: str) -> int:
    """Cheap token estimate used only for budgeting."""

    if not text:
        return 0
    words = len(re.findall(r"\S+", text))
    chars = len(text)
    return max(1, int(max(words * 1.35, chars / 4.0)))


def _normalize_text(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.strip())


def _truncate_to_token_estimate(text: str, *, max_tokens: int) -> str:
    if estimate_tokens(text) <= max_tokens:
        return text
    words = re.findall(r"\S+", text)
    kept: list[str] = []
    for word in words:
        candidate = " ".join(kept + [word])
        if estimate_tokens(candidate) > max_tokens:
            break
        kept.append(word)
    return " ".join(kept).rstrip() + " …"


def _contains_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def _stable_id(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _tokenize(text: str) -> set[str]:
    return {term for term in re.split(r"\W+", text.lower()) if len(term) > 2}


def _topic_for(chunk: MemoryChunk) -> str:
    tags = [t for t in chunk.tags if t]
    if tags:
        return tags[0][:80]
    title_words = re.findall(r"[A-Za-z0-9]+", chunk.title)
    return " ".join(title_words[:5]) or "General"


def _summary_sentence(text: str) -> str:
    first = re.split(r"(?<=[.!?])\s+", text.strip())[0]
    return first[:320] if first else "No summary available."


def _merge_summaries(current: str, incoming: str) -> str:
    if not current:
        return incoming
    if incoming in current:
        return current
    return f"{current} {incoming}"[:700]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
