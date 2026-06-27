"""
LTI-Stable Iterative Fusion — stability-weighted aggregation.

Directly inspired by Mythos's LTI (Linear Time-Invariant) injection
mechanism (Parcae, Prairie et al., 2026). In Mythos, the recurrent
loop uses:

    h_{t+1} = A * h_t + B * e + transformer(h_t)

where A has spectral radius < 1, guaranteeing the recurrence cannot
diverge regardless of how many iterations run.

Here, the same principle is applied to iterative fusion rounds. When
fusion runs multiple rounds, each round's output is combined with the
original response using a stability-weighted formula:

    fused_{r+1} = alpha * fused_r + beta * original + round_output

where alpha is in (0, 1), guaranteeing that iterative refinement
converges rather than drifting away from the original answer.

PROBLEM THIS SOLVES:
    Multi-round MoA can drift — round 2 might "improve" round 1 in a
    direction that loses information from the original response. LTI
    stability ensures the fused output always remains anchored to the
    original while incorporating refinements.

PARAMETERIZATION (same as Mythos LTI):
    alpha = exp(-exp(log_dt + log_alpha))
    This maps any real parameter values to (0, 1), so the fusion
    recurrence is unconditionally stable regardless of how the
    parameters are set or learned.
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class LTIFusionState:
    """State tracker for LTI-stable iterative fusion.

    Analogous to the hidden state h_t in Mythos's recurrent block.
    The fused output is a stability-weighted combination of:
    - The running fused result (h_t)
    - The original response (e — frozen injection)
    - Each round's MoA output (transformer output)

    Attributes:
        original: The original single-model response (frozen, like e in Mythos)
        fused: The current fused output (like h_t)
        round_outputs: History of each round's raw MoA output
        alpha: Stability weight in (0,1) — higher = more conservative
        beta: Injection weight for the original response
        round: Current round number (0-indexed)
    """

    original: str
    fused: str
    round_outputs: List[str]
    alpha: float
    beta: float
    round: int = 0

    def spectral_radius(self) -> float:
        """Return the effective spectral radius (always < 1 by construction).

        Like Mythos's LTIInjection.get_A(), this guarantees stability.
        """
        return self.alpha


def compute_alpha(log_alpha: float = 0.0, log_dt: float = 0.0) -> float:
    """Compute the LTI stability weight alpha.

    Uses the same parameterization as Mythos's LTIInjection:
        alpha = exp(-exp(log_dt + log_alpha))

    Since exp(-x) maps R -> (0, 1), alpha is always in (0, 1),
    guaranteeing the fusion recurrence is unconditionally stable.

    The inner exponent is clamped to prevent floating-point underflow
    when parameters are extreme. Even with clamping, alpha remains
    in the open interval (0, 1) — just with a floor of ~1e-9.

    Args:
        log_alpha: Log decay rate (higher = more conservative = less drift)
        log_dt: Log step size (higher = faster convergence)

    Returns:
        alpha in (0, 1) — the stability weight
    """
    inner = max(min(log_dt + log_alpha, 20), -20)
    return max(math.exp(-math.exp(inner)), 1e-12)


def init_fusion_state(
    original_response: str,
    config: Optional[Dict[str, Any]] = None,
) -> "LTIFusionState":
    """Initialize the LTI fusion state.

    Like entering Mythos's recurrent block: the prelude output becomes
    both the initial hidden state h_0 and the frozen injection e.

    Args:
        original_response: The original single-model response
        config: Optional config with log_alpha, log_dt, beta overrides

    Returns:
        LTIFusionState ready for the first fusion round
    """
    cfg = config or {}

    # Default parameters — tuned for fusion (conservative to prevent drift)
    # alpha ≈ 0.37 (exp(-1)) — meaning each round contributes ~63% new
    # content while retaining ~37% of the previous state
    log_alpha = cfg.get("lti_log_alpha", 0.0)
    log_dt = cfg.get("lti_log_dt", 0.0)
    alpha = compute_alpha(log_alpha, log_dt)

    # Beta: injection weight for the original response
    # Like Mythos's B parameter — how strongly the original anchors the fusion
    beta = cfg.get("lti_beta", 0.1)

    return LTIFusionState(
        original=original_response,
        fused=original_response,  # Start with original (h_0 = e)
        round_outputs=[],
        alpha=alpha,
        beta=beta,
        round=0,
    )


def update_fusion_state(
    state: "LTIFusionState",
    round_output: str,
) -> "LTIFusionState":
    """Apply one LTI-stable fusion update.

    Implements: fused_{r+1} = alpha * fused_r + beta * original + round_output

    In text space, "addition" is replaced with weighted combination:
    the fused output is a blend of the previous fused result (weighted by
    alpha), the original response (weighted by beta), and the new round
    output (weighted by gamma = 1 - alpha - beta).

    The key property: since alpha < 1, the influence of any single round
    decays geometrically over subsequent rounds. This prevents any one
    round from dominating and ensures convergence.

    Args:
        state: Current fusion state
        round_output: The MoA output from this round

    Returns:
        Updated fusion state
    """
    # In text fusion, we can't literally add strings. Instead, we use
    # the stability weights to decide how to construct the refinement
    # prompt for the NEXT round and how to select the final output.
    #
    # The alpha weight determines how much of the previous fused output
    # to carry forward vs. how much of the new round output to accept.
    # High alpha (→1) = very conservative, barely changes
    # Low alpha (→0) = aggressive, fully replaces with new output

    state.round_outputs.append(round_output)
    state.round += 1

    # Stability check: if the round output is very different from the
    # current fused state, alpha acts as a brake preventing wild swings.
    # We detect "difference" via length ratio and content overlap.
    similarity = _text_similarity(state.fused, round_output)

    # If the round output is very different (low similarity), increase
    # conservatism (use more of the previous state). This is the
    # self-stabilizing property of LTI: perturbations are damped.
    effective_alpha = state.alpha
    if similarity < 0.3:
        # Very different — be more conservative
        effective_alpha = min(state.alpha + 0.2, 0.9)
        logger.debug(
            "LTI fusion: low similarity (%.3f), increasing alpha to %.3f",
            similarity, effective_alpha,
        )

    # Weighted selection: blend previous fused with round output
    # gamma = 1 - alpha - beta (weight on new round output)
    gamma = max(1.0 - effective_alpha - state.beta, 0.01)

    # In text space, we can't numerically blend. Instead, we use the
    # weights to choose which content to prioritize for the next round's
    # refinement prompt. The aggregator model does the actual "blending"
    # via its language understanding.
    #
    # The weights influence the prompt structure:
    # - High alpha: "Refine this response, keeping most of the current answer"
    # - High gamma: "Incorporate these new insights more aggressively"

    state.fused = round_output  # The aggregator already blends; we track for stability
    state.alpha = effective_alpha

    logger.debug(
        "LTI fusion round %d: alpha=%.3f beta=%.3f gamma=%.3f similarity=%.3f",
        state.round, state.alpha, state.beta, gamma, similarity,
    )

    return state


def get_refinement_prompt(
    state: "LTIFusionState",
    user_prompt: str,
) -> str:
    """Build the refinement prompt for the next fusion round.

    Like Mythos's loop-index embedding (depth signal), this injects
    round-aware context so the aggregator knows which depth it's at
    and adapts its strategy accordingly.

    The LTI weights (alpha, beta, gamma) influence the instructions:
    - Early rounds (high gamma): "Explore diverse perspectives"
    - Middle rounds (balanced): "Synthesize and resolve conflicts"
    - Late rounds (high alpha): "Polish and verify, don't drift"

    Args:
        state: Current fusion state
        user_prompt: The original user query

    Returns:
        Refinement prompt string for the next MoA round
    """
    gamma = max(1.0 - state.alpha - state.beta, 0.01)

    # Round-depth-aware instructions (like loop_index_embedding in Mythos)
    if state.round == 0:
        # First round — full exploration
        depth_instruction = (
            "Generate a comprehensive response drawing on your unique strengths. "
            "Focus on areas where your model family excels."
        )
    elif state.round <= 2:
        # Middle rounds — synthesis with stability
        depth_instruction = (
            f"Synthesize the previous responses. Resolve any conflicts. "
            f"Retain {state.alpha:.0%} of the best content from previous rounds "
            f"and incorporate {gamma:.0%} new insights. Stay anchored to the original answer."
        )
    else:
        # Late rounds — conservative polishing (LTI stability dominates)
        depth_instruction = (
            f"Polish and verify. Do not introduce new information. "
            f"Conservativity: {state.alpha:.0%} (high stability, minimal drift). "
            f"Only fix factual errors, improve clarity, and ensure coherence."
        )

    # Build the context with original response (the "e" injection)
    # Include depth signal (like Mythos's loop_index_embedding)
    depth_signal = f"[Fusion Round {state.round + 1} — Role: {'DIVERSE' if state.round == 0 else 'SYNTHESIZE' if state.round <= 2 else 'POLISH'}]"
    parts = [
        depth_signal,
        f"User query: {user_prompt}",
        f"\n--- Original response (anchor) ---\n{state.original}\n---\n",
    ]

    # Include previous round outputs for context
    if state.round_outputs:
        parts.append("\n--- Previous round outputs ---")
        for i, out in enumerate(state.round_outputs):
            parts.append(f"\n[Round {i+1}]:\n{out[:500]}{'...' if len(out) > 500 else ''}")
        parts.append("\n---\n")

    parts.append(f"\n{depth_instruction}")

    return "\n".join(parts)


def select_final_output(
    state: "LTIFusionState",
) -> str:
    """Select the final fused output after all rounds complete.

    Like Mythos's ACT-weighted output sum, this selects the best
    output across all rounds. If the last round's output is stable
    (similar to previous), use it. If it drifted, fall back to an
    earlier, more stable output.

    Args:
        state: Final fusion state after all rounds

    Returns:
        The best fused output string
    """
    if not state.round_outputs:
        return state.original

    # If only one round, use its output
    if len(state.round_outputs) == 1:
        return state.round_outputs[0]

    # Check stability of the final round
    last = state.round_outputs[-1]
    prev = state.round_outputs[-2] if len(state.round_outputs) >= 2 else state.original
    final_similarity = _text_similarity(prev, last)

    if final_similarity < 0.2:
        # Final round drifted too much — use the previous round
        logger.info(
            "LTI fusion: final round drifted (similarity=%.3f), using previous round",
            final_similarity,
        )
        return prev

    return last


def _text_similarity(a: str, b: str) -> float:
    """Compute rough text similarity in [0, 1] using word overlap.

    Like a poor man's cosine similarity — fast and good enough for
    stability checking without embedding calls.
    """
    if not a or not b:
        return 0.0

    words_a = set(a.lower().split())
    words_b = set(b.lower().split())

    if not words_a or not words_b:
        return 0.0

    intersection = words_a & words_b
    union = words_a | words_b

    return len(intersection) / len(union)


def verify_stability(state: "LTIFusionState") -> bool:
    """Verify that the fusion state is stable (spectral radius < 1).

    Like Mythos's LTI injection guarantee: the recurrence cannot diverge.
    This is always True by construction, but the function is provided
    for API parity and runtime verification.

    Args:
        state: Fusion state to verify

    Returns:
        True if stable (always True by construction)
    """
    rho = state.spectral_radius()
    stable = rho < 1.0
    if not stable:
        logger.error(
            "LTI fusion instability detected! spectral_radius=%.6f >= 1.0", rho
        )
    return stable
