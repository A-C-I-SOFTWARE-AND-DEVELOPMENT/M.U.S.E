"""Approval notification provider + pending queue (Sprint 9 core).

Sprint 9 needs a notification abstraction so approvals can reach a phone
(local SSE/poll, FCM, or UnifiedPush) without hard-coding any one provider,
plus a pending-approval queue the gateway can drive. This kernel defines:

* :class:`ApprovalNotification` — the payload a provider delivers (redaction
  is the caller's job before constructing it; this carries only a short
  summary + risk tier, never a diff or secret);
* :class:`NotificationProvider` — a runtime-checkable Protocol, so a local
  SSE provider satisfies it just as well as FCM/UnifiedPush — **Google
  services are not required**;
* :class:`PendingApprovalQueue` — a pure in-memory queue with idempotent
  enqueue, notified-tracking, and resolution.

Concrete providers and durable persistence are deliberate follow-ups; this
is the interface + queue and its tests.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Protocol, runtime_checkable

__all__ = [
    "ApprovalNotification",
    "NotificationProvider",
    "PendingApprovalQueue",
]


@dataclass(frozen=True)
class ApprovalNotification:
    """A bounded, deliverable approval alert. No diff/secret payload."""

    approval_id: str
    job_id: str
    summary: str
    risk_tier: str
    created_at: float
    notified: bool = False


@runtime_checkable
class NotificationProvider(Protocol):
    """A delivery channel for approval alerts.

    Implementations may be a local SSE/poll bridge, FCM, or UnifiedPush. The
    queue and gateway depend only on this Protocol, never a concrete provider.
    """

    def subscribe(self, device_id: str, endpoint: str) -> None:
        """Register a device endpoint to receive alerts."""
        ...

    def notify_approval(self, notification: ApprovalNotification) -> bool:
        """Deliver ``notification``; return True if accepted for delivery."""
        ...


class PendingApprovalQueue:
    """In-memory pending-approval queue keyed by ``approval_id``.

    Enqueue is idempotent — re-enqueuing the same ``approval_id`` returns
    ``False`` and does not overwrite — so a duplicate event never creates a
    second pending alert.
    """

    def __init__(self) -> None:
        self._items: dict[str, ApprovalNotification] = {}

    def enqueue(self, notification: ApprovalNotification) -> bool:
        """Add a notification. Returns True if newly added, False if duplicate."""

        if notification.approval_id in self._items:
            return False
        self._items[notification.approval_id] = notification
        return True

    def get(self, approval_id: str) -> Optional[ApprovalNotification]:
        return self._items.get(approval_id)

    def pending(self) -> list[ApprovalNotification]:
        """Notifications not yet marked delivered, in insertion order."""

        return [n for n in self._items.values() if not n.notified]

    def mark_notified(self, approval_id: str) -> bool:
        """Flag a notification delivered. Returns False if unknown."""

        item = self._items.get(approval_id)
        if item is None:
            return False
        self._items[approval_id] = replace(item, notified=True)
        return True

    def resolve(self, approval_id: str) -> bool:
        """Remove a decided approval from the queue. Returns False if unknown."""

        return self._items.pop(approval_id, None) is not None

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, approval_id: object) -> bool:
        return approval_id in self._items
