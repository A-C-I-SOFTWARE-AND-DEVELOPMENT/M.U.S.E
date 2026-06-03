"""JARVIS Research Mode — the Evidence Engine.

Orchestrates the eight-step research pipeline the mobile cockpit drives:

1. **Decompose** the query into sub-questions (reuses
   :mod:`hermes_cli.jarvis_prime.research`'s ``ResearchBrief``).
2. **Gather** sources from the active web-search provider
   (:func:`agent.web_search_registry.get_active_search_provider`) and/or
   user-pasted ``manual_sources``. When no provider is configured *and* no
   manual sources are supplied, the engine returns an honest "no sources"
   result — it never fabricates.
3. **Rank** raw sources into :class:`~hermes_cli.jarvis_prime.research_vault.EvidenceStrength`
   tiers via deterministic domain heuristics.
4. **Cards** — each ranked source is stored in the existing
   :class:`~hermes_cli.jarvis_prime.research_vault.ResearchVault` (excerpt-only
   summaries, atomic JSONL) and wrapped as an :class:`EvidenceCard`.
5. **Synthesize** claims per sub-question from the card excerpts.
6. **Verify citations** — drop any claim whose cited card excerpt does not
   actually support it (no orphan citations).
7. **Contradictions** — pairwise disagreement between cards on the same
   subject becomes a :class:`ResearchContradiction`.
8. **Final answer** with calibrated uncertainty via
   :func:`hermes_cli.jarvis_prime.epistemics.audit_response`.

The engine *composes* existing primitives; it does not introduce a second
evidence store, memory store, or web client. Promotion to the Memory Tree and
coding-task creation are performed by the cockpit handlers through the existing
gated write paths — this module only prepares the payload
(:meth:`ResearchEngine.promotion_payload`).

Stdlib-only, local JSONL persistence with atomic writes (mirrors
``research_vault``). No network calls happen at import time.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Sequence
from urllib.parse import urlsplit

from hermes_cli.jarvis_prime.epistemics import audit_response
from hermes_cli.jarvis_prime.research import (
    ResearchBrief,
    ResearchQuestion,
    ResearchScope,
    open_brief,
)
from hermes_cli.jarvis_prime.research_vault import (
    EvidenceStrength,
    ResearchVault,
    SourceType,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _terms(text: str) -> set[str]:
    return {
        t
        for t in "".join(c.lower() if c.isalnum() else " " for c in text).split()
        if len(t) > 2
    }


# ---------------------------------------------------------------------------
# Source trust ranking — deterministic domain heuristics
# ---------------------------------------------------------------------------

# (host substring, SourceType, EvidenceStrength). First match wins; order
# matters (most specific first). Tuned to be conservative — unknown hosts land
# at WEAK so the synthesis step never over-trusts an anonymous blog.
_DOMAIN_RULES: tuple[tuple[str, SourceType, EvidenceStrength], ...] = (
    ("arxiv.org", SourceType.PAPER, EvidenceStrength.PRIMARY),
    ("doi.org", SourceType.PAPER, EvidenceStrength.PRIMARY),
    ("ncbi.nlm.nih.gov", SourceType.PAPER, EvidenceStrength.PRIMARY),
    ("pubmed", SourceType.PAPER, EvidenceStrength.PRIMARY),
    ("docs.python.org", SourceType.OFFICIAL_DOC, EvidenceStrength.PRIMARY),
    ("developer.mozilla.org", SourceType.OFFICIAL_DOC, EvidenceStrength.PRIMARY),
    ("kubernetes.io", SourceType.OFFICIAL_DOC, EvidenceStrength.PRIMARY),
    ("pkg.go.dev", SourceType.OFFICIAL_DOC, EvidenceStrength.PRIMARY),
    ("docs.", SourceType.OFFICIAL_DOC, EvidenceStrength.PRIMARY),
    (".gov", SourceType.OFFICIAL_DOC, EvidenceStrength.PRIMARY),
    ("github.com", SourceType.REPO, EvidenceStrength.STRONG),
    ("gitlab.com", SourceType.REPO, EvidenceStrength.STRONG),
    ("stackoverflow.com", SourceType.BLOG, EvidenceStrength.MODERATE),
    ("wikipedia.org", SourceType.BLOG, EvidenceStrength.MODERATE),
    ("medium.com", SourceType.BLOG, EvidenceStrength.WEAK),
    ("substack.com", SourceType.BLOG, EvidenceStrength.WEAK),
)


def classify_source(url: str) -> tuple[SourceType, EvidenceStrength]:
    """Map a URL to a (SourceType, EvidenceStrength) pair, deterministically.

    Unknown hosts default to ``BLOG`` / ``WEAK`` — conservative on purpose so
    an anonymous source is never silently trusted as primary.
    """
    host = (urlsplit(url).netloc or url).lower()
    path = urlsplit(url).path.lower()
    hay = host + path
    for needle, stype, strength in _DOMAIN_RULES:
        if needle in hay:
            return stype, strength
    return SourceType.BLOG, EvidenceStrength.WEAK


# ---------------------------------------------------------------------------
# Data shapes (all JSON-serializable for the cockpit contract)
# ---------------------------------------------------------------------------


@dataclass
class RawSource:
    """A pre-ranking source — from a provider hit or a user-pasted entry."""

    title: str
    url: str
    excerpt: str = ""
    provider: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "RawSource":
        return cls(
            title=str(d.get("title") or d.get("url") or "").strip(),
            url=str(d.get("url") or d.get("source_uri") or "").strip(),
            excerpt=str(
                d.get("excerpt") or d.get("content") or d.get("snippet") or ""
            ).strip(),
            provider=str(d.get("provider") or "manual").strip(),
        )


@dataclass
class EvidenceCard:
    """A ranked, stored source with the claim extracted from its excerpt."""

    id: str
    title: str
    source_uri: str
    source_type: str
    evidence_strength: str
    excerpt: str
    claim: str
    relevance: float = 0.0
    sub_question: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "source_uri": self.source_uri,
            "source_type": self.source_type,
            "evidence_strength": self.evidence_strength,
            "excerpt": self.excerpt,
            "claim": self.claim,
            "relevance": round(self.relevance, 4),
            "sub_question": self.sub_question,
        }


@dataclass
class SynthesizedClaim:
    text: str
    supporting_card_ids: tuple[str, ...] = ()
    confidence: float = 0.0
    uncertainty: str = ""
    sub_question: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "supporting_card_ids": list(self.supporting_card_ids),
            "confidence": round(self.confidence, 4),
            "uncertainty": self.uncertainty,
            "sub_question": self.sub_question,
        }


@dataclass
class ResearchContradiction:
    subject: str
    claim_a: str
    claim_b: str
    card_a_id: str
    card_b_id: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "claim_a": self.claim_a,
            "claim_b": self.claim_b,
            "card_a_id": self.card_a_id,
            "card_b_id": self.card_b_id,
            "reason": self.reason,
        }


@dataclass
class ResearchReport:
    id: str
    query: str
    sub_questions: tuple[str, ...] = ()
    cards: list[EvidenceCard] = field(default_factory=list)
    claims: list[SynthesizedClaim] = field(default_factory=list)
    contradictions: list[ResearchContradiction] = field(default_factory=list)
    final_answer: str = ""
    uncertainty: str = ""
    citations: tuple[str, ...] = ()
    notes: str = ""
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "sub_questions": list(self.sub_questions),
            "cards": [c.to_dict() for c in self.cards],
            "claims": [c.to_dict() for c in self.claims],
            "contradictions": [c.to_dict() for c in self.contradictions],
            "final_answer": self.final_answer,
            "uncertainty": self.uncertainty,
            "citations": list(self.citations),
            "notes": self.notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ResearchReport":
        return cls(
            id=d["id"],
            query=d.get("query", ""),
            sub_questions=tuple(d.get("sub_questions", []) or []),
            cards=[EvidenceCard(**{**c}) for c in d.get("cards", [])],
            claims=[
                SynthesizedClaim(**{
                    **c,
                    "supporting_card_ids": tuple(c.get("supporting_card_ids", [])),
                })
                for c in d.get("claims", [])
            ],
            contradictions=[
                ResearchContradiction(**c) for c in d.get("contradictions", [])
            ],
            final_answer=d.get("final_answer", ""),
            uncertainty=d.get("uncertainty", ""),
            citations=tuple(d.get("citations", []) or []),
            notes=d.get("notes", ""),
            created_at=d.get("created_at", _now_iso()),
        )

    def card_by_id(self, card_id: str) -> Optional[EvidenceCard]:
        return next((c for c in self.cards if c.id == card_id), None)


def _hermes_home() -> Path:
    """``$HERMES_HOME`` or ``~/.hermes`` — matches the rest of the stack."""
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base)


def _default_reports_path() -> Path:
    """Reports location, honoring ``HERMES_HOME`` like the rest of the stack."""
    return _hermes_home() / "jarvis_prime" / "research_reports.jsonl"


def _default_vault() -> ResearchVault:
    """A ResearchVault under ``$HERMES_HOME`` so cockpit state stays isolated."""
    return ResearchVault(path=_hermes_home() / "jarvis_prime" / "research_vault.jsonl")


# A source gatherer takes (query, limit) and returns RawSource list. Injectable
# so tests never touch the network; defaults to the web_search_registry.
SourceGatherer = Callable[[str, int], list[RawSource]]


def _registry_gatherer(query: str, limit: int) -> list[RawSource]:
    """Default gatherer: the configured web-search provider, or [] if none."""
    try:
        from agent.web_search_registry import get_active_search_provider
    except Exception:
        return []
    provider = None
    try:
        provider = get_active_search_provider()
    except Exception:
        provider = None
    if provider is None or not provider.supports_search():
        return []
    try:
        raw = provider.search(query, limit=limit)
    except Exception:
        return []
    return _parse_provider_results(raw, provider_name=getattr(provider, "name", "web"))


def _parse_provider_results(raw: Any, *, provider_name: str) -> list[RawSource]:
    """Tolerantly parse the assorted provider search-result shapes."""
    items: Sequence[Any]
    if isinstance(raw, dict):
        items = raw.get("results") or raw.get("data") or raw.get("hits") or []
    elif isinstance(raw, list):
        items = raw
    else:
        items = []
    out: list[RawSource] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        url = str(it.get("url") or it.get("link") or it.get("href") or "").strip()
        if not url:
            continue
        out.append(
            RawSource(
                title=str(it.get("title") or url).strip(),
                url=url,
                excerpt=str(
                    it.get("content")
                    or it.get("snippet")
                    or it.get("description")
                    or it.get("text")
                    or ""
                ).strip(),
                provider=provider_name,
            )
        )
    return out


@dataclass
class ResearchEngine:
    """Composes the research primitives into the eight-step pipeline."""

    vault: ResearchVault = field(default_factory=_default_vault)
    gatherer: Optional[SourceGatherer] = None
    reports_path: Optional[Path] = None
    confidence_floor: float = 0.65

    # -- step 1: decompose --------------------------------------------------

    def decompose(self, query: str, *, max_sub: int = 4) -> ResearchBrief:
        """Build a ResearchBrief whose questions are the sub-questions.

        Deterministic, stdlib-only: the primary question plus light facet
        questions (definition / evidence / caveats). The cockpit can refine
        this later; the point is a structured brief, not a guess.
        """
        query = query.strip()
        facets = [
            ("What is the precise answer to: " + query + "?", "core claim"),
            ("What primary or official source supports it?", "provenance"),
            ("What are the caveats, limits, or disagreements?", "contradiction check"),
        ]
        questions = [
            ResearchQuestion(text=t, why_it_matters=w) for t, w in facets[:max_sub]
        ]
        return open_brief(
            topic=query or "(empty query)",
            triggered_by="unfamiliar_topic",
            questions=questions,
            scopes=(ResearchScope.EXTERNAL_WEB, ResearchScope.LOCAL_MEMORY),
            minimum_sources=2,
        )

    # -- step 2: gather -----------------------------------------------------

    def gather(
        self,
        brief: ResearchBrief,
        *,
        manual_sources: Optional[Sequence[dict]] = None,
        per_question_limit: int = 4,
    ) -> tuple[list[RawSource], str]:
        """Collect raw sources. Returns ``(sources, notes)``.

        ``notes`` is an honest, user-facing string (e.g. why a result set is
        empty) — never a fabricated source.
        """
        sources: list[RawSource] = []
        seen: set[str] = set()

        for entry in manual_sources or ():
            rs = RawSource.from_dict(entry)
            if rs.url and rs.url not in seen:
                seen.add(rs.url)
                sources.append(rs)

        gatherer = self.gatherer or _registry_gatherer
        provider_used = False
        for q in brief.questions:
            try:
                hits = gatherer(q.text, per_question_limit)
            except Exception:
                hits = []
            for rs in hits:
                provider_used = True
                if rs.url and rs.url not in seen:
                    seen.add(rs.url)
                    sources.append(rs)

        if not sources:
            if not provider_used and not (manual_sources or ()):
                note = (
                    "No web-search provider is configured and no manual sources "
                    "were supplied. Configure a provider (plugins/web/*) or paste "
                    "sources to research. No answer was fabricated."
                )
            else:
                note = "No sources matched the query."
            return [], note
        return sources, ""

    # -- step 3: rank -------------------------------------------------------

    def rank(self, raw: Sequence[RawSource], *, query: str) -> list[RawSource]:
        """Order sources by (trust tier, query relevance), strongest first."""
        q_terms = _terms(query)

        def _strength_rank(rs: RawSource) -> int:
            _, strength = classify_source(rs.url)
            order = {
                EvidenceStrength.PRIMARY: 0,
                EvidenceStrength.STRONG: 1,
                EvidenceStrength.MODERATE: 2,
                EvidenceStrength.WEAK: 3,
                EvidenceStrength.VENDOR_REPORTED: 4,
            }
            return order[strength]

        def _relevance(rs: RawSource) -> float:
            hay = _terms(f"{rs.title} {rs.excerpt}")
            if not q_terms:
                return 0.0
            return len(q_terms & hay) / len(q_terms)

        return sorted(raw, key=lambda rs: (_strength_rank(rs), -_relevance(rs)))

    # -- step 4: cards ------------------------------------------------------

    def to_cards(
        self, ranked: Sequence[RawSource], *, query: str, brief: ResearchBrief
    ) -> list[EvidenceCard]:
        q_terms = _terms(query)
        cards: list[EvidenceCard] = []
        for rs in ranked:
            stype, strength = classify_source(rs.url)
            art = self.vault.add(
                title=rs.title or rs.url,
                source_uri=rs.url,
                source_type=stype,
                evidence_strength=strength,
                excerpt=rs.excerpt,
                tags=("research-mode",),
            )
            hay = _terms(f"{rs.title} {rs.excerpt}")
            relevance = (len(q_terms & hay) / len(q_terms)) if q_terms else 0.0
            cards.append(
                EvidenceCard(
                    id=art.id,
                    title=art.title,
                    source_uri=art.source_uri,
                    source_type=art.source_type.value,
                    evidence_strength=art.evidence_strength.value,
                    excerpt=art.excerpt,
                    claim=art.summary or art.excerpt[:160],
                    relevance=relevance,
                )
            )
        return cards

    # -- step 5: synthesize -------------------------------------------------

    def synthesize(
        self, cards: Sequence[EvidenceCard], *, query: str
    ) -> list[SynthesizedClaim]:
        """One claim per card, with confidence from the card's trust tier.

        We do *not* invent cross-source claims here — the claim text is the
        card's own excerpt-derived summary. This keeps every claim traceable
        to exactly one cited source (verified in :meth:`verify_citations`).
        """
        trust_conf = {
            EvidenceStrength.PRIMARY.value: 0.9,
            EvidenceStrength.STRONG.value: 0.8,
            EvidenceStrength.MODERATE.value: 0.65,
            EvidenceStrength.WEAK.value: 0.45,
            EvidenceStrength.VENDOR_REPORTED.value: 0.5,
        }
        claims: list[SynthesizedClaim] = []
        for card in cards:
            if not card.claim.strip():
                continue
            conf = trust_conf.get(card.evidence_strength, 0.5)
            claims.append(
                SynthesizedClaim(
                    text=card.claim,
                    supporting_card_ids=(card.id,),
                    confidence=conf,
                    uncertainty=""
                    if conf >= self.confidence_floor
                    else "below confidence floor — verify before relying",
                )
            )
        return claims

    # -- step 6: verify citations -------------------------------------------

    def verify_citations(
        self, claims: Sequence[SynthesizedClaim], cards: Sequence[EvidenceCard]
    ) -> list[SynthesizedClaim]:
        """Drop claims whose cited card excerpt does not support the claim.

        Support = non-trivial term overlap between the claim text and the
        cited card's excerpt. Eliminates orphan / hallucinated citations.
        """
        by_id = {c.id: c for c in cards}
        kept: list[SynthesizedClaim] = []
        for claim in claims:
            ok = False
            claim_terms = _terms(claim.text)
            for cid in claim.supporting_card_ids:
                card = by_id.get(cid)
                if not card:
                    continue
                support = _terms(card.excerpt) | _terms(card.title)
                if not claim_terms or (claim_terms & support):
                    ok = True
                    break
            if ok:
                kept.append(claim)
        return kept

    # -- step 7: contradictions ---------------------------------------------

    def find_contradictions(
        self, cards: Sequence[EvidenceCard]
    ) -> list[ResearchContradiction]:
        """Flag pairs of cards that share a subject but oppose each other.

        Heuristic and conservative: two cards are contradictory when their
        claims share subject terms yet one negates a token the other asserts
        (``not``/``no``/``never``/``cannot`` or an antonym-ish ``in/de`` flip).
        Reported, never auto-resolved.
        """
        out: list[ResearchContradiction] = []
        _NEG = {
            "not",
            "no",
            "never",
            "cannot",
            "can't",
            "isn't",
            "aren't",
            "false",
            "incorrect",
            "unsupported",
        }
        for i in range(len(cards)):
            for j in range(i + 1, len(cards)):
                a, b = cards[i], cards[j]
                a_terms, b_terms = _terms(a.claim), _terms(b.claim)
                shared = a_terms & b_terms
                if len(shared) < 2:
                    continue
                a_neg = bool(a_terms & _NEG)
                b_neg = bool(b_terms & _NEG)
                if a_neg != b_neg:
                    out.append(
                        ResearchContradiction(
                            subject=" ".join(sorted(shared)[:4]),
                            claim_a=a.claim,
                            claim_b=b.claim,
                            card_a_id=a.id,
                            card_b_id=b.id,
                            reason="one source negates a claim the other asserts on a shared subject",
                        )
                    )
        return out

    # -- step 8: final answer -----------------------------------------------

    def compose_answer(
        self,
        query: str,
        claims: Sequence[SynthesizedClaim],
        cards: Sequence[EvidenceCard],
        contradictions: Sequence[ResearchContradiction],
    ) -> tuple[str, str, tuple[str, ...]]:
        """Assemble the answer + calibrated uncertainty + citation list."""
        if not claims:
            return (
                "I don't know yet — I couldn't gather source-backed evidence for this query.",
                "no verified sources",
                (),
            )
        by_id = {c.id: c for c in cards}
        citations: list[str] = []
        lines: list[str] = []
        for claim in claims:
            cited = [
                by_id[cid].source_uri
                for cid in claim.supporting_card_ids
                if cid in by_id
            ]
            for uri in cited:
                if uri not in citations:
                    citations.append(uri)
            cite_str = f" [{', '.join(cited)}]" if cited else ""
            lines.append(f"- {claim.text}{cite_str}")
        answer = "\n".join(lines)
        if contradictions:
            answer += f"\n\nNote: {len(contradictions)} contradiction(s) detected across sources — see the contradiction report."

        report = audit_response(
            answer,
            provided_citations=citations,
            confidence=max((c.confidence for c in claims), default=0.0),
            confidence_floor=self.confidence_floor,
        )
        uncertainty = report.outcome.value
        if report.findings:
            uncertainty += f" ({len(report.findings)} unhedged specific(s))"
        return answer, uncertainty, tuple(citations)

    # -- orchestration ------------------------------------------------------

    def run(
        self,
        query: str,
        *,
        manual_sources: Optional[Sequence[dict]] = None,
        persist: bool = True,
    ) -> ResearchReport:
        brief = self.decompose(query)
        raw, notes = self.gather(brief, manual_sources=manual_sources)
        report_id = (
            "rr_" + hashlib.sha1(f"{query}|{_now_iso()}".encode()).hexdigest()[:16]
        )

        if not raw:
            report = ResearchReport(
                id=report_id,
                query=query,
                sub_questions=tuple(q.text for q in brief.questions),
                final_answer="I don't know yet — no sources were available to research this.",
                uncertainty="no sources",
                notes=notes,
            )
            if persist:
                self._save(report)
            return report

        ranked = self.rank(raw, query=query)
        cards = self.to_cards(ranked, query=query, brief=brief)
        claims = self.synthesize(cards, query=query)
        claims = self.verify_citations(claims, cards)
        contradictions = self.find_contradictions(cards)
        answer, uncertainty, citations = self.compose_answer(
            query, claims, cards, contradictions
        )

        report = ResearchReport(
            id=report_id,
            query=query,
            sub_questions=tuple(q.text for q in brief.questions),
            cards=cards,
            claims=claims,
            contradictions=contradictions,
            final_answer=answer,
            uncertainty=uncertainty,
            citations=citations,
            notes=notes,
        )
        if persist:
            self._save(report)
        return report

    # -- promotion / task payloads (executed by the gated cockpit handlers) -

    @staticmethod
    def promotion_payload(
        report: ResearchReport, card_id: str
    ) -> Optional[dict[str, Any]]:
        """Build the Memory-write payload for a card (handler applies the gate).

        Returns the canonical ``MemoryStore.remember`` kwargs, or ``None`` when
        the card is unknown. The handler — not the engine — performs the gated
        write so promotion flows through the same policy the Memory screen
        reads.
        """
        card = report.card_by_id(card_id)
        if card is None:
            return None
        # Trust tier → confidence so the durable-confidence floor (0.6) applies.
        conf = {
            "primary": 0.95,
            "strong": 0.85,
            "moderate": 0.7,
            "weak": 0.45,
            "vendor_reported": 0.5,
        }.get(card.evidence_strength, 0.5)
        return {
            "key": card.title[:120] or card.source_uri,
            "value": card.claim or card.excerpt[:280],
            "durability": "durable",
            "source": f"research:{card.source_uri}",
            "confidence": conf,
            "citations": (card.source_uri,),
            "tags": ("research-mode", card.source_type),
        }

    @staticmethod
    def task_prompt(report: ResearchReport) -> str:
        """Build a coding-task prompt from a report's answer + citations."""
        lines = [
            f"Research-derived task for: {report.query}",
            "",
            "Findings:",
            report.final_answer or "(no answer)",
        ]
        if report.citations:
            lines += ["", "Sources:"]
            lines += [f"- {c}" for c in report.citations]
        if report.contradictions:
            lines += [
                "",
                f"Caution: {len(report.contradictions)} contradiction(s) flagged — resolve before relying.",
            ]
        return "\n".join(lines)

    # -- persistence (mirrors ResearchVault) --------------------------------

    def _resolve_reports_path(self) -> Path:
        return Path(self.reports_path) if self.reports_path else _default_reports_path()

    def _save(self, report: ResearchReport) -> Path:
        reports = self.list_reports()
        reports = [r for r in reports if r.id != report.id]
        reports.append(report)
        target = self._resolve_reports_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = "".join(
            json.dumps(r.to_dict(), sort_keys=True) + "\n" for r in reports
        )
        fd, tmp = tempfile.mkstemp(
            dir=str(target.parent), prefix=".rreports-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
        return target

    def list_reports(self) -> list[ResearchReport]:
        target = self._resolve_reports_path()
        if not target.exists():
            return []
        out: list[ResearchReport] = []
        with open(target, "r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    out.append(ResearchReport.from_dict(json.loads(raw)))
                except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                    continue
        return out

    def get_report(self, report_id: str) -> Optional[ResearchReport]:
        return next((r for r in self.list_reports() if r.id == report_id), None)
