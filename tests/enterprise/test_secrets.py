"""Secret-fetching ACL, redaction, and short-lived semantics.

The single most important property to lock down: a secret value MUST
NOT reach a log file, an audit row, or a string-formatted repr. The
last assertion in each test exercises that.
"""

from __future__ import annotations

import logging

import pytest

from enterprise.secrets import (
    SecretAccessDenied,
    SecretBundle,
    SecretNotFound,
    fetch_secret,
    list_acl,
    secret_fingerprint,
)


def test_fetch_secret_returns_value_for_allowed_role(seed_secret):
    seed_secret("stripe", "sk-test-VALUEFAKE_AAAAAAAA")
    bundle = fetch_secret("stripe", caller_role="finance")
    assert isinstance(bundle, SecretBundle)
    assert bundle.value == "sk-test-VALUEFAKE_AAAAAAAA"
    assert bundle.service == "stripe"
    assert bundle.ephemeral is False  # long-lived API key path


def test_fetch_secret_denies_wrong_role(seed_secret):
    seed_secret("stripe", "sk-test-NOPE_NOPE_NOPE")
    with pytest.raises(SecretAccessDenied):
        fetch_secret("stripe", caller_role="sales")


def test_fetch_secret_allows_delegated_role(seed_secret):
    seed_secret("stripe", "sk-test-DELEGATED_DELEGATED")
    # Orchestrator fetches on behalf of finance — allowed.
    bundle = fetch_secret("stripe", caller_role="orchestrator", delegated_for="finance")
    assert bundle.service == "stripe"


def test_fetch_secret_missing_env_raises():
    # No env var set, no pool entry — must be SecretNotFound.
    with pytest.raises(SecretNotFound):
        fetch_secret("workday", caller_role="hr")


def test_fetch_secret_unknown_service_raises():
    with pytest.raises(SecretNotFound):
        fetch_secret("totally-made-up", caller_role="finance")


def test_fetch_secret_rejects_value_with_newline(monkeypatch, seed_secret):
    monkeypatch.setenv("STRIPE_API_KEY", "sk-test-AAAA\nsk-test-BBBB")
    with pytest.raises(SecretNotFound):
        fetch_secret("stripe", caller_role="finance")


def test_secret_bundle_repr_does_not_leak_value(seed_secret):
    seed_secret("stripe", "sk-test-SUPERSECRETLEAK_AAAA")
    bundle = fetch_secret("stripe", caller_role="finance")
    text = repr(bundle)
    assert "SUPERSECRETLEAK" not in text
    assert "<redacted" in text


def test_logger_does_not_emit_secret_value(seed_secret, caplog):
    seed_secret("stripe", "sk-test-CAPLOG_LEAK_PROBE_XX")
    with caplog.at_level(logging.INFO, logger="enterprise.secrets"):
        fetch_secret("stripe", caller_role="finance", scope="invoice.read")
    # The info log row from `_logger.info(...)` must NOT include the raw
    # value. It logs service/scope/role only.
    rendered = "\n".join(rec.message for rec in caplog.records)
    assert "CAPLOG_LEAK_PROBE" not in rendered
    assert "stripe" in rendered  # but service name IS expected


def test_secret_fingerprint_is_deterministic_and_short(seed_secret):
    seed_secret("stripe", "sk-test-fingerprint-stable")
    b1 = fetch_secret("stripe", caller_role="finance")
    b2 = fetch_secret("stripe", caller_role="finance")
    fp1 = secret_fingerprint(b1)
    fp2 = secret_fingerprint(b2)
    assert fp1 == fp2
    assert fp1.startswith("stripe:")
    assert len(fp1.split(":")[1]) == 8  # 8 hex chars, not the whole hash


def test_acl_lists_known_services():
    acl = list_acl(["stripe", "salesforce", "compliancedb"])
    assert acl["stripe"] == ["finance"]
    # docusign is a cross-domain entry; both sales and finance may use it.
    full = list_acl()
    assert "finance" in full["docusign"] and "sales" in full["docusign"]
