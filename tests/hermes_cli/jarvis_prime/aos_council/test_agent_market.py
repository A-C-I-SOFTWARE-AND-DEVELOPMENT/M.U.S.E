"""Tests for hermes_cli.jarvis_prime.aos_council.agent_market."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.aos_council.agent_factory import (
    AgentSpec,
    create_agent,
)
from hermes_cli.jarvis_prime.aos_council.agent_market import (
    auction,
    extract_task_tags,
    record_outcome,
    reputation,
    score_agent,
)


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    return tmp_path / "registry.json"


@pytest.fixture
def outcomes(tmp_path: Path) -> Path:
    return tmp_path / "outcomes.jsonl"


def _mk(name: str, caps: list[str], cost: float = 0.0) -> AgentSpec:
    return AgentSpec(
        name=name,
        capabilities=caps,
        model="m",
        cost_per_1k_input=cost,
        cost_per_1k_output=cost,
    )


# ---------------------------------------------------------------------------
# reputation
# ---------------------------------------------------------------------------


def test_reputation_no_data_returns_prior(outcomes: Path) -> None:
    assert reputation("nobody", outcomes_path=outcomes) == 0.5


def test_reputation_all_wins_approaches_one(outcomes: Path) -> None:
    for i in range(10):
        record_outcome("a", f"t{i}", True, outcomes_path=outcomes)
    rep = reputation("a", outcomes_path=outcomes)
    assert rep > 0.8


def test_reputation_all_losses_approaches_zero(outcomes: Path) -> None:
    for i in range(10):
        record_outcome("a", f"t{i}", False, outcomes_path=outcomes)
    rep = reputation("a", outcomes_path=outcomes)
    assert rep < 0.2


def test_reputation_mixed_is_middle(outcomes: Path) -> None:
    for i in range(5):
        record_outcome("a", f"w{i}", True, outcomes_path=outcomes)
        record_outcome("a", f"l{i}", False, outcomes_path=outcomes)
    rep = reputation("a", outcomes_path=outcomes)
    assert 0.4 < rep < 0.6


# ---------------------------------------------------------------------------
# extract_task_tags
# ---------------------------------------------------------------------------


def test_extract_task_tags_picks_up_known_vocab() -> None:
    tags = extract_task_tags("Fix the Python bug in the API endpoint")
    assert "python" in tags
    assert "api" in tags


def test_extract_task_tags_action_words() -> None:
    tags = extract_task_tags("Debug and refactor the code")
    assert "debug" in tags
    assert "refactor" in tags
    assert "code" in tags


def test_extract_task_tags_defaults_to_general() -> None:
    tags = extract_task_tags("xyzzy plugh foobar")
    assert "general" in tags


# ---------------------------------------------------------------------------
# score_agent
# ---------------------------------------------------------------------------


def test_score_agent_capability_match_dominates(outcomes: Path) -> None:
    good = _mk("good", ["python", "debug"])
    bad = _mk("bad", ["rust", "cargo"])
    task = "Debug the python script"
    assert score_agent(good, task, outcomes) > score_agent(bad, task, outcomes)


def test_score_agent_cost_efficiency_penalizes_expensive(outcomes: Path) -> None:
    free = _mk("free", ["python"], cost=0.0)
    expensive = _mk("exp", ["python"], cost=0.5)
    task = "python work"
    assert score_agent(free, task, outcomes) > score_agent(expensive, task, outcomes)


def test_score_agent_reputation_matters(outcomes: Path) -> None:
    agent = _mk("a", ["python"])
    task = "python work"
    score_before = score_agent(agent, task, outcomes)
    for i in range(10):
        record_outcome(agent.agent_id, f"t{i}", True, outcomes_path=outcomes)
    score_after = score_agent(agent, task, outcomes)
    assert score_after > score_before


# ---------------------------------------------------------------------------
# auction
# ---------------------------------------------------------------------------


def test_auction_picks_best_match(registry: Path, outcomes: Path) -> None:
    py_agent = _mk("py", ["python", "debug"])
    rust_agent = _mk("rs", ["rust", "cargo"])
    create_agent(py_agent, registry_path=registry)
    create_agent(rust_agent, registry_path=registry)

    result = auction(
        "Debug the python script",
        registry_path=registry,
        outcomes_path=outcomes,
    )
    assert result is not None
    assert result.winner_id == py_agent.agent_id


def test_auction_returns_none_when_no_candidates(registry: Path, outcomes: Path) -> None:
    result = auction("anything", registry_path=registry, outcomes_path=outcomes)
    assert result is None


def test_auction_respects_candidate_filter(registry: Path, outcomes: Path) -> None:
    a = _mk("a", ["python"])
    b = _mk("b", ["rust"])
    create_agent(a, registry_path=registry)
    create_agent(b, registry_path=registry)

    result = auction(
        "python work",
        candidate_ids=[b.agent_id],  # exclude the python agent
        registry_path=registry,
        outcomes_path=outcomes,
    )
    assert result is not None
    assert result.winner_id == b.agent_id


def test_auction_champion_gate_holds_when_challenger_weak(
    registry: Path, outcomes: Path
) -> None:
    champion = _mk("champ", ["python"])
    challenger = _mk("chall", ["python"])
    create_agent(champion, registry_path=registry)
    create_agent(challenger, registry_path=registry)

    # Build up champion reputation so it clearly wins
    for i in range(10):
        record_outcome(champion.agent_id, f"t{i}", True, outcomes_path=outcomes)

    result = auction(
        "python work",
        registry_path=registry,
        outcomes_path=outcomes,
        champion_id=champion.agent_id,
        win_margin=0.55,
    )
    assert result is not None
    # Champion has more reputation, so it should hold
    assert result.winner_id == champion.agent_id
    assert result.champion_displaced is False


def test_auction_champion_displaced_by_strong_challenger(
    registry: Path, outcomes: Path
) -> None:
    champion = _mk("champ", ["general"])  # weak match
    challenger = _mk("chall", ["python", "debug"])  # strong match
    create_agent(champion, registry_path=registry)
    create_agent(challenger, registry_path=registry)

    result = auction(
        "Debug the python script",
        registry_path=registry,
        outcomes_path=outcomes,
        champion_id=champion.agent_id,
        win_margin=0.05,  # low bar — easy to displace
    )
    assert result is not None
    assert result.winner_id == challenger.agent_id
    assert result.champion_displaced is True
