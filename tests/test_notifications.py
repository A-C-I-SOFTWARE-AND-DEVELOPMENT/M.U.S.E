"""Tests for the approval notification provider + pending queue (Sprint 9)."""

from __future__ import annotations

from hermes_cli.notifications import (
    ApprovalNotification,
    NotificationProvider,
    PendingApprovalQueue,
)


def _notif(approval_id: str = "appr_1", *, created_at: float = 1.0) -> ApprovalNotification:
    return ApprovalNotification(
        approval_id=approval_id,
        job_id="job_1",
        summary="Create PR from validated patch",
        risk_tier="ask",
        created_at=created_at,
    )


def test_enqueue_new_then_duplicate():
    q = PendingApprovalQueue()
    assert q.enqueue(_notif()) is True
    assert q.enqueue(_notif()) is False  # idempotent on approval_id
    assert len(q) == 1


def test_enqueue_does_not_overwrite_on_duplicate():
    q = PendingApprovalQueue()
    q.enqueue(_notif(created_at=1.0))
    q.enqueue(ApprovalNotification("appr_1", "job_1", "DIFFERENT", "refuse", 99.0))
    item = q.get("appr_1")
    assert item is not None
    assert item.summary == "Create PR from validated patch"
    assert item.created_at == 1.0


def test_pending_excludes_notified():
    q = PendingApprovalQueue()
    q.enqueue(_notif("a"))
    q.enqueue(_notif("b"))
    assert {n.approval_id for n in q.pending()} == {"a", "b"}
    q.mark_notified("a")
    assert [n.approval_id for n in q.pending()] == ["b"]


def test_mark_notified_unknown_returns_false():
    q = PendingApprovalQueue()
    assert q.mark_notified("nope") is False


def test_resolve_removes():
    q = PendingApprovalQueue()
    q.enqueue(_notif("a"))
    assert "a" in q
    assert q.resolve("a") is True
    assert "a" not in q
    assert q.resolve("a") is False  # already gone


def test_get_returns_none_for_unknown():
    assert PendingApprovalQueue().get("missing") is None


def test_pending_preserves_insertion_order():
    q = PendingApprovalQueue()
    for i in range(5):
        q.enqueue(_notif(f"a{i}", created_at=float(i)))
    assert [n.approval_id for n in q.pending()] == [f"a{i}" for i in range(5)]


def test_runtime_checkable_protocol():
    class LocalSseProvider:
        def __init__(self):
            self.sent = []

        def subscribe(self, device_id: str, endpoint: str) -> None:
            pass

        def notify_approval(self, notification: ApprovalNotification) -> bool:
            self.sent.append(notification.approval_id)
            return True

    provider = LocalSseProvider()
    assert isinstance(provider, NotificationProvider)  # no Google services needed
    assert provider.notify_approval(_notif()) is True
    assert provider.sent == ["appr_1"]


def test_incomplete_provider_is_not_instance():
    class Broken:
        def subscribe(self, device_id: str, endpoint: str) -> None:
            pass

        # missing notify_approval

    assert not isinstance(Broken(), NotificationProvider)
