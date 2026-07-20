"""Agent Market — capability-based hiring + simple auction.

Replaces the static keyword-overlap scoring in the AoS dispatcher with a
capability-aware auction. Agents are scored on:

    score = capability_match * reputation * cost_efficiency

Where:
    capability_match ∈ [0,1]  — Jaccard overlap of agent.capabilities vs task tags
    reputation       ∈ [0,1]  — Beta-distribution posterior from past outcomes
    cost_efficiency  ∈ (0,1]  — 1 / (1 + normalized_cost)

The auction picks the highest scorer, with an EVAL_WIN_MARGIN=0.55 head-to-head
gate when a reigning champion exists (matches the research_fabric ratchet).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from hermes_cli.jarvis_prime.aos_council.agent_factory import (
    AgentSpec,
    default_registry_path,
    list_agents,
)

__all__ = [
    "score_agent",
    "auction",
    "record_outcome",
    "reputation",
    "extract_task_tags",
    "AuctionResult",
]


# ---------------------------------------------------------------------------
# Reputation store (append-only JSONL)
# ---------------------------------------------------------------------------


def _default_outcomes_path() -> Path:
    return default_registry_path().parent / "agent_outcomes.jsonl"


def reputation(agent_id: str, outcomes_path: Optional[Path] = None) -> float:
    """Beta(1+wins, 1+losses) posterior mean. Returns prior 0.5 with no data."""
    path = outcomes_path or _default_outcomes_path()
    if not path.exists():
        return 0.5
    wins = losses = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("agent_id") != agent_id:
            continue
        if rec.get("success"):
            wins += 1
        else:
            losses += 1
    # Beta(1+wins, 1+losses) mean = (1+wins) / (2 + wins + losses)
    return (1.0 + wins) / (2.0 + wins + losses)


def record_outcome(
    agent_id: str,
    task_id: str,
    success: bool,
    outcomes_path: Optional[Path] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Append an outcome to the reputation log."""
    path = outcomes_path or _default_outcomes_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    rec: dict[str, Any] = {
        "agent_id": agent_id,
        "task_id": task_id,
        "success": bool(success),
        "ts": time.time(),
    }
    if extra:
        rec.update(extra)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Capability matching
# ---------------------------------------------------------------------------


_TASK_TAG_VOCAB = {
    "python", "javascript", "typescript", "rust", "go", "cpp", "java", "ruby",
    "code", "edit", "review", "debug", "refactor", "test", "docs", "research",
    "web", "browser", "api", "database", "sql", "deploy", "docker", "ci",
    "security", "performance", "frontend", "backend", "devops", "ml", "ai",
    "math", "reasoning", "planning", "writing", "translation",
}


def extract_task_tags(task: str) -> set[str]:
    """Very small keyword tagger. Replace with an embedding model later."""
    text = task.lower()
    tags = set()
    for word in _TASK_TAG_VOCAB:
        if word in text:
            tags.add(word)
    # Always include 'general' so generic agents can match
    if not tags:
        tags.add("general")
    return tags


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


# ---------------------------------------------------------------------------
# Scoring + auction
# ---------------------------------------------------------------------------


def _normalized_cost(spec: AgentSpec) -> float:
    """Return a cost in [0, ∞). Free models → 0. Frontier → ~0.1."""
    return (spec.cost_per_1k_input + spec.cost_per_1k_output) / 2.0


def score_agent(
    spec: AgentSpec,
    task: str,
    outcomes_path: Optional[Path] = None,
) -> float:
    """Score an agent for a task. Returns a value in [0, 1]."""
    tags = extract_task_tags(task)
    caps = {c.lower() for c in spec.capabilities}
    capability_match = _jaccard(tags, caps)

    # Boost if the agent's `when_to_use` text overlaps the task
    text = task.lower()
    if spec.when_to_use and any(
        tok in text for tok in spec.when_to_use.lower().split() if len(tok) > 4
    ):
        capability_match = min(1.0, capability_match + 0.2)
    if spec.when_not_to_use and any(
        tok in text for tok in spec.when_not_to_use.lower().split() if len(tok) > 4
    ):
        capability_match = max(0.0, capability_match - 0.3)

    rep = reputation(spec.agent_id, outcomes_path=outcomes_path)
    cost = _normalized_cost(spec)
    cost_efficiency = 1.0 / (1.0 + 10.0 * cost)  # cost=0 → 1.0; cost=0.1 → 0.5

    return capability_match * rep * cost_efficiency


@dataclass
class AuctionResult:
    winner_id: str
    winner_score: float
    runner_up_id: Optional[str] = None
    runner_up_score: float = 0.0
    champion_id: Optional[str] = None
    champion_displaced: bool = False
    all_scores: dict[str, float] = field(default_factory=dict)


def auction(
    task: str,
    candidate_ids: Optional[Iterable[str]] = None,
    registry_path: Optional[Path] = None,
    outcomes_path: Optional[Path] = None,
    champion_id: Optional[str] = None,
    win_margin: float = 0.55,
) -> Optional[AuctionResult]:
    """Pick the best agent for the task.

    Args:
        task: free-form task description
        candidate_ids: restrict to these agent_ids; None = all dynamic agents
        registry_path: override the operating registry path
        outcomes_path: override the reputation log path
        champion_id: if set, the challenger must beat the champion by win_margin
        win_margin: required score ratio to displace the champion (default 0.55
            — matches the research_fabric AlphaZero gate)

    Returns:
        AuctionResult, or None if no candidates.
    """
    all_agents = list_agents(registry_path=registry_path)
    if candidate_ids is not None:
        keep = set(candidate_ids)
        all_agents = [a for a in all_agents if a.agent_id in keep]
    if not all_agents:
        return None

    scores = {a.agent_id: score_agent(a, task, outcomes_path) for a in all_agents}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    winner_id, winner_score = ranked[0]
    runner_up_id, runner_up_score = (ranked[1] if len(ranked) > 1 else (None, 0.0))

    # Champion gate: challenger must win by win_margin
    champion_displaced = False
    if champion_id and champion_id in scores and champion_id != winner_id:
        champion_score = scores[champion_id]
        if champion_score > 0 and winner_score / champion_score < (1.0 + win_margin):
            # Champion holds
            return AuctionResult(
                winner_id=champion_id,
                winner_score=champion_score,
                runner_up_id=winner_id,
                runner_up_score=winner_score,
                champion_id=champion_id,
                champion_displaced=False,
                all_scores=scores,
            )
        champion_displaced = True

    return AuctionResult(
        winner_id=winner_id,
        winner_score=winner_score,
        runner_up_id=runner_up_id,
        runner_up_score=runner_up_score,
        champion_id=champion_id,
        champion_displaced=champion_displaced,
        all_scores=scores,
    )
