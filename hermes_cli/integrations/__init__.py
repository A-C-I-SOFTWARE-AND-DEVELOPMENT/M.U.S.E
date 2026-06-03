"""Hermes integration adapters for external developer services.

Each module in this package wraps a single external service (GitHub,
Supabase, Vercel, …) in a uniform shape:

- ``detect()`` — return whether the service's CLI/tooling is reachable
  from the current shell, without making any network call.
- ``plan(...)`` — return a structured plan describing what *would*
  happen if the operator approved the action. Always safe to call.
- ``explain(plan)`` — render the plan in plain English. Never has side
  effects; intended for humans and for the orchestration ledger.
- ``execute(plan, approve=True)`` — actually run the commands. Refuses
  to run unless ``approve=True`` is explicitly passed.

The adapters live at this layer because Hermes treats external services
as opt-in capabilities that must be discovered at runtime — we never
want an import-time failure just because somebody hasn't installed the
``gh`` CLI. The integration policy (``docs/integrations/integration-policy.md``)
describes the cross-cutting rules every adapter must follow:

1. Detect CLI availability before suggesting commands.
2. Build commands as argv lists, never as shell strings.
3. Default to ``dry_run=True`` / ``approve=False``.
4. Block on secret-shaped content before staging or shipping anything.
5. Emit a rollback note alongside every plan.
6. Surface a validation plan the operator can run to confirm success.
"""

from __future__ import annotations

from . import github, supabase, vercel
# INT-1: capability/approval governance layer that complements the developer-
# service adapters above. It catalogs communication integrations (email/SMS/
# calendar) and enforces owner approval on send/create actions, without adding
# any new outbound credential path (transports are wired explicitly by callers,
# e.g. delegating to an existing gateway channel).
from .registry import (
    ActionRequest,
    ActionResult,
    IntegrationError,
    IntegrationRegistry,
    IntegrationSpec,
    default_registry,
)
from .transports import build_live_registry, make_gateway_transport

__all__ = [
    "github",
    "supabase",
    "vercel",
    "available_integrations",
    # INT-1 governance layer
    "IntegrationSpec",
    "IntegrationRegistry",
    "ActionRequest",
    "ActionResult",
    "IntegrationError",
    "default_registry",
    "build_live_registry",
    "make_gateway_transport",
]


def available_integrations() -> dict[str, bool]:
    """Return ``{name: cli_present}`` for every known integration.

    Pure: only calls each adapter's ``detect()``. Never makes a network
    request, never writes a file.
    """
    return {
        "github": github.detect().cli_present,
        "supabase": supabase.detect().cli_present,
        "vercel": vercel.detect().cli_present,
    }
