"""
Fusion Router — Routes responses through Mixture-of-Agents with four
Mythos-inspired adaptive mechanisms.

When fusion mode is active (default), the router applies four concepts
ported from Anthropic's Mythos recurrent-depth transformer architecture:

1. ACT-Inspired Difficulty Routing (from Mythos ACT halting):
   Easy queries skip fusion, medium queries use fewer models, hard
   queries get the full MoA council. Like easy tokens halting early.

2. MoE-Inspired Model Routing (from Mythos/DeepSeek-V3 MoE):
   Queries are classified by type (code, math, creative, etc.) and
   routed to the best-suited models. Includes aux-loss-free load
   balancing to prevent rate-limit exhaustion on popular providers.

3. LTI-Stable Iterative Fusion (from Mythos LTI injection):
   Multi-round fusion uses stability-weighted aggregation to prevent
   response drift. The recurrence is unconditionally stable (spectral
   radius < 1 by construction), so more rounds can't make it worse.

4. Per-Round Specialization (from Mythos LoRA adapters):
   Each fusion round gets a different system prompt (DIVERSE →
   SYNTHESIZE → VERIFY → POLISH), like how LoRA adapters specialize
   the shared transformer block at each loop depth.

5. Depth Extrapolation (from Mythos inference-time scaling):
   Hard queries get more rounds at inference time, like increasing
   loop count from T=16 to T=64 in Mythos for harder problems.

Modes:
- "fusion" (default): Route through MoA with all adaptive mechanisms
- "single": Traditional single-model response (legacy behavior)

Configuration via config.yaml:
    fusion:
      mode: fusion
      reference_models:
        - anthropic/claude-opus-4.6
        - google/gemini-2.5-pro
        - deepseek/deepseek-r1
      rounds: 1
      aggregator: anthropic/claude-opus-4.6
      difficulty_aware: true     # ACT-inspired routing
      moe_routing: true          # MoE-inspired model selection
      lti_stable: true           # LTI-stable aggregation
      round_specialization: true # Per-round LoRA-analog prompts
"""

import asyncio
import json
import logging
from typing import Any, Optional, Dict, List

logger = logging.getLogger(__name__)


# Default fusion configuration
FUSION_CONFIG = {
    "mode": "fusion",  # "fusion" or "single"
    "reference_models": [
        "anthropic/claude-opus-4.6",
        "google/gemini-2.5-pro",
        "deepseek/deepseek-r1",
    ],
    "aggregator_model": "anthropic/claude-opus-4.6",
    "rounds": 1,
    "strategy": "parallel",
    # ACT-inspired adaptive difficulty routing (Mythos ACT halting analog).
    "difficulty_aware": True,
    # MoE-inspired model routing (Mythos/DeepSeek-V3 MoE analog).
    # Routes queries to best-suited models with load balancing.
    "moe_routing": True,
    # LTI-stable iterative fusion (Mythos LTI injection analog).
    # Prevents response drift in multi-round fusion.
    "lti_stable": True,
    # Per-round specialization (Mythos LoRA adapter analog).
    # Different system prompts per fusion round.
    "round_specialization": True,
}


def get_fusion_config() -> Dict[str, Any]:
    """Load fusion config from config.yaml or use defaults."""
    try:
        from hermes_cli.config import load_config
        cfg = load_config()
        fusion_cfg = cfg.get("fusion", {})
        # Merge with defaults
        merged = FUSION_CONFIG.copy()
        merged.update(fusion_cfg)
        return merged
    except Exception as e:
        logger.debug(f"Could not load fusion config, using defaults: {e}")
        return FUSION_CONFIG.copy()


def should_use_fusion() -> bool:
    """Check if fusion mode is active."""
    cfg = get_fusion_config()
    return cfg.get("mode", "fusion") == "fusion"


