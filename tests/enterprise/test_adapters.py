"""Smoke tests for the five domain adapters.

Each adapter must:
  * Build cleanly from a SecretBundle.
  * Dispatch a representative action through its ``call(action, args)``
    surface and return a dict with a ``status`` key.
  * Refuse unknown actions with ``status == "unknown_action"`` instead
    of raising — the orchestrator relies on that to record the failure
    cleanly rather than crashing the dispatch loop.
"""

from __future__ import annotations

import pytest

from enterprise.adapters import for_domain, known_domains
from enterprise.secrets import SecretBundle


def _bundle(service: str) -> SecretBundle:
    return SecretBundle(
        service=service,
        scope=None,
        value="sk-test-FAKE_VALUE_FOR_ADAPTERS",
        expires_at=None,
        ephemeral=False,
    )


def test_known_domains_are_the_canonical_five():
    assert known_domains() == [
        "customer-service",
        "finance",
        "hr",
        "operations",
        "sales",
    ]


@pytest.mark.parametrize("domain", known_domains())
def test_for_domain_returns_a_callable_factory(domain):
    build = for_domain(domain)
    assert callable(build)
    adapter = build(_bundle(domain.split("-")[0]))
    assert hasattr(adapter, "call")


def test_finance_invoice_create_and_send_roundtrip():
    a = for_domain("finance")(_bundle("stripe"))
    r1 = a.call("invoice.create", {"vendor": "ACME", "amount": 1_200})
    assert r1["status"] == "ok"
    iid = r1["invoice_id"]
    r2 = a.call("invoice.send", {"invoice_id": iid})
    assert r2 == {"status": "ok", "invoice_id": iid, "state": "sent"}


def test_hr_candidate_screen_scores_relevant_skills():
    a = for_domain("hr")(_bundle("workday"))
    r = a.call(
        "candidate.screen",
        {
            "name": "Ada",
            "resume_text": "Worked extensively in Python and SQL on data pipelines.",
            "role": "Data Engineer",
            "required_skills": ("python", "sql", "rust"),
        },
    )
    assert r["status"] == "ok"
    assert "python" in r["skills_present"] and "sql" in r["skills_present"]
    assert "rust" in r["skills_missing"]


def test_customer_service_classifies_billing_ticket():
    a = for_domain("customer-service")(_bundle("zendesk"))
    r = a.call(
        "ticket.classify", {"subject": "Wrong charge", "body": "You billed me twice."}
    )
    assert r["category"] == "billing"
    assert r["severity"] in {"low", "medium", "high"}


def test_operations_compliance_check_flags_missing_evidence():
    a = for_domain("operations")(_bundle("sap"))
    r = a.call(
        "compliance.check",
        {"region": "EU", "category": "financial", "evidence": ()},
    )
    assert r["verdict"] == "issues"
    assert any("DPA" in f for f in r["findings"])


def test_sales_proposal_draft_and_discount():
    a = for_domain("sales")(_bundle("salesforce"))
    draft = a.call(
        "proposal.draft",
        {"lead_id": "LEAD-1", "product": "Pro", "amount": 10_000},
    )
    assert draft["status"] == "ok"
    pid = draft["proposal_id"]
    discounted = a.call(
        "discount.apply",
        {"proposal_id": pid, "discount": 0.10, "reason": "early-bird"},
    )
    assert discounted["new_amount"] == 9_000.0


def test_adapter_returns_unknown_action_instead_of_raising():
    a = for_domain("finance")(_bundle("stripe"))
    r = a.call("invoice.do-the-thing", {})
    assert r == {"status": "unknown_action", "action": "invoice.do-the-thing"}
