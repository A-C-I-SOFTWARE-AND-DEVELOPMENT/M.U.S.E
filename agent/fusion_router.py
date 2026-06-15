"""
Fusion Router — Routes all responses through Mixture-of-Agents by default.

When fusion mode is active (default), every final assistant response passes
through the MoA pipeline before being returned to the user. This creates a
"collective intelligence" effect where multiple frontier models collaboratively
refine the response.

Modes:
- "fusion" (default): Route through MoA with 3-4 reference models
- "single": Traditional single-model response (legacy behavior)

Configuration via config.yaml:
    fusion:
      mode: fusion          # "fusion" or "single"
      reference_models:     # Override if needed
        - anthropic/claude-opus-4.6
        - google/gemini-2.5-pro
        - deepseek/deepseek-r1
      rounds: 1             # Iterative refinement rounds (1-5)
      aggregator: anthropic/claude-opus-4.6
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
) -> str:
    """
    Route a response through the MoA fusion pipeline.
    
    Args:
        user_prompt: The user's original query
        original_response: Optional single-model response to refine (if None, generates from scratch)
        config: Optional fusion config override
    
    Returns:
        Fused response string
    """
    cfg = config or get_fusion_config()
    
    # If we have an original response, append it as context for the reference models
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
) -> str:
    """
    Synchronous wrapper for fuse_response.
    
    Uses asyncio.run() to execute the async fusion pipeline.
    Safe to call from synchronous code paths.
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
                    fuse_response(user_prompt, original_response, config)
                )
                return future.result(timeout=120)  # 2 minute timeout
        except RuntimeError:
            # No running loop — safe to use asyncio.run() directly
            return asyncio.run(fuse_response(user_prompt, original_response, config))
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
    }
