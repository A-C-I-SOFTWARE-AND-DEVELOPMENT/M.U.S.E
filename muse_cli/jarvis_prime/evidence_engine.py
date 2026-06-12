"""JARVIS Evidence Engine — hybrid retrieval, source ranking, citation verify.

This module composes the **existing** primitives into a source-grounded
research engine. It introduces no new store:

* Evidence lives in :class:`research_vault.ResearchVault`.
* Durable facts live in :class:`memory_tree.MemoryTreeStore` (the only
  promotion target).
* Trust ordering reuses :class:`memory_tree.SourceTrust` weights.
* The hallucination read reuses :func:`epistemics.audit_response`.
* Secret / chain-of-thought rejection reuses
  :class:`memory_tree.MemoryWritePolicy`.

Retrieval is **hybrid** and stdlib-only: a BM25-style keyword rank over the
vault, a Memory-Tree search blend, and an optional bounded repo-symbol grep.
A vector/embedding lane is supported behind the :class:`EmbeddingBackend`
hook but is **never** imported at module load and requires an optional extra
to do anything — :class:`NullEmbeddingBackend` is the default.

No network calls. Deterministic for a given input so it is testable.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Protocol, Sequence

from muse_cli.jarvis_prime import epistemics
from muse_cli.jarvis_prime.memory_tree import (
    ApprovalState,
    MemoryLayer,
    MemorySource,
    MemoryTreeStore,
    MemoryWritePolicy,
    MemoryWriteResult,
    SourceTrust,
    canonicalize_text,
)
from muse_cli.jarvis_prime.research_vault import ResearchArtifact, ResearchVault

_STOPWORDS = frozenset(
    "the a an and or of to in is are was were be been for on at by with as it "
    "this that these those from into over under not no".split()
)

_NEGATION = ("not", "no", "never", "cannot", "can't", "isn't", "aren't", "doesn't", "won't", "without")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens > 1 char, stopwords removed. Deterministic."""

    raw = re.split(r"\W+", (text or "").lower())
    return [t for t in raw if len(t) > 1 and t not in _STOPWORDS]


def _subject_key(title: str) -> str:
    return " ".join(sorted(set(tokenize(title))))


def _has_negation(text: str) -> bool:
    """Negation check on raw words (``not``/``no`` are stopwords for tokenize)."""

    words = re.split(r"\W+", (text or "").lower())
    return any(n in words for n in _NEGATION)


# ---------------------------------------------------------------------------
# Embedding hook (optional; off by default)
# ---------------------------------------------------------------------------


