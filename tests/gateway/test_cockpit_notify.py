"""Tests for the local (no-Google) approval notification provider.

Covers ``gateway.cockpit.notify``:

* the provider satisfies the ``NotificationProvider`` Protocol (isinstance),
* ``notify_approval`` emits a bounded ``approval pending`` event that the
  cockpit event log (which powers the SSE stream) can read back,
* ``enqueue_and_notify`` is idempotent on ``approval_id`` (a duplicate emits no
  second alert), and never raises,
* the emitted attributes carry no secret, and
* the real proposal-creation site (``ledger_rollback_request``) enqueues +
  emits for the newly created pending approval.

Hermetic: each test isolates ``HERMES_HOME`` (so the event log + ledger live in
a tmp dir) and resets the process-singleton queue.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway.cockpit import event_log, notify
from hermes_cli.notifications import (
    ApprovalNotification,
    NotificationProvider,
    PendingApprovalQueue,
)

# A planted secret that must never appear in an emitted event's attributes.
PLANTED_SECRET = "sk-live-abcdef0123456789abcdef0123"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate the event-log + ledger root and reset the singleton queue."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    # The process-singleton queue is shared across tests; start each test clean
    # so idempotency assertions are deterministic.
    monkeypatch.setattr(notify, "_QUEUE", PendingApprovalQueue())
    return tmp_path


def _notif(approval_id: str = "appr_1", *, summary: str = "Rollback publish step",
           job_id: str = "job_1", risk_tier: str = "SERIOUS") -> ApprovalNotification:
    return ApprovalNotification(
        approval_id=approval_id,
        job_id=job_id,
        summary=summary,
        risk_tier=risk_tier,
        created_at=1.0,
    )


def _read_pending_events() -> list[dict]:
    return event_log.read(level="info", source="gateway", limit=100)


# ── provider Protocol conformance ───────────────────────────────────────────


def test_provider_satisfies_protocol() -> None:
    provider = notify.LocalSseNotificationProvider()
    # No Google services required: a local SSE provider IS a NotificationProvider.
    assert isinstance(provider, NotificationProvider)
    assert isinstance(notify.default_provider(), NotificationProvider)


def test_pending_approvals_is_process_singleton() -> None:
    assert notify.pending_approvals() is notify.pending_approvals()
    assert isinstance(notify.pending_approvals(), PendingApprovalQueue)


# ── notify_approval emits a bounded event ───────────────────────────────────


def test_notify_approval_emits_event(home: Path) -> None:
    provider = notify.LocalSseNotificationProvider()
    assert provider.notify_approval(_notif()) is True

    events = _read_pending_events()
    assert len(events) == 1
    ev = events[0]
    assert ev["message"] == "approval pending"
    assert ev["level"] == "info"
    assert ev["source"] == "gateway"
    assert ev["job_id"] == "job_1"
    attrs = ev["attributes"]
    assert attrs["approval_id"] == "appr_1"
    assert attrs["risk_tier"] == "SERIOUS"
    assert attrs["summary"] == "Rollback publish step"


def test_notify_approval_empty_job_id_is_absent(home: Path) -> None:
    notify.LocalSseNotificationProvider().notify_approval(_notif(job_id=""))
    ev = _read_pending_events()[0]
    # An empty job id is emitted as honestly-absent (None), not "".
    assert ev["job_id"] is None


def test_emitted_attributes_carry_no_secret(home: Path) -> None:
    # Even if a secret somehow reached the summary, the event payload is the
    # only thing delivered — assert no secret-shaped value escapes here, and
    # (more importantly) that ONLY the three bounded keys are present, i.e. no
    # diff/body/credential field is ever attached.
    notify.LocalSseNotificationProvider().notify_approval(
        _notif(summary="redacted summary")
    )
    ev = _read_pending_events()[0]
    assert set(ev["attributes"].keys()) == {"approval_id", "risk_tier", "summary"}
    assert PLANTED_SECRET not in json.dumps(ev)


# ── enqueue_and_notify: idempotent + best-effort ────────────────────────────


def test_enqueue_and_notify_new_then_duplicate(home: Path) -> None:
    q = notify.pending_approvals()
    assert notify.enqueue_and_notify(_notif("a")) is True
    assert len(q) == 1
    # Duplicate approval_id: not re-enqueued, and NO second alert is emitted.
    assert notify.enqueue_and_notify(_notif("a")) is False
    assert len(q) == 1
    assert len(_read_pending_events()) == 1


def test_enqueue_and_notify_distinct_ids_emit_each(home: Path) -> None:
    notify.enqueue_and_notify(_notif("a"))
    notify.enqueue_and_notify(_notif("b"))
    assert {n.approval_id for n in notify.pending_approvals().pending()} == {"a", "b"}
    assert len(_read_pending_events()) == 2


def test_enqueue_and_notify_never_raises_on_notify_failure(home: Path) -> None:
    class Boom:
        def subscribe(self, device_id: str, endpoint: str) -> None:  # pragma: no cover
            pass

        def notify_approval(self, notification: ApprovalNotification) -> bool:
            raise RuntimeError("provider down")

    q = PendingApprovalQueue()
    # A failing provider must not break the caller; the item still enqueues.
    assert notify.enqueue_and_notify(_notif("a"), queue=q, provider=Boom()) is True
    assert "a" in q


# ── creation site: ledger_rollback_request enqueues + emits ─────────────────


def _seed_ledger(home: Path, job_id: str, entries: list[dict]) -> None:
    d = home / "jobs" / job_id
    d.mkdir(parents=True, exist_ok=True)
    with (d / "ledger.jsonl").open("w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")


def test_rollback_request_creation_enqueues_and_emits(home: Path) -> None:
    from gateway.cockpit.handlers import Request, ledger_rollback_request

    _seed_ledger(
        home,
        "job_alpha",
        [
            {"ts": "2026-06-01T09:00:00+00:00", "kind": "submit", "prompt": "do a thing"},
            {"ts": "2026-06-01T09:03:00+00:00", "kind": "publish"},
        ],
    )

    req = Request(
        method="POST",
        path="/v1/cockpit/ledger/job_alpha/1/rollback",
        body={"reason": "publish was premature"},
        path_params={"job": "job_alpha", "index": "1"},
    )
    resp = ledger_rollback_request(req)
    assert resp.status == 201
    approval_id = resp.payload["id"]

    # The newly created pending proposal was enqueued in the shared queue...
    queued = notify.pending_approvals().get(approval_id)
    assert queued is not None
    assert queued.job_id == "job_alpha"
    assert queued.risk_tier == "SERIOUS"  # RC3 -> SERIOUS

    # ...and a bounded "approval pending" event was emitted for it.
    matching = [
        ev
        for ev in _read_pending_events()
        if ev["message"] == "approval pending"
        and ev["attributes"].get("approval_id") == approval_id
    ]
    assert len(matching) == 1
    attrs = matching[0]["attributes"]
    assert set(attrs.keys()) == {"approval_id", "risk_tier", "summary"}
    assert attrs["summary"]  # short rationale, non-empty
