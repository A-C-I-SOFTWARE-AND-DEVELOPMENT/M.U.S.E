"""Tests for per-round specialization (Mythos LoRA adapter analog)."""

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent.fusion_round_specialization import (
    RoundRole,
    get_round_system_prompt,
    get_round_instruction,
    get_round_config,
)


def test_single_round_is_diverse():
    """Single round should use DIVERSE role."""
    prompt = get_round_system_prompt(0, 1)
    assert "DIVERSE" in prompt


def test_first_round_always_diverse():
    """Round 0 should always be DIVERSE regardless of total."""
    for total in [1, 2, 3, 4, 5]:
        prompt = get_round_system_prompt(0, total)
        assert "DIVERSE" in prompt, f"Round 0 with total={total} should be DIVERSE"


def test_two_rounds_diverse_then_synthesize():
    """2 rounds: DIVERSE → SYNTHESIZE."""
    r0 = get_round_system_prompt(0, 2)
    r1 = get_round_system_prompt(1, 2)
    assert "DIVERSE" in r0
    assert "SYNTHESIZE" in r1


def test_three_rounds_diverse_synthesize_synthesize():
    """3 rounds: DIVERSE → SYNTHESIZE → SYNTHESIZE (last is synthesize for <4)."""
    r0 = get_round_system_prompt(0, 3)
    r1 = get_round_system_prompt(1, 3)
    r2 = get_round_system_prompt(2, 3)
    assert "DIVERSE" in r0
    assert "SYNTHESIZE" in r1
    assert "SYNTHESIZE" in r2


def test_four_rounds_diverse_synthesize_verify_polish():
    """4 rounds: DIVERSE → SYNTHESIZE → VERIFY → POLISH."""
    r0 = get_round_system_prompt(0, 4)
    r1 = get_round_system_prompt(1, 4)
    r2 = get_round_system_prompt(2, 4)
    r3 = get_round_system_prompt(3, 4)
    assert "DIVERSE" in r0
    assert "SYNTHESIZE" in r1
    assert "VERIFY" in r2
    assert "POLISH" in r3


def test_five_rounds_extra_verify():
    """5 rounds: extra round gets VERIFY."""
    r0 = get_round_system_prompt(0, 5)
    r1 = get_round_system_prompt(1, 5)
    r2 = get_round_system_prompt(2, 5)
    r3 = get_round_system_prompt(3, 5)
    r4 = get_round_system_prompt(4, 5)
    assert "DIVERSE" in r0
    assert "SYNTHESIZE" in r1
    assert "VERIFY" in r2
    assert "VERIFY" in r3  # extra verify
    assert "POLISH" in r4


def test_depth_signal_in_prompt():
    """Prompt should include round number (like loop_index_embedding)."""
    prompt = get_round_system_prompt(2, 4)
    assert "Round 3" in prompt  # 0-indexed + 1
    assert "4" in prompt  # total rounds


def test_base_prompt_prepended():
    """Base prompt should be prepended to the adapter."""
    base = "You are Axiom, a collective intelligence AI."
    prompt = get_round_system_prompt(0, 2, base_prompt=base)
    assert base in prompt
    assert "DIVERSE" in prompt


def test_round_instruction_changes_with_depth():
    """Instructions should differ between rounds."""
    instr_0 = get_round_instruction(0, 3)
    instr_1 = get_round_instruction(1, 3)
    instr_2 = get_round_instruction(2, 3)
    assert instr_0 != instr_1
    assert instr_1 != instr_2


def test_round_config_temperature_decreases():
    """Temperature should decrease in later rounds (more focused)."""
    cfg_0 = get_round_config(0, 4)
    cfg_3 = get_round_config(3, 4)
    assert cfg_0["temperature"] > cfg_3["temperature"]


def test_round_config_includes_role_name():
    """Round config should include the role name for logging."""
    cfg = get_round_config(0, 4)
    assert "system_prompt_role" in cfg
    assert cfg["system_prompt_role"] == "DIVERSE"


def test_round_roles_ordered():
    """RoundRole enum should be ordered DIVERSE < SYNTHESIZE < VERIFY < POLISH."""
    assert RoundRole.DIVERSE < RoundRole.SYNTHESIZE
    assert RoundRole.SYNTHESIZE < RoundRole.VERIFY
    assert RoundRole.VERIFY < RoundRole.POLISH
