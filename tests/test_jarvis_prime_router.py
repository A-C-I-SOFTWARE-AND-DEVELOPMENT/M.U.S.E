"""Tests for muse_cli.jarvis_prime.router — routing hierarchy."""

from __future__ import annotations

from muse_cli.jarvis_prime.modes import Mode
from muse_cli.jarvis_prime.router import RouteTarget, Router


def test_owner_pending_action_routes_to_owner_decision() -> None:
    router = Router()
    decision = router.route(
        mode=Mode.BUILDER,
        intent="publish v0.14.1-aci.1",
        pending_owner_actions=("package_publish",),
    )
    assert decision.target == RouteTarget.OWNER_DECISION
    assert decision.requires_owner_authorization is True


def test_mobile_voice_defers_to_focused_mode() -> None:
    router = Router()
    decision = router.route(mode=Mode.MOBILE_VOICE, intent="quick idea")
    assert decision.target == RouteTarget.DEFER_TO_FOCUSED_MODE


def test_builder_routes_to_claude_code_by_default() -> None:
    router = Router()
    decision = router.route(mode=Mode.BUILDER, intent="implement the new parser")
    assert decision.target == RouteTarget.CLAUDE_CODE_BUILDER
    assert decision.delegate_to == "claude-code-builder"


def test_builder_review_intent_routes_to_codex() -> None:
    router = Router()
    decision = router.route(mode=Mode.BUILDER, intent="please review this diff")
    assert decision.target == RouteTarget.CODEX_REVIEWER


def test_builder_test_intent_routes_to_local_test_runner() -> None:
    router = Router()
    decision = router.route(mode=Mode.BUILDER, intent="run pytest")
    assert decision.target == RouteTarget.LOCAL_TEST_RUNNER


def test_builder_pr_intent_routes_to_publisher_without_owner_gate() -> None:
    # Opening a PR no longer requires the owner phrase. The merge itself
    # is governed by LaunchGate (docs/launch/AUTOMATED_MERGE_POLICY.md).
    router = Router()
    decision = router.route(mode=Mode.BUILDER, intent="open a pull request")
    assert decision.target == RouteTarget.GITHUB_PR_PUBLISHER
    assert decision.requires_owner_authorization is False
    assert "main_branch_merge" not in decision.pending_actions


def test_builder_rollback_routes_to_bounded_fix() -> None:
    router = Router()
    decision = router.route(mode=Mode.BUILDER, intent="rollback that change")
    assert decision.target == RouteTarget.CODEX_BOUNDED_FIX


def test_critic_routes_to_contrarian_reviewer() -> None:
    router = Router()
    decision = router.route(mode=Mode.CRITIC, intent="tear it apart")
    assert decision.target == RouteTarget.SPECIALIST
    assert decision.delegate_to == "contrarian-reviewer"


def test_operator_council_trigger_routes_to_council() -> None:
    router = Router()
    decision = router.route(
        mode=Mode.OPERATOR,
        intent="we need a security review and a release readiness check",
    )
    assert decision.target == RouteTarget.AOS_COUNCIL
    assert len(decision.council_questions) >= 1


def test_operator_specialist_domain_routes_to_specialist() -> None:
    router = Router()
    decision = router.route(
        mode=Mode.OPERATOR,
        intent="review the 49 CFR placarding for the hazmat shipping papers",
    )
    assert decision.target == RouteTarget.SPECIALIST
    assert decision.delegate_to == "hazmat-command-specialist"


def test_operator_nutrition_routes_to_nourish_specialist() -> None:
    router = Router()
    decision = router.route(
        mode=Mode.OPERATOR,
        intent="add a recipe and update the nutrition data and nutrient math",
    )
    assert decision.delegate_to == "nourish-product-specialist"


def test_operator_no_trigger_direct_answer() -> None:
    router = Router()
    decision = router.route(mode=Mode.OPERATOR, intent="what's the next task")
    assert decision.target == RouteTarget.DIRECT_ANSWER


def test_strategy_routes_to_council() -> None:
    router = Router()
    decision = router.route(mode=Mode.STRATEGY, intent="should we change positioning")
    assert decision.target == RouteTarget.AOS_COUNCIL


def test_companion_direct_answer() -> None:
    router = Router()
    decision = router.route(mode=Mode.COMPANION, intent="I'm having a rough day")
    assert decision.target == RouteTarget.DIRECT_ANSWER


def test_route_decision_serializes() -> None:
    router = Router()
    decision = router.route(mode=Mode.STRATEGY, intent="strategy")
    payload = decision.to_dict()
    assert payload["target"] == RouteTarget.AOS_COUNCIL.value
    assert isinstance(payload["council_questions"], list)
