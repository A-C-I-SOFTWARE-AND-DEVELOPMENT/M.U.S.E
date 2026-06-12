"""Tests for the alignment monitor / tripwires."""

from __future__ import annotations

from muse_cli.jarvis_prime.guardrail_evidence import GuardrailLedger
from muse_cli.jarvis_prime.owner_auth import authorize_challenge, create_challenge
from muse_cli.jarvis_prime.research_fabric.charter import CharterBook
from muse_cli.jarvis_prime.research_fabric.monitor import (
    AlignmentMonitor,
    TripwireSignal,
)


def _book_with_active(tmp_path) -> CharterBook:
    book = CharterBook(path=tmp_path / "charters.jsonl")
    ch = create_challenge("grant_autonomy_charter", risk_class="RC3")
    grant = authorize_challenge(ch, ch.required_phrase)
    book.grant(
        allowed_kinds=("skill_update",),
        risk_band_ceiling="RC2",
        per_window_budget=3,
        window_seconds=86400,
        ttl_seconds=3600,
        grant=grant,  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture
        persist=False,
    )
    return book


def test_no_signal_does_not_trip(tmp_path) -> None:
    ledger = GuardrailLedger(tmp_path / "l.jsonl")
    book = _book_with_active(tmp_path)
    mon = AlignmentMonitor(ledger=ledger, charter_book=book)
    res = mon.check([])
    assert res.tripped is False
    assert book.active() is not None


def test_monitor_tampering_revokes_charter_and_halts(tmp_path) -> None:
    ledger = GuardrailLedger(tmp_path / "l.jsonl")
    book = _book_with_active(tmp_path)
    mon = AlignmentMonitor(ledger=ledger, charter_book=book)
    res = mon.check(
        [TripwireSignal(kind="monitor_tampering", detail="edited the monitor")]
    )
    assert res.tripped is True
    assert len(res.revoked_charters) == 1
    assert book.active() is None
    assert "tripwire" in [r.kind for r in ledger.read_all()]


def test_unknown_signal_kind_is_ignored(tmp_path) -> None:
    ledger = GuardrailLedger(tmp_path / "l.jsonl")
    book = _book_with_active(tmp_path)
    mon = AlignmentMonitor(ledger=ledger, charter_book=book)
    res = mon.check([TripwireSignal(kind="not_a_real_tripwire", detail="noise")])
    assert res.tripped is False
    assert book.active() is not None
