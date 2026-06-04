"""Enterprise Council — autonomous multi-agent system for Hermes.

This package backs the ``skills/enterprise-council/*`` agent set. The
runtime here is deliberately thin — it composes existing Hermes
primitives (credential pool, redacting logger, curator) rather than
duplicating them. Each module is meant to be importable without
side-effects so it can be exercised from unit tests and from real
Hermes sessions equally cleanly.

Public surface:

    from enterprise.secrets import fetch_secret, SecretBundle
    from enterprise.policy import classify, requires_human, Risk
    from enterprise.audit import audit, AuditEvent
    from enterprise.judge import cross_check
    from enterprise.council import plan, dispatch
    from enterprise.adapters import for_domain

Anything not exported above is implementation detail.
"""

from enterprise.audit import AuditEvent, audit
from enterprise.council import dispatch, plan
from enterprise.judge import cross_check
from enterprise.policy import Risk, classify, requires_human
from enterprise.secrets import OAuthRefreshError, SecretBundle, fetch_secret

__all__ = [
    "AuditEvent",
    "OAuthRefreshError",
    "Risk",
    "SecretBundle",
    "audit",
    "classify",
    "cross_check",
    "dispatch",
    "fetch_secret",
    "plan",
    "requires_human",
]
