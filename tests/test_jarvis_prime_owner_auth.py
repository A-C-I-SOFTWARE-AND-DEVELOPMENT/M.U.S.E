"""Tests for muse_cli.jarvis_prime.owner_auth — exact-phrase enforcement."""

from __future__ import annotations

import pytest

from muse_cli.jarvis_prime.owner_auth import (
    AUTHORIZATION_PHRASE,
    OWNER_GATED_ACTIONS,
    OwnerAuth,
)


def test_authorization_phrase_is_canonical_constant() -> None:
    assert AUTHORIZATION_PHRASE == "Yes, with authorization."


def test_owner_gated_actions_includes_known_categories() -> None:
    for action in (
        "spend_money", "production_deploy", "package_publish",
        "credential_change", "regulated_claim",
    ):
        assert action in OWNER_GATED_ACTIONS


def test_main_branch_merge_is_not_owner_gated() -> None:
    # Repository merge approval is governed by the automated LaunchGate
    # policy — see docs/launch/AUTOMATED_MERGE_POLICY.md — not by the
    # runtime owner phrase. Runtime owner gates remain in place for the
    # destructive actions enumerated in OWNER_GATED_ACTIONS.
    assert "main_branch_merge" not in OWNER_GATED_ACTIONS


def test_request_unknown_action_raises() -> None:
    auth = OwnerAuth()
    with pytest.raises(ValueError):
        auth.request("eat_the_repo")


def test_request_main_branch_merge_now_rejected() -> None:
    # main_branch_merge is no longer a runtime owner gate; requesting
    # it as one must raise so callers don't silently bypass LaunchGate.
    auth = OwnerAuth()
    with pytest.raises(ValueError):
        auth.request("main_branch_merge")


def test_request_then_no_authorize_means_no_grant() -> None:
    auth = OwnerAuth()
    auth.request("production_deploy", risk_class="RC2", rationale="ship hot fix")
    assert auth.pending_actions() == ["production_deploy"]
    granted = auth.authorize("go for it")
    assert granted == []
    assert auth.pending_actions() == ["production_deploy"]


def test_exact_phrase_grants_authorization() -> None:
    auth = OwnerAuth()
    auth.request("production_deploy", rationale="ship")
    granted = auth.authorize(AUTHORIZATION_PHRASE)
    assert len(granted) == 1
    assert granted[0].action == "production_deploy"
    assert granted[0].authorized
    assert auth.pending_actions() == []


def test_phrase_variations_do_not_authorize() -> None:
    auth = OwnerAuth()
    auth.request("production_deploy", rationale="ship")
    for variant in (
        "yes, with authorization.",     # lowercase
        "Yes with authorization",        # no comma
        "Yes, with authorization",       # no period
        "yes",
        "approved",
        "go ahead",
        "lgtm",
    ):
        assert auth.authorize(variant) == []
    # The pending action is still there because no variant matched.
    assert auth.pending_actions() == ["production_deploy"]


def test_authorize_targeted_to_one_action() -> None:
    auth = OwnerAuth()
    auth.request("production_deploy", rationale="ship")
    auth.request("package_publish", rationale="release")
    granted = auth.authorize(AUTHORIZATION_PHRASE, action="package_publish")
    assert [g.action for g in granted] == ["package_publish"]
    assert auth.pending_actions() == ["production_deploy"]


def test_history_preserves_authorized_gates() -> None:
    auth = OwnerAuth()
    auth.request("production_deploy", rationale="hot fix")
    auth.authorize(AUTHORIZATION_PHRASE)
    assert len(auth.history) == 1
    assert auth.history[0].action == "production_deploy"
    assert auth.history[0].authorized


def test_revoke_clears_authorization() -> None:
    auth = OwnerAuth()
    auth.request("oauth_change", rationale="rotate")
    auth.authorize(AUTHORIZATION_PHRASE)
    revoked = auth.revoke("oauth_change")
    assert revoked == 1
    # History entry still exists but no longer "authorized".
    assert not auth.history[0].authorized


def test_is_gated_action_helper() -> None:
    assert OwnerAuth.is_gated_action("production_deploy") is True
    assert OwnerAuth.is_gated_action("write_a_comment") is False