class EmbeddingBackend(Protocol):
    """Optional dense-retrieval backend. Implementations live behind an extra."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class NullEmbeddingBackend:
    """Default no-op backend — keeps the engine stdlib-only / Termux-safe."""

    available = False

    def embed(self, texts: Sequence[str]) -> list[list[float]]:  # pragma: no cover - trivial
        return [[] for _ in texts]


# ---------------------------------------------------------------------------
# Hits
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceHit:
    """A ranked retrieval result carrying its source + trust."""

    kind: str  # "vault" | "memory" | "repo"
    title: str
    uri: str
    excerpt: str
    trust: SourceTrust
    score: float
    artifact_id: Optional[str] = None
    citation_anchors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "title": self.title,
            "uri": self.uri,
            "excerpt": self.excerpt,
            "trust": self.trust.value,
            "score": round(self.score, 4),
            "artifact_id": self.artifact_id,
            "citation_anchors": list(self.citation_anchors),
        }


# ---------------------------------------------------------------------------
# BM25-style keyword scoring
# ---------------------------------------------------------------------------


def _bm25_scores(
    query_terms: Sequence[str],
    docs: Sequence[Sequence[str]],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    """Classic Okapi BM25 over a small in-memory corpus. Deterministic."""

    n = len(docs)
    if n == 0:
        return []
    doc_len = [len(d) for d in docs]
    avgdl = (sum(doc_len) / n) if n else 0.0
    # Document frequency per term.
    df: dict[str, int] = {}
    doc_sets = [set(d) for d in docs]
    for term in set(query_terms):
        df[term] = sum(1 for s in doc_sets if term in s)

    scores = [0.0] * n
    for i, doc in enumerate(docs):
        if not doc:
            continue
        counts: dict[str, int] = {}
        for tok in doc:
            counts[tok] = counts.get(tok, 0) + 1
        dl = doc_len[i] or 1
        score = 0.0
        for term in query_terms:
            f = counts.get(term, 0)
            if f == 0:
                continue
            n_q = df.get(term, 0)
            # +1 smoothing keeps idf non-negative for tiny corpora.
            idf = math.log(1 + (n - n_q + 0.5) / (n_q + 0.5))
            denom = f + k1 * (1 - b + b * dl / (avgdl or 1))
            score += idf * (f * (k1 + 1)) / (denom or 1)
        scores[i] = score
    return scores


# ---------------------------------------------------------------------------
# Repo-symbol search (bounded, optional)
# ---------------------------------------------------------------------------

_REPO_EXTS = (".py", ".kt", ".md", ".ts", ".js", ".java", ".toml", ".yaml", ".yml")


def repo_symbol_hits(
    query: str,
    repo_root: Path,
    *,
    limit: int = 5,
    max_files: int = 2000,
) -> list[EvidenceHit]:
    """Bounded keyword grep over repo source files. Stdlib-only, no shelling out.

    Returns repo lines as COMMUNITY-trust hits (local code is corroborating
    evidence, not an authority). Skips VCS/build dirs and large/binary files.
    """

    terms = tokenize(query)
    if not terms or not repo_root.is_dir():
        return []
    skip_dirs = {".git", "node_modules", "build", ".gradle", "__pycache__", ".venv", "venv", "dist"}
    hits: list[EvidenceHit] = []
    scanned = 0
    for path in sorted(repo_root.rglob("*")):
        if scanned >= max_files:
            break
        if not path.is_file() or path.suffix not in _REPO_EXTS:
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            low = line.lower()
            overlap = sum(1 for t in terms if t in low)
            if overlap == 0:
                continue
            rel = path.relative_to(repo_root).as_posix()
            hits.append(
                EvidenceHit(
                    kind="repo",
                    title=rel,
                    uri=rel,
                    excerpt=line.strip()[:280],
                    trust=SourceTrust.COMMUNITY,
                    score=float(overlap),
                    citation_anchors=(f"{rel}:{lineno}",),
                )
            )
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]


# ---------------------------------------------------------------------------
# Hybrid retrieval + ranking
# ---------------------------------------------------------------------------


def _artifact_hit(art: ResearchArtifact, score: float) -> EvidenceHit:
    return EvidenceHit(
        kind="vault",
        title=art.title,
        uri=art.source_uri,
        excerpt=art.excerpt or art.summary,
        trust=art.evidence_strength.trust,
        score=score,
        artifact_id=art.id,
        citation_anchors=art.citation_anchors,
    )


def retrieve(
    query: str,
    *,
    vault: ResearchVault,
    memory_store: Optional[MemoryTreeStore] = None,
    repo_root: Optional[Path] = None,
    limit: int = 10,
    embedding: Optional[EmbeddingBackend] = None,
) -> list[EvidenceHit]:
    """Hybrid retrieval across vault (BM25) + memory + optional repo grep.

    Results are ranked by :func:`rank_sources` (trust first, then relevance).
    ``embedding`` is accepted for forward compatibility; the default
    :class:`NullEmbeddingBackend` contributes nothing.
    """

    q_terms = tokenize(query)
    hits: list[EvidenceHit] = []

    # 1. Vault — BM25 over title+summary+excerpt+tags.
    arts = list(vault.artifacts.values())
    if arts and q_terms:
        docs = [
            tokenize(f"{a.title} {a.summary} {a.excerpt} {' '.join(a.tags)}") for a in arts
        ]
        scores = _bm25_scores(q_terms, docs)
        for art, sc in zip(arts, scores):
            if sc > 0:
                hits.append(_artifact_hit(art, sc))

    # 2. Memory Tree — reuse its own ranked search (active, non-contested).
    if memory_store is not None:
        for res in memory_store.search(query, limit=limit):
            node = res.node
            uri = (node.source_uri or "") or (node.sources[0].uri if node.sources else "")
            hits.append(
                EvidenceHit(
                    kind="memory",
                    title=node.title,
                    uri=uri,
                    excerpt=node.summary or node.text,
                    trust=node.source_trust,
                    score=res.score,
                    citation_anchors=tuple(
                        s.line_ref for s in node.sources if s.line_ref
                    ),
                )
            )

    # 3. Repo symbols — corroborating local code (optional, bounded).
    if repo_root is not None:
        hits.extend(repo_symbol_hits(query, repo_root, limit=limit))

    return rank_sources(hits)[:limit]


def rank_sources(hits: Iterable[EvidenceHit]) -> list[EvidenceHit]:
    """Order hits by source trust (owner > primary > … > unverified) then score."""

    return sorted(hits, key=lambda h: (h.trust.weight, h.score), reverse=True)


# ---------------------------------------------------------------------------
# Citation verifier
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClaimCitation:
    claim: str
    supported: bool
    hits: tuple[EvidenceHit, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "claim": self.claim,
            "supported": self.supported,
            "hits": [h.to_dict() for h in self.hits],
        }


@dataclass(frozen=True)
class Contradiction:
    subject: str
    a: str
    b: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {"subject": self.subject, "a": self.a, "b": self.b, "reason": self.reason}


@dataclass
class VerificationResult:
    citations: list[ClaimCitation] = field(default_factory=list)
    uncertain: list[str] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)  # secret/CoT claims dropped
    audit: Optional[dict] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "citations": [c.to_dict() for c in self.citations],
            "uncertain": list(self.uncertain),
            "contradictions": [c.to_dict() for c in self.contradictions],
            "rejected": list(self.rejected),
            "audit": self.audit,
        }


class CitationVerifier:
    """Maps factual claims to evidence; flags unsupported claims + contradictions."""

    def __init__(self, policy: Optional[MemoryWritePolicy] = None, *, min_overlap: int = 1):
        self.policy = policy or MemoryWritePolicy()
        self.min_overlap = min_overlap

    def _supporting(self, claim: str, hits: Sequence[EvidenceHit]) -> list[EvidenceHit]:
        c_terms = set(tokenize(claim))
        if not c_terms:
            return []
        matched: list[tuple[int, EvidenceHit]] = []
        for h in hits:
            overlap = len(c_terms & set(tokenize(f"{h.title} {h.excerpt}")))
            if overlap >= self.min_overlap:
                matched.append((overlap, h))
        matched.sort(key=lambda x: (x[0], x[1].trust.weight), reverse=True)
        return [h for _, h in matched]

    def verify(
        self,
        claims: Sequence[str],
        hits: Sequence[EvidenceHit],
        *,
        memory_store: Optional[MemoryTreeStore] = None,
        confidence: float = 1.0,
    ) -> VerificationResult:
        result = VerificationResult()
        for claim in claims:
            claim = (claim or "").strip()
            if not claim:
                continue
            # Never let secrets / chain-of-thought become "evidence".
            if self.policy.detect_secret(claim) or self.policy.detect_chain_of_thought(claim):
                result.rejected.append(claim)
                continue
            supporting = self._supporting(claim, hits)
            if supporting:
                result.citations.append(
                    ClaimCitation(claim=claim, supported=True, hits=tuple(supporting[:5]))
                )
            else:
                result.citations.append(ClaimCitation(claim=claim, supported=False))
                result.uncertain.append(claim)

        result.contradictions = detect_contradictions(hits, memory_store=memory_store)

        # Overall hallucination read over the joined claims, citing the hit uris.
        joined = "\n".join(c for c in claims if c)
        if joined:
            report = epistemics.audit_response(
                joined,
                provided_citations=[h.uri for h in hits if h.uri],
                confidence=confidence,
            )
            result.audit = report.to_dict()
        return result


def detect_contradictions(
    hits: Sequence[EvidenceHit],
    *,
    memory_store: Optional[MemoryTreeStore] = None,
) -> list[Contradiction]:
    """Surface conflicts among hits and any open Memory-Tree contradictions."""

    out: list[Contradiction] = []

    # 1. Real, already-recorded Memory-Tree contradictions (reuse existing logic).
    if memory_store is not None:
        for rep in memory_store.open_contradictions():
            out.append(
                Contradiction(
                    subject=rep.subject,
                    a=rep.node_a_id,
                    b=rep.node_b_id,
                    reason=rep.reason,
                )
            )

    # 2. Heuristic over hits: same subject, one side negates the other.
    by_subject: dict[str, list[EvidenceHit]] = {}
    for h in hits:
        by_subject.setdefault(_subject_key(h.title), []).append(h)
    for subject, group in by_subject.items():
        if not subject or len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if canonicalize_text(a.excerpt) == canonicalize_text(b.excerpt):
                    continue
                if _has_negation(a.excerpt) != _has_negation(b.excerpt):
                    out.append(
                        Contradiction(
                            subject=subject,
                            a=a.uri or a.title,
                            b=b.uri or b.title,
                            reason="conflicting statements on the same subject",
                        )
                    )
    return out


# ---------------------------------------------------------------------------
# Promotion to durable memory (the ONLY write path; gates preserved)
# ---------------------------------------------------------------------------


def promote_to_memory(
    artifact: ResearchArtifact,
    store: MemoryTreeStore,
    *,
    namespace: str = "jarvis/research",
    confidence: Optional[float] = None,
    owner_approved: bool = False,
    persist: bool = True,
) -> MemoryWriteResult:
    """Promote an evidence artifact into the durable Memory Tree.

    Routes through :meth:`MemoryTreeStore.write` so **every** existing
    guarantee holds: secrets / chain-of-thought are rejected, durable writes
    require provenance, and low-confidence durable writes need owner approval.
    Rejection is returned honestly in the :class:`MemoryWriteResult` — it is
    never bypassed. This is the rule "unverified data does not become durable
    memory automatically".
    """

    src = artifact.as_memory_source()
    # Trust → confidence floor unless the caller is explicit.
    conf = confidence if confidence is not None else artifact.evidence_strength.trust.weight
    return store.write(
        text=artifact.excerpt or artifact.summary,
        namespace=namespace,
        title=artifact.title,
        layer=MemoryLayer.DURABLE,
        summary=artifact.summary,
        sources=(src,),
        source_uri=artifact.source_uri,
        source_trust=artifact.evidence_strength.trust,
        confidence=conf,
        approval_state=(
            ApprovalState.OWNER_APPROVED if owner_approved else ApprovalState.PROPOSED
        ),
        freshness_due=artifact.freshness_due,
        tags=artifact.tags,
        owner_approved=owner_approved,
        persist=persist,
    )
