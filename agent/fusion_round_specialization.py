"""
Per-Round Specialization — LoRA-analog depth-wise adaptation for fusion.

Directly inspired by Mythos's LoRAAdapter (Hu et al., 2021), which
applies a different rank-r update to the transformer block's weights
at each loop iteration. This allows the shared block to specialize
its behavior per depth without duplicating parameters.

In Axiom's fusion pipeline, the same concept is applied by giving each
fusion round a different system prompt — a "soft adapter" that shifts
the aggregator model's behavior at each depth:

    Round 0 (DIVERSE):  "Generate diverse, independent perspectives"
    Round 1 (SYNTHESIZE): "Find consensus, resolve conflicts, merge insights"
    Round 2 (VERIFY):    "Fact-check, identify errors, verify claims"
    Round 3 (POLISH):    "Improve clarity, structure, and presentation"

Like LoRA, these are lightweight "adapters" (prompt templates) that
specialize a shared base model (the aggregator) for different depths.
Unlike LoRA, they don't require training — they're instruction-level
specialization.

MYTHOS LoRA → AXIOM ROUND SPECIALIZATION MAP:
    LoRA adapter per loop → System prompt per fusion round
    rank-r weight update  → Round-specific instruction prefix
    Depth signal injection → Round number in system prompt
    Identity at start (B=0) → Round 0 = no modification (pure generation)
    Increasing specialization → Increasing focus (diverse → synthesize → verify → polish)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RoundRole(IntEnum):
    """Role of each fusion round — like LoRA depth specialization.

    Each round has a different "job", progressing from exploration
    to verification, exactly like how deeper loop iterations in Mythos
    refine the representation from coarse to precise.
    """

    DIVERSE = 0       # Generate independent, diverse perspectives
    SYNTHESIZE = 1    # Merge perspectives, resolve conflicts
    VERIFY = 2        # Fact-check, identify errors
    POLISH = 3        # Improve clarity and presentation


# ── Round-specific system prompts (the "LoRA adapters") ──────────────
# Each prompt is a lightweight behavioral adapter that shifts the
# aggregator's focus at that depth, like how LoRA shifts the weight
# matrix at each loop iteration.

_ROUND_PROMPTS: Dict[RoundRole, str] = {
    RoundRole.DIVERSE: (
        "You are a diverse perspective generator. Your task is to provide "
        "a response that draws on your unique strengths and training. "
        "Do not try to agree with other models — bring your own perspective. "
        "Focus on areas where you excel that others might miss. "
        "Be thorough and explore multiple angles of the question."
    ),

    RoundRole.SYNTHESIZE: (
        "You are a synthesis engine. You have been given multiple model "
        "responses. Your task is to merge them into a single, superior answer. "
        "Resolve any conflicts between the responses. Keep the best insights "
        "from each model and discard redundant or incorrect content. "
        "The synthesized response should be better than any individual response."
    ),

    RoundRole.VERIFY: (
        "You are a verification engine. Your task is to fact-check the "
        "response for accuracy. Identify any factual errors, logical "
        "inconsistencies, or unsupported claims. Fix any errors you find. "
        "Do not add new information — only verify and correct. "
        "If the response is accurate, improve its precision and specificity."
    ),

    RoundRole.POLISH: (
        "You are a polishing engine. Your task is to improve the clarity, "
        "structure, and presentation of the response. Fix grammar, improve "
        "flow, add structure (headers, lists) where helpful. "
        "Do not change the meaning or add new information. "
        "The response should read as if written by a single expert."
    ),
}


def get_round_system_prompt(
    round_idx: int,
    total_rounds: int,
    base_prompt: Optional[str] = None,
) -> str:
    """Get the system prompt for a specific fusion round.

    Like Mythos's LoRAAdapter, this applies a depth-specific "adapter"
    (prompt) to the aggregator model. The adapter changes behavior at
    each depth without changing the underlying model.

    The role is determined by the round's position relative to total:
    - With 1 round:  just DIVERSE (single-pass MoA)
    - With 2 rounds: DIVERSE → SYNTHESIZE
    - With 3 rounds: DIVERSE → SYNTHESIZE → VERIFY
    - With 4+ rounds: DIVERSE → SYNTHESIZE → VERIFY → POLISH (+ extra VERIFY)

    Args:
        round_idx: Current round (0-indexed)
        total_rounds: Total number of rounds planned
        base_prompt: Optional base system prompt to prepend

    Returns:
        System prompt string for this round
    """
    # Determine role based on round position
    if total_rounds <= 1:
        # Single round — just generate diverse perspectives
        role = RoundRole.DIVERSE
    elif round_idx == 0:
        role = RoundRole.DIVERSE
    elif round_idx == total_rounds - 1:
        # Last round is always POLISH (if 4+ rounds) or SYNTHESIZE (if 2-3)
        if total_rounds >= 4:
            role = RoundRole.POLISH
        else:
            role = RoundRole.SYNTHESIZE
    elif round_idx == 1:
        role = RoundRole.SYNTHESIZE
    elif round_idx == total_rounds - 2 and total_rounds >= 4:
        role = RoundRole.VERIFY
    else:
        # Extra rounds get VERIFY
        role = RoundRole.VERIFY

    adapter_prompt = _ROUND_PROMPTS[role]

    # Build final prompt: base + depth signal + adapter
    # The depth signal (round number) is like Mythos's loop_index_embedding
    depth_signal = f"[Fusion Round {round_idx + 1}/{total_rounds} — Role: {role.name}]"

    if base_prompt:
        return f"{base_prompt}\n\n{depth_signal}\n{adapter_prompt}"
    else:
        return f"{depth_signal}\n{adapter_prompt}"


def get_round_instruction(
    round_idx: int,
    total_rounds: int,
) -> str:
    """Get a short instruction prefix for the user prompt at this round.

    Like the LoRA delta that gets added to the base computation, this
    is a lightweight modifier that shifts the aggregator's behavior.

    Args:
        round_idx: Current round (0-indexed)
        total_rounds: Total number of rounds

    Returns:
        Short instruction string to prepend to the user prompt
    """
    if total_rounds <= 1 or round_idx == 0:
        return (
            "Provide your best independent response to the following query. "
            "Draw on your unique strengths."
        )
    elif round_idx == 1:
        return (
            "Below are responses from multiple AI models. Synthesize them "
            "into one superior response. Resolve conflicts and keep the "
            "best insights from each."
        )
    elif round_idx == total_rounds - 1 and total_rounds >= 4:
        return (
            "Below is a synthesized response. Polish it for clarity, "
            "structure, and presentation. Do not change the meaning."
        )
    elif round_idx >= 2:
        return (
            "Below is a response from previous fusion rounds. Verify it "
            "for accuracy. Fix any errors. Do not add new information."
        )
    else:
        return "Refine the following response, incorporating all perspectives."


def get_round_config(
    round_idx: int,
    total_rounds: int,
) -> Dict[str, Any]:
    """Get configuration parameters for this round.

    Like how LoRA adapters have different scaling at different depths,
    each round can have different parameters (temperature, top_k, etc.).

    Args:
        round_idx: Current round (0-indexed)
        total_rounds: Total number of rounds

    Returns:
        Dict with round-specific parameters
    """
    if round_idx == 0:
        # First round: higher temperature for diversity
        return {
            "temperature": 0.8,
            "instruction": get_round_instruction(round_idx, total_rounds),
            "system_prompt_role": RoundRole.DIVERSE.name,
        }
    elif round_idx == 1:
        # Synthesis: moderate temperature
        return {
            "temperature": 0.5,
            "instruction": get_round_instruction(round_idx, total_rounds),
            "system_prompt_role": RoundRole.SYNTHESIZE.name,
        }
    elif round_idx >= total_rounds - 1 and total_rounds >= 4:
        # Polish: low temperature for consistency
        return {
            "temperature": 0.3,
            "instruction": get_round_instruction(round_idx, total_rounds),
            "system_prompt_role": RoundRole.POLISH.name,
        }
    else:
        # Verify: very low temperature for precision
        return {
            "temperature": 0.2,
            "instruction": get_round_instruction(round_idx, total_rounds),
            "system_prompt_role": RoundRole.VERIFY.name,
        }
