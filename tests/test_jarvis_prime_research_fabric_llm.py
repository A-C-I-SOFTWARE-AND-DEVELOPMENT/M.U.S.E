"""Tests for the LLM solver/mutator adapter (fake provider; no network)."""

from __future__ import annotations

from hermes_cli.jarvis_prime.research_fabric.selfplay.llm import (
    LLMMutator,
    LLMSolver,
    extract_code,
)
from hermes_cli.jarvis_prime.research_fabric.selfplay.tasks import DEMO_EVOLVE_TASK
from hermes_cli.jarvis_prime.research_fabric.verifier.algorithms import (
    score_algorithm_candidate,
)


def test_extract_code_from_fence() -> None:
    text = "Here you go:\n```python\ndef solve(xs):\n    return sum(xs)\n```\nDone."
    code = extract_code(text)
    assert "def solve(xs):" in code
    assert "Here you go" not in code


def test_extract_code_without_fence() -> None:
    code = extract_code("def solve(xs):\n    return sum(xs)")
    assert code.strip().startswith("def solve")


def test_llm_solver_output_passes_verifier() -> None:
    # Fake provider returns a correct solution in a code fence.
    provider = lambda _prompt: "```python\ndef solve(xs):\n    return sum(xs)\n```"
    solver = LLMSolver(provider)
    code = solver(DEMO_EVOLVE_TASK)
    score = score_algorithm_candidate(code, DEMO_EVOLVE_TASK)
    assert score.accepted is True


def test_llm_mutator_returns_requested_count() -> None:
    provider = lambda _p: "```python\ndef solve(xs):\n    return sum(xs)\n```"
    mutator = LLMMutator(provider, n=3)
    variants = mutator("def solve(xs):\n    return 0\n")
    assert len(variants) == 3
    assert all("return sum(xs)" in v for v in variants)


def test_llm_mutator_bad_output_is_caught_by_verifier() -> None:
    # A plausible-but-wrong mutation must not pass the executable verifier.
    provider = lambda _p: "```python\ndef solve(xs):\n    return 123\n```"
    variant = LLMMutator(provider)("def solve(xs):\n    return sum(xs)\n")[0]
    assert score_algorithm_candidate(variant, DEMO_EVOLVE_TASK).accepted is False
