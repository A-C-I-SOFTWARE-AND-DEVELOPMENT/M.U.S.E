"""Tests for the JARVIS Research Mode Evidence Engine.

Covers the eight pipeline steps end to end with an injected (network-free)
source gatherer, plus the honest no-source path and the promotion payload that
the cockpit gate consumes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.research_engine import (
    EvidenceCard,
    RawSource,
    ResearchEngine,
    ResearchReport,
    classify_source,
)
from hermes_cli.jarvis_prime.research_vault import (
    EvidenceStrength,
    ResearchVault,
    SourceType,
)


def _engine(tmp_path: Path, gatherer=None) -> ResearchEngine:
    return ResearchEngine(
        vault=ResearchVault(path=tmp_path / "vault.jsonl"),
        gatherer=gatherer,
        reports_path=tmp_path / "reports.jsonl",
    )


def _fake_gatherer(results):
    def _g(query: str, limit: int):
        return [RawSource.from_dict(r) for r in results]

    return _g


def test_classify_source_trust_tiers():
    assert classify_source("https://arxiv.org/abs/1234")[1] is EvidenceStrength.PRIMARY
    assert classify_source("https://docs.python.org/3/")[0] is SourceType.OFFICIAL_DOC
    assert classify_source("https://github.com/x/y")[1] is EvidenceStrength.STRONG
    # Unknown host is conservative.
    assert (
        classify_source("https://some-random-blog.example/post")[1]
        is EvidenceStrength.WEAK
    )
    # Boundary-safe: a spoofed host or a trusted token in the path must NOT be
    # promoted to primary (incomplete-substring-sanitization regression).
    assert classify_source("https://arxiv.org.evil.com/x")[1] is EvidenceStrength.WEAK
    assert classify_source("https://evil.com/arxiv.org")[1] is EvidenceStrength.WEAK
    # A genuine subdomain of a trusted host still resolves.
    assert (
        classify_source("https://export.arxiv.org/abs/1")[1] is EvidenceStrength.PRIMARY
    )


def test_decompose_produces_sub_questions(tmp_path):
    brief = _engine(tmp_path).decompose("What is HTTP/3?")
    assert len(brief.questions) >= 2
    assert any("HTTP/3" in q.text for q in brief.questions)


def test_run_with_fake_provider_yields_source_backed_report(tmp_path):
    gatherer = _fake_gatherer([
        {
            "title": "HTTP/3 spec",
            "url": "https://docs.example.org/http3",
            "content": "HTTP/3 uses QUIC transport over UDP for multiplexing.",
        }
    ])
    report = _engine(tmp_path, gatherer).run("What transport does HTTP/3 use?")
    assert report.cards, "expected at least one evidence card"
    assert report.claims, "expected synthesized claims"
    # Every citation in the answer is backed by a real card source.
    card_uris = {c.source_uri for c in report.cards}
    assert set(report.citations).issubset(card_uris)
    assert "QUIC" in report.final_answer or "quic" in report.final_answer.lower()


def test_run_with_no_provider_is_honest_not_fabricated(tmp_path):
    # Gatherer returns nothing and no manual sources -> honest empty result.
    report = _engine(tmp_path, _fake_gatherer([])).run("obscure unknowable thing")
    assert report.cards == []
    assert report.claims == []
    assert "don't know" in report.final_answer.lower()
    assert report.notes  # explains why it's empty
    assert "fabricat" in report.notes.lower()


def test_manual_sources_used_when_no_provider(tmp_path):
    report = _engine(tmp_path, _fake_gatherer([])).run(
        "What is the capital city referenced?",
        manual_sources=[
            {
                "title": "Reference doc",
                "url": "https://docs.example.gov/ref",
                "excerpt": "The capital city referenced is Springfield.",
            }
        ],
    )
    assert report.cards
    assert report.citations == ("https://docs.example.gov/ref",)


def test_ranking_orders_primary_before_weak(tmp_path):
    eng = _engine(tmp_path)
    raw = [
        RawSource(title="blog", url="https://random.example/x", excerpt="alpha beta"),
        RawSource(title="paper", url="https://arxiv.org/abs/1", excerpt="alpha beta"),
    ]
    ranked = eng.rank(raw, query="alpha beta")
    # The primary (arxiv) source ranks ahead of the weak blog. Assert on the
    # exact URL rather than a substring so the check is boundary-safe.
    assert ranked[0].url == "https://arxiv.org/abs/1"


def test_verify_citations_drops_orphans(tmp_path):
    eng = _engine(tmp_path)
    card = EvidenceCard(
        id="c1",
        title="Doc",
        source_uri="https://x",
        source_type="official_doc",
        evidence_strength="primary",
        excerpt="QUIC over UDP",
        claim="QUIC over UDP",
    )
    from hermes_cli.jarvis_prime.research_engine import SynthesizedClaim

    supported = SynthesizedClaim(text="QUIC over UDP", supporting_card_ids=("c1",))
    orphan = SynthesizedClaim(
        text="completely unrelated topic words", supporting_card_ids=("missing",)
    )
    kept = eng.verify_citations([supported, orphan], [card])
    assert supported in kept
    assert orphan not in kept


def test_find_contradictions_flags_negation(tmp_path):
    eng = _engine(tmp_path)
    cards = [
        EvidenceCard(
            "a",
            "A",
            "https://a",
            "blog",
            "moderate",
            "",
            "feature x is supported on platform",
        ),
        EvidenceCard(
            "b",
            "B",
            "https://b",
            "blog",
            "moderate",
            "",
            "feature x is not supported on platform",
        ),
    ]
    contradictions = eng.find_contradictions(cards)
    assert contradictions
    assert contradictions[0].card_a_id == "a"


def test_report_round_trips_and_persists(tmp_path):
    eng = _engine(
        tmp_path,
        _fake_gatherer([
            {
                "title": "T",
                "url": "https://docs.example.org/t",
                "content": "alpha beta gamma",
            }
        ]),
    )
    report = eng.run("alpha beta")
    again = eng.get_report(report.id)
    assert again is not None
    assert again.id == report.id
    # Round-trip dict.
    rebuilt = ResearchReport.from_dict(report.to_dict())
    assert rebuilt.query == report.query
    assert len(rebuilt.cards) == len(report.cards)


def test_promotion_payload_carries_provenance(tmp_path):
    eng = _engine(
        tmp_path,
        _fake_gatherer([
            {
                "title": "Primary spec",
                "url": "https://arxiv.org/abs/9",
                "content": "alpha beta gamma delta",
            }
        ]),
    )
    report = eng.run("alpha beta")
    card = report.cards[0]
    payload = ResearchEngine.promotion_payload(report, card.id)
    assert payload is not None
    assert payload["citations"] == (card.source_uri,)
    assert payload["source"].startswith("research:")
    assert payload["durability"] == "durable"
    # Primary source clears the durable-confidence floor (0.6).
    assert payload["confidence"] >= 0.6
    assert ResearchEngine.promotion_payload(report, "nonexistent") is None


def test_task_prompt_includes_answer_and_sources(tmp_path):
    eng = _engine(
        tmp_path,
        _fake_gatherer([
            {
                "title": "T",
                "url": "https://docs.example.org/t",
                "content": "alpha beta gamma",
            }
        ]),
    )
    report = eng.run("alpha beta")
    prompt = ResearchEngine.task_prompt(report)
    assert "alpha beta" in prompt
    assert "https://docs.example.org/t" in prompt
