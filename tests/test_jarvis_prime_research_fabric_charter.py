"""Tests for the Autonomy Charter — owner-signed, revocable, budgeted, walled."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hermes_cli.jarvis_prime.owner_auth import authorize_challenge, create_challenge
from hermes_cli.jarvis_prime.self_update import ProposalKind
from hermes_cli.jarvis_prime.research_fabric.charter import (
    CharterBook,
    CharterRejected,
    HARD_WALL_KINDS,
    is_hard_walled,
)


def _grant():
    ch = create_challenge("grant_autonomy_charter", risk_class="RC3")
    grant = authorize_challenge(ch, ch.required_phrase)
    assert grant is not None
    return grant


def test_bare_phrase_does_not_authorize_charter() -> None:
    ch = create_challenge("grant_autonomy_charter")
    # The bare static phrase (no nonce) must NOT authorize.
    assert authorize_challenge(ch, "Yes, with authorization.") is None
    # The exact nonce-bound phrase does.
    assert authorize_challenge(ch, ch.required_phrase) is not None


def test_grant_creates_active_charter(tmp_path) -> None:
    book = CharterBook(path=tmp_path / "charters.jsonl")
    charter = book.grant(
        allowed_kinds=("skill_update",),
        risk_band_ceiling="RC2",
        per_window_budget=3,
        window_seconds=86400,
        ttl_seconds=3600,
        grant=_grant(),
        persist=False,
    )
    assert charter.is_active() is True
    assert book.active() is not None


def test_grant_rejects_hard_walled_kinds(tmp_path) -> None:
    book = CharterBook(path=tmp_path / "charters.jsonl")
    with pytest.raises(CharterRejected):
        book.grant(
            allowed_kinds=("self_runtime_update",),  # hard-walled
            risk_band_ceiling="RC2",
            per_window_budget=1,
            window_seconds=86400,
            ttl_seconds=3600,
            grant=_grant(),
            persist=False,
        )


def test_grant_rejects_rc4_ceiling(tmp_path) -> None:
    book = CharterBook(path=tmp_path / "charters.jsonl")
    with pytest.raises(CharterRejected):
        book.grant(
            allowed_kinds=("skill_update",),
            risk_band_ceiling="RC4",
            per_window_budget=1,
            window_seconds=86400,
            ttl_seconds=3600,
            grant=_grant(),
            persist=False,
        )


def test_revoke_makes_charter_inactive(tmp_path) -> None:
    book = CharterBook(path=tmp_path / "charters.jsonl")
    charter = book.grant(
        allowed_kinds=("skill_update",),
        risk_band_ceiling="RC2",
        per_window_budget=3,
        window_seconds=86400,
        ttl_seconds=3600,
        grant=_grant(),
        persist=True,
    )
    assert book.revoke(charter.charter_id) is True
    assert book.active() is None


def test_expiry_makes_charter_inactive(tmp_path) -> None:
    book = CharterBook(path=tmp_path / "charters.jsonl")
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    charter = book.grant(
        allowed_kinds=("skill_update",),
        risk_band_ceiling="RC2",
        per_window_budget=3,
        window_seconds=86400,
        ttl_seconds=1,
        grant=_grant(),
        now=past,
        persist=False,
    )
    assert charter.is_active() is False
    assert book.active() is None


def test_permits_scope_and_ceiling(tmp_path) -> None:
    book = CharterBook(path=tmp_path / "charters.jsonl")
    charter = book.grant(
        allowed_kinds=("skill_update",),
        risk_band_ceiling="RC2",
        per_window_budget=3,
        window_seconds=86400,
        ttl_seconds=3600,
        grant=_grant(),
        persist=False,
    )
    ok, _ = charter.permits(ProposalKind.SKILL_UPDATE, "RC1")
    assert ok is True
    # Out of scope kind.
    ok2, _ = charter.permits(ProposalKind.NEW_SKILL, "RC1")
    assert ok2 is False
    # Over ceiling.
    ok3, _ = charter.permits(ProposalKind.SKILL_UPDATE, "RC3")
    assert ok3 is False


def test_persistence_round_trips(tmp_path) -> None:
    path = tmp_path / "charters.jsonl"
    book = CharterBook(path=path)
    book.grant(
        allowed_kinds=("skill_update",),
        risk_band_ceiling="RC2",
        per_window_budget=3,
        window_seconds=86400,
        ttl_seconds=3600,
        grant=_grant(),
        persist=True,
    )
    reloaded = CharterBook.load(path)
    assert reloaded.active() is not None


def test_hard_wall_helpers() -> None:
    assert ProposalKind.SELF_RUNTIME_UPDATE in HARD_WALL_KINDS
    walled, _ = is_hard_walled(ProposalKind.SKILL_UPDATE, "hermes_cli/jarvis_prime/gates.py")
    assert walled is True  # protected path
    walled2, _ = is_hard_walled(ProposalKind.SKILL_UPDATE, "skills/foo/SKILL.md")
    assert walled2 is False
