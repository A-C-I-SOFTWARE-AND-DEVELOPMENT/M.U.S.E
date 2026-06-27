"""Tests for LTI-stable iterative fusion (Mythos LTI injection analog)."""

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent.fusion_lti import (
    LTIFusionState,
    compute_alpha,
    init_fusion_state,
    update_fusion_state,
    get_refinement_prompt,
    select_final_output,
    verify_stability,
    _text_similarity,
)


def test_alpha_always_in_open_interval():
    """alpha must be in (0, 1) for any parameter values — LTI guarantee."""
    for log_alpha in [-10, -5, -1, 0, 1, 5, 10]:
        for log_dt in [-10, -5, -1, 0, 1, 5, 10]:
            a = compute_alpha(log_alpha, log_dt)
            assert 0 < a < 1, f"alpha={a} not in (0,1) for log_alpha={log_alpha}, log_dt={log_dt}"


def test_default_alpha_is_exp_neg_1():
    """Default parameters should give alpha = exp(-1) ≈ 0.368."""
    a = compute_alpha(0.0, 0.0)
    assert abs(a - 0.367879) < 0.001


def test_init_fusion_state():
    """State initializes with original as both h_0 and e."""
    state = init_fusion_state("Original response")
    assert state.original == "Original response"
    assert state.fused == "Original response"
    assert state.round == 0
    assert state.round_outputs == []
    assert 0 < state.alpha < 1
    assert verify_stability(state) is True


def test_update_increments_round():
    """Each update increments the round counter."""
    state = init_fusion_state("Original")
    state = update_fusion_state(state, "Round 1 output")
    assert state.round == 1
    assert len(state.round_outputs) == 1
    state = update_fusion_state(state, "Round 2 output")
    assert state.round == 2
    assert len(state.round_outputs) == 2


def test_spectral_radius_always_less_than_one():
    """Stability guarantee: spectral radius < 1 by construction."""
    state = init_fusion_state("Original")
    for i in range(10):
        state = update_fusion_state(state, f"Round {i+1} output")
        assert verify_stability(state) is True
        assert state.spectral_radius() < 1.0


def test_refinement_prompt_includes_depth_signal():
    """Refinement prompt should include round number (like loop_index_embedding)."""
    state = init_fusion_state("Original")
    prompt = get_refinement_prompt(state, "User query")
    assert "Round 1" in prompt or "Round 0" in prompt
    assert "User query" in prompt

    state = update_fusion_state(state, "Round 1 output")
    prompt = get_refinement_prompt(state, "User query")
    assert "Round" in prompt  # depth signal present


def test_refinement_prompt_changes_with_depth():
    """Different rounds should produce different prompts (LoRA-analog)."""
    state = init_fusion_state("Original")
    prompt_0 = get_refinement_prompt(state, "Query")

    state = update_fusion_state(state, "Output 1")
    prompt_1 = get_refinement_prompt(state, "Query")

    state = update_fusion_state(state, "Output 2")
    state = update_fusion_state(state, "Output 3")
    prompt_late = get_refinement_prompt(state, "Query")

    # Early vs late prompts should differ in instructions
    assert prompt_0 != prompt_1
    assert prompt_0 != prompt_late


def test_select_final_output_returns_original_if_no_rounds():
    """No rounds → return original."""
    state = init_fusion_state("Original")
    assert select_final_output(state) == "Original"


def test_select_final_output_returns_single_round():
    """One round → return that round's output."""
    state = init_fusion_state("Original")
    state = update_fusion_state(state, "Round 1")
    assert select_final_output(state) == "Round 1"


def test_select_final_output_falls_back_on_drift():
    """If final round drifts too much, use previous round."""
    state = init_fusion_state("Original")
    state = update_fusion_state(state, "The quick brown fox jumps over the lazy dog")
    state = update_fusion_state(state, "Completely different words with no overlap at all here")
    # Should fall back to round 1 (more stable)
    result = select_final_output(state)
    assert "quick brown fox" in result


def test_text_similarity():
    """Similarity score should be reasonable."""
    assert _text_similarity("", "") == 0.0
    assert _text_similarity("hello world", "hello world") == 1.0
    sim = _text_similarity("hello world foo", "hello world bar")
    assert 0 < sim < 1
    # More overlap = higher similarity
    sim1 = _text_similarity("a b c", "a b c d e")
    sim2 = _text_similarity("a b c", "x y z d e")
    assert sim1 > sim2


def test_custom_config_parameters():
    """Custom LTI parameters should be respected."""
    state = init_fusion_state("Original", config={
        "lti_log_alpha": 2.0,
        "lti_log_dt": 1.0,
        "lti_beta": 0.2,
    })
    # alpha = exp(-exp(3)) ≈ exp(-20.09) ≈ very small
    assert state.alpha < 0.01
    assert state.beta == 0.2
