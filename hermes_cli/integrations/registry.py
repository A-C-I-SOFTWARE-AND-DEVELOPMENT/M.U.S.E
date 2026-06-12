"""Integration registry with approval-gated actions (INT-1).

A thin, capability-typed registry that **wraps** existing transports (the
`gateway/` channels, MCP adapters) rather than introducing new ones. Its job is
governance, not transport: every action is checked against the integration's
declared capabilities, and any capability marked ``requires_approval`` (send
email/SMS, create calendar events, …) is **blocked unless an owner approval is
present**. No outbound action leaves the machine through this module — a
transport callable must be supplied explicitly, and approval-gated actions are
refused without approval.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, List

logger = logging.getLogger(__name__)

# A transport actually performs an action for an integration. Supplied by the
# caller (e.g. an existing gateway channel). None ⇒ declared-but-not-wired.
Transport = Callable[["ActionRequest"], Any]


@dataclass(frozen=True)
class IntegrationSpec:
    name: str
    capabilities: frozenset[str]
    requires_approval: frozenset[str] = frozenset()
    scopes: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        # requires_approval must be a subset of capabilities.
        unknown = self.requires_approval - self.capabilities
        if unknown:
            raise ValueError(f"{self.name}: requires_approval not in capabilities: {sorted(unknown)}")


@dataclass(frozen=True)
class ActionRequest:
    integration: str
    capability: str
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ActionResult:
    status: str  # "ok" | "needs_approval" | "rejected" | "error"
    detail: str = ""
    data: Any = None


class IntegrationError(Exception):
    pass


def _autonomy_allows_send(request: "ActionRequest") -> bool:
    """True iff the autonomy policy auto-approves this outbound action.

    Delegates to the existing ``hermes_cli/approval_policy.py`` so behavior is
    governed by the project's ``HERMES_AUTONOMY`` switch (default ASSISTED →
    requires confirmation; AUTONOMOUS/YOLO → auto-approve, audited). Fail-closed:
    any error means "not auto-approved".
    """
    try:
        from hermes_cli import approval_policy as ap

        req = ap.ApprovalRequest(
            action=ap.Action.OUTBOUND_MESSAGE,
            summary=f"{request.integration}.{request.capability}",
            target=str(request.payload.get("to", "")),
            details={"integration": request.integration, "capability": request.capability},
        )
        result = ap.evaluate(req)
        try:
            ap.record_decision(req, result)
        except Exception:
            pass  # auditing is best-effort; never block on it
        return result.decision is ap.Decision.ALLOW
    except Exception:
        return False


class IntegrationRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, IntegrationSpec] = {}
        self._transports: dict[str, Transport] = {}

    def register(self, spec: IntegrationSpec, transport: Optional[Transport] = None) -> None:
        self._specs[spec.name] = spec
        if transport is not None:
            self._transports[spec.name] = transport

    def list(self) -> "List[IntegrationSpec]":
        return list(self._specs.values())

    def get(self, name: str) -> Optional[IntegrationSpec]:
        return self._specs.get(name)

    def execute(self, request: ActionRequest, *, approved: bool = False) -> ActionResult:
        """Execute (or refuse) an action under capability + approval governance.

        * unknown integration / capability → ``rejected``.
        * capability in ``requires_approval`` and not ``approved`` →
          ``needs_approval`` (transport is NOT called — nothing is sent).
        * otherwise → call the registered transport, or return ``ok`` with no
          side effect when no transport is wired (declared-but-gated stub).
        """
        spec = self._specs.get(request.integration)
        if spec is None:
            return ActionResult("rejected", f"unknown integration {request.integration!r}")
        if request.capability not in spec.capabilities:
            return ActionResult(
                "rejected",
                f"{request.integration!r} does not support capability {request.capability!r}",
            )
        if request.capability in spec.requires_approval and not approved:
            # Consult the existing autonomy policy: under AUTONOMOUS/YOLO an
            # outbound send is auto-approved (and audited); under ASSISTED /
            # READ_ONLY it still requires explicit owner confirmation.
            if not _autonomy_allows_send(request):
                return ActionResult(
                    "needs_approval",
                    f"{request.integration}.{request.capability} requires owner approval "
                    f"(set HERMES_AUTONOMY=autonomous to auto-approve)",
                )

        transport = self._transports.get(request.integration)
        if transport is None:
            # Declared but not wired to a real transport — no external effect.
            return ActionResult("ok", "no transport wired (declared-only)", data=None)
        try:
            data = transport(request)
            return ActionResult("ok", "executed", data=data)
        except Exception as err:
            logger.warning("[integrations] transport error %s.%s: %s",
                           request.integration, request.capability, err)
            return ActionResult("error", str(err))


# ── Seed specs (capability declarations; approval-gated sends) ───────────────

def default_registry() -> IntegrationRegistry:
    """A registry seeded with common integrations as governance declarations.

    Transports are intentionally unwired (no new credential paths). Sends/creates
    are approval-gated; reads/drafts are allowed. Wire a transport later by
    delegating to the existing gateway/MCP path.
    """
    reg = IntegrationRegistry()
    reg.register(IntegrationSpec(
        name="email",
        capabilities=frozenset({"read", "draft", "send"}),
        requires_approval=frozenset({"send"}),
        scopes=("inbox", "compose"),
        notes="Send is owner-gated; delegate transport to existing gateway email path.",
    ))
    reg.register(IntegrationSpec(
        name="sms",
        capabilities=frozenset({"read", "draft", "send"}),
        requires_approval=frozenset({"send"}),
        notes="Send is owner-gated.",
    ))
    reg.register(IntegrationSpec(
        name="calendar",
        capabilities=frozenset({"read", "create_event"}),
        requires_approval=frozenset({"create_event"}),
        notes="Event creation is owner-gated.",
    ))
    return reg
