"""Tests for the MUSE Prime effort-class (E0–E5) routing taxonomy.

Covers ``hermes_cli.jarvis_prime.effort_class`` (the pure classifier + caps)
and its stamping onto ``RouteDecision`` and the per-turn ``JarvisTurn`` trace.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.effort_class import (
    EffortClass,
    cap_council_size,
    classify_effort,
    max_council_size,
)
from hermes_cli.jarvis_prime.memory import MemoryStore
from hermes_cli.jarvis_prime.memory_tree import MemoryTreeStore
from hermes_cli.jarvis_prime.modes import Mode
from hermes_cli.jarvis_prime.router import RouteDecision, RouteTarget, Router
from hermes_cli.jarvis_prime.runtime import JarvisConfig, JarvisPrime


# ---------------------------------------------------------------------------
# Pure classifier: representative signals → expected class
# ---------------------------------------------------------------------------


def _decision(
    target: RouteTarget,
    *,
    delegate_to: str | None = None,
    owner: bool = False,
) -> RouteDecision:
    return RouteDecision(
        target=target,
        rationale="test",
        delegate_to=delegate_to,
        requires_owner_authorization=owner,
    )


def test_direct_answer_is_e0() -> None:
    assert classify_effort(_decision(RouteTarget.DIRECT_ANSWER)) is EffortClass.E0


def test_defer_and_owner_decision_are_e0() -> None:
    assert (
        classify_effort(_decision(RouteTarget.DEFER_TO_FOCUSED_MODE))
        is EffortClass.E0
    )
    assert classify_effort(_decision(RouteTarget.OWNER_DECISION)) is EffortClass.E0


def test_single_specialist_lens_is_e1() -> None:
    d = _decision(RouteTarget.SPECIALIST, delegate_to="hazmat-command-specialist")
    assert classify_effort(d) is EffortClass.E1


def test_single_skill_lens_is_e1() -> None:
    assert classify_effort(_decision(RouteTarget.SKILL)) is EffortClass.E1


def test_full_council_is_e3() -> None:
    d = _decision(RouteTarget.AOS_COUNCIL, delegate_to="aos-council-director")
    assert classify_effort(d) is EffortClass.E3


def test_deep_build_run_is_e4() -> None:
    for target in (
        RouteTarget.CLAUDE_CODE_BUILDER,
        RouteTarget.CODEX_REVIEWER,
        RouteTarget.CODEX_BOUNDED_FIX,
        RouteTarget.LOCAL_TEST_RUNNER,
        RouteTarget.GITHUB_PR_PUBLISHER,
    ):
        assert classify_effort(_decision(target)) is EffortClass.E4


def test_owner_gated_swarm_is_e5() -> None:
    d = _decision(
        RouteTarget.SKILL, delegate_to="research-fabric", owner=True
    )
    assert classify_effort(d) is EffortClass.E5


def test_swarm_requires_owner_gate_else_downgrades() -> None:
    # Same swarm target/delegate but WITHOUT the owner-authorization signal
    # must NOT be classified E5 — E5 reuses the existing owner gate.
    d = _decision(
        RouteTarget.SKILL, delegate_to="research-fabric", owner=False
    )
    assert classify_effort(d) is not EffortClass.E5
    assert classify_effort(d) is EffortClass.E1  # falls back to single-lens


# ---------------------------------------------------------------------------
# Smallest-sufficient default / soft council cap
# ---------------------------------------------------------------------------


def test_council_size_ceilings() -> None:
    assert max_council_size(EffortClass.E0) == 0
    assert max_council_size(EffortClass.E1) == 1
    assert max_council_size(EffortClass.E2) == 3
    assert max_council_size(EffortClass.E3) == 7
    assert max_council_size(EffortClass.E4) is None
    assert max_council_size(EffortClass.E5) is None


def test_cap_council_size_clamps_down_never_up() -> None:
    # E2 permits at most 3; a request for 6 is clamped to 3.
    assert cap_council_size(EffortClass.E2, 6) == 3
    # A request that already fits is unchanged.
    assert cap_council_size(EffortClass.E2, 2) == 2
    # E1 permits exactly one lens.
    assert cap_council_size(EffortClass.E1, 5) == 1
    # E0 permits no council at all.
    assert cap_council_size(EffortClass.E0, 4) == 0
    # E4/E5 impose no council ceiling (execution runs).
    assert cap_council_size(EffortClass.E4, 9) == 9
    # Negative requests are floored at zero.
    assert cap_council_size(EffortClass.E3, -2) == 0


def test_effort_class_rank_orders_ladder() -> None:
    ranks = [c.rank for c in (
        EffortClass.E0,
        EffortClass.E1,
        EffortClass.E2,
        EffortClass.E3,
        EffortClass.E4,
        EffortClass.E5,
    )]
    assert ranks == [0, 1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Stamping: RouteDecision + serialization
# ---------------------------------------------------------------------------


def test_router_stamps_effort_class_on_every_decision() -> None:
    router = Router()
    cases = {
        (Mode.COMPANION, "I had a rough day"): "E0",
        (Mode.OPERATOR, "what's the next task"): "E0",
        (Mode.CRITIC, "tear it apart"): "E1",
        (Mode.OPERATOR, "review the 49 cfr placarding hazmat shipping papers"): "E1",
        (Mode.STRATEGY, "should we change positioning"): "E3",
        (Mode.BUILDER, "implement the new parser"): "E4",
    }
    for (mode, intent), expected in cases.items():
        decision = router.route(mode=mode, intent=intent)
        assert decision.effort_class == expected, (mode, intent)
        # Serialisation surfaces the stamp.
        assert decision.to_dict()["effort_class"] == expected


def test_router_stamps_e5_for_owner_gated_swarm() -> None:
    router = Router()
    decision = router.route(mode=Mode.BUILDER, intent="self-improve your own code")
    assert decision.target == RouteTarget.SKILL
    assert decision.delegate_to == "research-fabric"
    assert decision.requires_owner_authorization is True
    assert decision.effort_class == "E5"


def test_route_decision_to_dict_includes_effort_class_key() -> None:
    router = Router()
    payload = router.route(mode=Mode.STRATEGY, intent="strategy").to_dict()
    assert "effort_class" in payload
    assert payload["effort_class"] == "E3"


# ---------------------------------------------------------------------------
# Stamping: JarvisTurn trace record
# ---------------------------------------------------------------------------


@pytest.fixture
def jp(tmp_path: Path) -> JarvisPrime:
    config = JarvisConfig(
        memory=MemoryStore(journal_path=tmp_path / "memory.jsonl"),
        memory_tree=MemoryTreeStore(path=tmp_path / "memory_tree.jsonl"),
    )
    return JarvisPrime(config=config)


def test_turn_stamps_effort_class_field_and_trace(jp: JarvisPrime) -> None:
    turn = jp.handle("implement the new parser", skip_perceive=True)
    # First-class field on the trace mirrors the routing decision.
    assert turn.effort_class == turn.route.effort_class
    assert turn.effort_class is not None
    # Observable in the serialised trace.
    payload = turn.to_dict()
    assert payload["effort_class"] == turn.effort_class
    assert payload["route"]["effort_class"] == turn.effort_class


def test_delegation_envelope_carries_effort_class(jp: JarvisPrime) -> None:
    decision = jp.decide(mode=Mode.STRATEGY, intent="should we change positioning")
    envelope = jp.delegate(decision)
    assert envelope["effort_class"] == decision.effort_class == "E3"
