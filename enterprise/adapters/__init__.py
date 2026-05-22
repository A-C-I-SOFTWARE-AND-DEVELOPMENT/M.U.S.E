"""Domain adapter shims for the enterprise council.

Each domain (Finance, HR, CustomerService, Operations, Sales) gets one
module here exposing 2–4 service classes. The classes are in-memory
mocks suitable for tests and demos; an operator deploys the system
by swapping these for real SDKs (stripe, workday-rest, simple-salesforce,
zendesk-python, etc.) without changing the SKILL.md or the orchestrator.

The adapter interface is intentionally small:
  * ``__init__(secret: SecretBundle)`` — receives the credential at
    construction. The adapter does NOT call `fetch_secret` itself
    so the orchestrator stays in control of least-privilege.
  * One method per declared sub-skill. Methods take ordinary kwargs
    and return JSON-serialisable dicts so audit can hash them.

If you're adding a new domain: copy `finance.py`, rename, list the
service classes in `for_domain`, add the (domain, action) entries to
`enterprise.policy._BASE_RULES`, and add an SKILL.md.
"""

from __future__ import annotations

from typing import Callable

from enterprise.adapters import cs, finance, hr, ops, sales

_DOMAINS: dict[str, Callable[..., object]] = {
    "finance": finance.build,
    "hr": hr.build,
    "customer-service": cs.build,
    "operations": ops.build,
    "sales": sales.build,
}


def for_domain(domain: str):
    """Return the build() factory for ``domain``. Raises KeyError if unknown."""
    try:
        return _DOMAINS[domain]
    except KeyError as exc:
        raise KeyError(
            f"Unknown enterprise domain {domain!r}. Known: {sorted(_DOMAINS)}"
        ) from exc


def known_domains() -> list[str]:
    return sorted(_DOMAINS.keys())
