"""Tests for muse_cli.jarvis_prime.research + .epistemics.

The research module triggers a brief when JARVIS doesn't know
enough. The epistemics module enforces no-hallucination on every
output. Together they implement the user's "never hallucinates"
requirement.
"""

from __future__ import annotations

from muse_cli.jarvis_prime.epistemics import (
    AuditOutcome,
    audit_response,
)
from muse_cli.jarvis_prime.research import (
    ResearchQuestion,
    ResearchScope,
    needs_research,
    open_brief,
)


def test_needs_research_returns_none_when_confident_and_known() -> None:
    assert needs_research(
        confidence=0.9,
        recollection_hits=3,
        has_matching_rule=True,
    ) is None


def test_needs_research_low_confidence_no_recollection() -> None:
    assert needs_research(
        confidence=0.3,
        recollection_hits=0,
        has_matching_rule=False,
    ) in ("no_recollection", "low_confidence", "unfamiliar_topic")


def test_needs_research_unfamiliar_code_question() -> None:
    assert needs_research(
        confidence=0.4,
        recollection_hits=0,
        has_matching_rule=False,
        is_code_question=True,
    ) in ("no_recollection", "code_unknown", "unfamiliar_topic", "low_confidence")


def test_open_brief_local_scopes_by_default() -> None:
    brief = open_brief(
        topic="how does the parser handle empty input",
        triggered_by="code_unknown",
        questions=[ResearchQuestion("does parser handle empty input", "avoid crash")],
    )
    assert ResearchScope.LOCAL_REPO in brief.scopes
    assert ResearchScope.LOCAL_MEMORY in brief.scopes
    assert ResearchScope.LOCAL_DOCS in brief.scopes
    # External web is NOT included for code questions.
    assert ResearchScope.EXTERNAL_WEB not in brief.scopes


def test_open_brief_external_for_unfamiliar_topic() -> None:
    brief = open_brief(
        topic="post-quantum cryptography roadmap",
        triggered_by="unfamiliar_topic",
        questions=[ResearchQuestion("what is PQC", "user asked")],
    )
    assert ResearchScope.EXTERNAL_WEB in brief.scopes


def test_audit_pass_on_calibrated_response() -> None:
    response = (
        "I'm not certain — based on what I recall the install URL pattern is "
        "the same as before."
    )
    report = audit_response(response, confidence=0.95)
    assert report.outcome == AuditOutcome.PASS
    assert report.hedge_count >= 1


def test_audit_flags_uncited_url() -> None:
    response = "The docs at https://example.com/api/v1 say it works that way."
    report = audit_response(response, confidence=0.95)
    assert report.outcome in (AuditOutcome.NEEDS_CITATIONS, AuditOutcome.FAIL)
    assert any(f.kind == "URL" for f in report.findings)


def test_audit_passes_when_citation_provided() -> None:
    response = "The function lives at muse_cli/jarvis_prime/runtime.py and the doc URL is https://example.com."
    report = audit_response(
        response,
        provided_citations=["muse_cli/jarvis_prime/runtime.py", "https://example.com"],
        confidence=0.9,
    )
    assert report.outcome in (AuditOutcome.PASS, AuditOutcome.NEEDS_CITATIONS)


def test_audit_low_confidence_demands_research() -> None:
    report = audit_response("anything goes", confidence=0.2)
    assert report.outcome == AuditOutcome.NEEDS_RESEARCH


def test_audit_many_uncited_specifics_fails() -> None:
    response = (
        "Use foo() in src/lib.py:42. Latest version is v3.14.159. RFC 8765 covers it. "
        "Function bar() returns a dict per PEP 484. See https://docs.x.com section 4.2.1."
    )
    report = audit_response(response, confidence=0.95)
    assert report.outcome in (AuditOutcome.FAIL, AuditOutcome.NEEDS_CITATIONS)
    assert report.risky_claim_count >= 3