async def fuse_response(
    user_prompt: str,
    original_response: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    tool_iterations: int = 0,
) -> str:
    """
    Route a response through the MoA fusion pipeline.

    If difficulty_aware is enabled (default), the query is classified
    first (ACT-inspired), and the fusion depth is selected accordingly:
    - Easy queries skip fusion entirely (return original response)
    - Medium queries get light fusion (fewer models)
    - Hard queries get full MoA with all models and more rounds

    Args:
        user_prompt: The user's original query
        original_response: Optional single-model response to refine (if None, generates from scratch)
        config: Optional fusion config override
        tool_iterations: Number of tool calls made during this turn (difficulty signal)

    Returns:
        Fused response string
    """
    cfg = config or get_fusion_config()

    # ── ACT-inspired difficulty assessment ────────────────────────────
    # Like Mythos's ACT halting: assess difficulty before spending compute.
    # Easy queries halt immediately (skip fusion), hard queries run deep.
    if cfg.get("difficulty_aware", True) and original_response:
        from agent.fusion_difficulty import classify_difficulty, depth_to_config, FusionDepth

        assessment = classify_difficulty(
            prompt=user_prompt,
            response=original_response,
            tool_iterations=tool_iterations,
            config=cfg,
        )

        logger.info(
            "Fusion difficulty: score=%.3f depth=%s halted=%s",
            assessment.score, assessment.depth.name, assessment.halted_early,
        )

        # SKIP = easy query, return original (ACT early halt)
        if assessment.depth == FusionDepth.SKIP:
            logger.info("Fusion skipped — easy query (ACT halt at depth 0)")
            return original_response

        # Adjust config based on depth (like choosing loop count in Mythos)
        cfg = depth_to_config(assessment, cfg)
        logger.info(
            "Fusion depth %s: %d models, %d rounds",
            assessment.depth.name,
            len(cfg.get("reference_models", [])),
            cfg.get("rounds", 1),
        )

    # ── MoE-inspired model routing ────────────────────────────────────
    # Like Mythos's MoE: route the query to the best-suited models based
    # on query type, with aux-loss-free load balancing across providers.
    if cfg.get("moe_routing", True):
        from agent.fusion_model_router import MoEModelRouter

        all_models = cfg.get("reference_models", FUSION_CONFIG["reference_models"])
        aggregator = cfg.get("aggregator_model", FUSION_CONFIG["aggregator_model"])

        # Create router with current model pool
        router = MoEModelRouter(
            available_models=all_models,
            anchor_model=aggregator,
        )

        # Route query to best models (like top-K expert selection)
        n_models = len(cfg.get("reference_models", all_models))
        selected_models, query_type, scores = router.route(
            prompt=user_prompt,
            response=original_response or "",
            top_k=n_models,
        )

        # Override reference models with MoE-selected ones
        cfg["reference_models"] = selected_models
        cfg["_moe_query_type"] = query_type.value
        cfg["_moe_scores"] = {k: round(v, 3) for k, v in scores.items()}

        logger.info(
            "MoE routing: type=%s models=%s",
            query_type.value, selected_models,
        )

    # ── Per-round specialization (LoRA analog) ────────────────────────
    # Like Mythos's LoRA adapters: each round gets a different system
    # prompt that shifts the aggregator's behavior at that depth.
    rounds = cfg.get("rounds", 1)
    if cfg.get("round_specialization", True) and rounds > 1:
        from agent.fusion_round_specialization import get_round_instruction

        # Build round-aware enhanced prompt (first round uses standard format)
        enhanced_prompt = user_prompt
        if original_response:
            round_instruction = get_round_instruction(0, rounds)
            enhanced_prompt = (
                f"{round_instruction}\n\n"
                f"User query: {user_prompt}\n\n"
                f"---\n"
                f"Initial response to refine:\n"
                f"{original_response}\n"
                f"---"
            )
    else:
        # Standard single-round prompt (or specialization disabled)
        enhanced_prompt = user_prompt
        if original_response:
            enhanced_prompt = (
                f"{user_prompt}\n\n"
                f"---\n"
                f"Initial response to refine:\n"
                f"{original_response}\n"
                f"---\n\n"
                f"Please synthesize and improve upon this response."
            )
    
    try:
        # Import MoA tool
        from tools.mixture_of_agents_tool import mixture_of_agents_tool
        
        # Build the prompt for MoA
        moa_prompt = enhanced_prompt
        
        # Call MoA with configured parameters
        result_json = await mixture_of_agents_tool(
            user_prompt=moa_prompt,
            reference_models=cfg.get("reference_models", FUSION_CONFIG["reference_models"]),
            aggregator_model=cfg.get("aggregator_model", FUSION_CONFIG["aggregator_model"]),
            rounds=cfg.get("rounds", FUSION_CONFIG["rounds"]),
            strategy=cfg.get("strategy", FUSION_CONFIG["strategy"]),
        )
        
        # Parse the JSON result
        result = json.loads(result_json)
        
        if result.get("success"):
            fused = result.get("response", "")
            metadata = result.get("metadata", {})
            models_used = len(metadata.get("reference_models", []))
            rounds_executed = len(metadata.get("rounds_executed", []))
            
            logger.info(
                f"Fusion complete: {models_used} models × {rounds_executed} rounds → "
                f"{len(fused)} chars"
            )
            
            return fused
        else:
            # MoA failed — return the original response or an error
            error = result.get("error", "Unknown fusion error")
            logger.warning(f"Fusion failed ({error}), falling back to original response")
            return original_response or f"Fusion unavailable: {error}"
            
    except ImportError as e:
        logger.error(f"MoA tool not available: {e}")
        return original_response or "Fusion pipeline not configured"
        
    except Exception as e:
        logger.error(f"Fusion error: {e}", exc_info=True)
        return original_response or f"Fusion error: {e}"


def fuse_response_sync(
    user_prompt: str,
    original_response: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    tool_iterations: int = 0,
) -> str:
    """
    Synchronous wrapper for fuse_response.
    
    Uses asyncio.run() to execute the async fusion pipeline.
    Safe to call from synchronous code paths.

    Args:
        user_prompt: The user's original query
        original_response: Optional single-model response to refine
        config: Optional fusion config override
        tool_iterations: Number of tool calls this turn (difficulty signal)
    """
    try:
        # Check if we're already in an async context
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context — use run_coroutine_threadsafe
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    fuse_response(
                        user_prompt,
                        original_response,
                        config,
                        tool_iterations=tool_iterations,
                    )
                )
                return future.result(timeout=120)  # 2 minute timeout
        except RuntimeError:
            # No running loop — safe to use asyncio.run() directly
            return asyncio.run(
                fuse_response(
                    user_prompt,
                    original_response,
                    config,
                    tool_iterations=tool_iterations,
                )
            )
    except Exception as e:
        logger.error(f"Sync fusion wrapper error: {e}")
        return original_response or f"Fusion unavailable: {e}"


def get_fusion_status() -> Dict[str, Any]:
    """Get current fusion mode status for display."""
    cfg = get_fusion_config()
    is_active = cfg.get("mode") == "fusion"
    
    return {
        "mode": cfg.get("mode", "single"),
        "active": is_active,
        "reference_models": cfg.get("reference_models", []),
        "aggregator_model": cfg.get("aggregator_model", ""),
        "rounds": cfg.get("rounds", 1),
        "difficulty_aware": cfg.get("difficulty_aware", True),
        "moe_routing": cfg.get("moe_routing", True),
        "lti_stable": cfg.get("lti_stable", True),
        "round_specialization": cfg.get("round_specialization", True),
    }
