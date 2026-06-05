"""Local (no-Google) approval notification provider + process queue.

This wires the provider-agnostic kernel in :mod:`hermes_cli.notifications`
(``ApprovalNotification`` / ``NotificationProvider`` / ``PendingApprovalQueue``)
to the cockpit's existing append-only event log. A pending approval is
delivered by emitting one bounded ``CockpitEvent`` — which the live
``GET /v1/cockpit/events`` + SSE stream already surfaces to a phone, with
**no Firebase / FCM / Google services required**.

What this module adds:

* :class:`LocalSseNotificationProvider` — a concrete
  :class:`~hermes_cli.notifications.NotificationProvider` whose
  ``notify_approval`` calls ``event_log.emit(...)``. The payload carries only
  ``approval_id`` / ``risk_tier`` / ``summary`` (the summary is already bounded
  by the caller) — never a diff, body, or secret.
* :func:`pending_approvals` — a process-singleton ``PendingApprovalQueue`` so
  every emitter shares one idempotent queue.
* :func:`enqueue_and_notify` — enqueue (idempotent) then notify, best-effort:
  it never raises into the caller, so a notification failure can never break
  the action (e.g. proposal creation) that emitted it.

Subscription is a deliberate no-op for the local-SSE channel: there is no
per-device push endpoint to register — every authorized client tails the same
event stream — so ``subscribe`` exists only to satisfy the Protocol.
"""

from __future__ import annotations

from hermes_cli.notifications import (
    ApprovalNotification,
    NotificationProvider,
    PendingApprovalQueue,
)

from . import event_log

__all__ = [
    "LocalSseNotificationProvider",
    "pending_approvals",
    "default_provider",
    "enqueue_and_notify",
]


class LocalSseNotificationProvider:
    """Deliver approval alerts over the cockpit event log (local SSE / poll).

    Implements the :class:`~hermes_cli.notifications.NotificationProvider`
    Protocol. No Google services: delivery is a single best-effort
    ``event_log.emit`` that the existing ``/v1/cockpit/events`` stream picks up.
    """

    def subscribe(self, device_id: str, endpoint: str) -> None:
        """No-op for the local SSE channel.

        Local SSE has no per-device push endpoint to register — every
        authorized client tails the shared event stream — so this method exists
        only to satisfy the Protocol.
        """
        return None

    def notify_approval(self, notification: ApprovalNotification) -> bool:
        """Emit a bounded ``approval pending`` event. Returns True if accepted.

        The attributes carry only the approval id, risk tier, and the already
        bounded summary — never a diff, request body, or secret. ``event_log``
        is best-effort and swallows its own errors; we still return True to mean
        "accepted for delivery" (the stream is the delivery channel).
        """
        # Empty job ids become ``None`` so the event's ``job_id`` is honestly
        # absent rather than an empty string.
        job_id = notification.job_id or None
        event_log.emit(
            "info",
            "gateway",
            "approval pending",
            job_id=job_id,
            attributes={
                "approval_id": notification.approval_id,
                "risk_tier": notification.risk_tier,
                "summary": notification.summary,
            },
        )
        return True


# Process-singleton queue + provider. The queue is in-memory by design (durable
# persistence is a documented follow-up in hermes_cli.notifications); a single
# instance per process keeps enqueue idempotency meaningful across emitters.
_QUEUE: PendingApprovalQueue = PendingApprovalQueue()
_PROVIDER: LocalSseNotificationProvider = LocalSseNotificationProvider()


def pending_approvals() -> PendingApprovalQueue:
    """The shared, process-wide pending-approval queue."""
    return _QUEUE


def default_provider() -> NotificationProvider:
    """The shared local-SSE notification provider for this process."""
    return _PROVIDER


def enqueue_and_notify(
    notification: ApprovalNotification,
    *,
    queue: PendingApprovalQueue | None = None,
    provider: NotificationProvider | None = None,
) -> bool:
    """Enqueue ``notification`` (idempotent) then notify. Best-effort.

    Returns True when the notification was *newly* enqueued (and thus a fresh
    alert was emitted), False when it was a duplicate ``approval_id`` (already
    pending — no second alert). Never raises: a queue/notify failure must not
    break the action that created the approval.
    """
    q = queue if queue is not None else _QUEUE
    p = provider if provider is not None else _PROVIDER
    try:
        newly_added = q.enqueue(notification)
    except Exception:  # pragma: no cover - defensive; queue must not break caller
        return False
    if not newly_added:
        # Duplicate approval_id: already pending, don't emit a second alert.
        return False
    try:
        p.notify_approval(notification)
    except Exception:  # pragma: no cover - defensive; notify must not break caller
        pass
    return True
