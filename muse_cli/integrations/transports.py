"""Transports that bind the integration registry to real send paths (INT-1).

The registry governs *whether* an action may run (capability + autonomy policy);
a transport *performs* it. These adapters delegate to the existing Hermes
gateway send path (``gateway/delivery.py`` + ``gateway/platforms/{email,sms}.py``)
rather than opening any new outbound credential path.

Binding is explicit: a caller supplies a configured ``send_fn`` (e.g. one that
wraps their gateway ``DeliveryRouter``), and `make_gateway_transport` adapts it
to the registry's ``Transport`` shape. `build_live_registry` wires email/SMS/
calendar transports when senders are provided; with no senders it returns the
declared-only registry (no side effects).
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from .registry import ActionRequest, IntegrationError, IntegrationRegistry, default_registry

logger = logging.getLogger(__name__)

# A sender takes the action payload and actually delivers it, returning a
# transport-specific receipt. Supplied by the caller (configured gateway path).
Sender = Callable[[dict], Any]


def make_gateway_transport(send_fn: Sender) -> Callable[[ActionRequest], Any]:
    """Adapt a payload-sender into a registry Transport.

    The returned transport extracts ``request.payload`` and calls ``send_fn``.
    Errors propagate to the registry, which surfaces them as an ``error``
    ActionResult (never an unhandled crash).
    """

    def _transport(request: ActionRequest) -> Any:
        if send_fn is None:  # defensive
            raise IntegrationError("no send_fn bound for this transport")
        return send_fn(dict(request.payload))

    return _transport


def gateway_sender_from_router(deliver_fn: Callable[[dict], Any]) -> Sender:
    """Wrap an existing gateway delivery callable as a Sender.

    ``deliver_fn`` is whatever the host already uses to deliver a message
    through the gateway (sync). For the async ``DeliveryRouter.deliver``,
    callers should pass a small sync shim (e.g. ``lambda p: asyncio.run(
    router.deliver(_target_from(p)))``) — kept out of this module so the
    gateway's event-loop policy stays the caller's concern.
    """
    return lambda payload: deliver_fn(payload)


def build_live_registry(
    *,
    email_sender: Optional[Sender] = None,
    sms_sender: Optional[Sender] = None,
    calendar_sender: Optional[Sender] = None,
) -> IntegrationRegistry:
    """Return a registry with transports wired for the provided senders.

    Senders left as ``None`` stay declared-only (governed but no side effect).
    Approval for ``send``/``create_event`` is still enforced by the registry's
    autonomy check — a wired transport does not bypass the gate.
    """
    reg = default_registry()
    if email_sender is not None:
        reg.register(reg.get("email"), transport=make_gateway_transport(email_sender))  # ty: ignore[invalid-argument-type]  # dynamic config/plugin path
    if sms_sender is not None:
        reg.register(reg.get("sms"), transport=make_gateway_transport(sms_sender))  # ty: ignore[invalid-argument-type]  # dynamic config/plugin path
    if calendar_sender is not None:
        reg.register(reg.get("calendar"), transport=make_gateway_transport(calendar_sender))  # ty: ignore[invalid-argument-type]  # dynamic config/plugin path
    return reg
