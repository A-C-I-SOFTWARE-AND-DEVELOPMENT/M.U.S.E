#!/usr/bin/env python3
"""
Mixture-of-Agents Tool Module — Unlimited Model Fusion

Implements the Mixture-of-Agents (MoA) methodology with an open-ended
architecture: the orchestrator (MUSE) can choose ANY models from ANY
provider accessible through the configured OpenRouter client — no hard
limits on count, round, or strategy.

Based on: "Mixture-of-Agents Enhances Large Language Model Capabilities"
(Wang et al., arXiv:2406.04692v1)

Key Features
-----------
- Unlimited model fusion — MUSE chooses any OpenRouter-accessible model slug
- Multi-round iterative refinement — output of round N feeds round N+1 context
- Parallel reference dispatch via asyncio.gather
- Graceful degradation: continues when individual models fail
- Two fusion strategies: ``parallel`` (ref → aggregator) and ``single`` (raw poll)
- Retry-safe with exponential backoff on rate/transient errors
- Debug mode via MOA_TOOLS_DEBUG=true

Architecture
-----------
Layer 0 (Reference, R): N reference models produce diverse initial responses
    in parallel. N is chosen by MUSE — no upper bound.

Layer 0..K (Iterative fusion, optional): When ``rounds > 1``, each round
    feeds the previous round's fused output back into the reference prompts
    as additional context, allowing later rounds to build on earlier
    consensus while still exploring diverse reasoning paths.

Layer F (Fusion / Aggregator): The aggregator model (also chosen by MUSE)
    synthesizes all reference responses into a single fused output.

Failure tolerance
-----------------
Any reference model may fail (rate limit, timeout, 4xx) — we drop it from
the round and proceed as long as at least ``MIN_SUCCESSFUL_REFERENCES``
models succeed. The fused output carries a ``failed_models`` footnote so
MUSE can see what was lost.
"""

import datetime
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import asyncio

from agent.auxiliary_client import extract_content_or_reasoning
from tools.debug_helpers import DebugSession
from tools.openrouter_client import (
    check_api_key as check_openrouter_api_key,
    get_async_client as _get_openrouter_client,
)

logger = logging.getLogger(__name__)

_debug = DebugSession("moa_tools", env_var="MOA_TOOLS_DEBUG")


# ---------------------------------------------------------------------------
# Defaults — used when MUSE doesn't specify models or wants the stock set.
# Aligned with currently top-tier frontier OpenRouter slugs. Kept as module
# constants so tests/tests_mixture_of_agents_tool.py can assert on shape.
# ---------------------------------------------------------------------------
REFERENCE_MODELS = [
    "anthropic/claude-opus-4.6",
    "google/gemini-2.5-pro",
    "openai/gpt-5.4-pro",
    "deepseek/deepseek-v3.2",
]

AGGREGATOR_MODEL = "anthropic/claude-opus-4.6"

# Sampling temperatures — per-role, tuned for diversity-vs-precision balance.
REFERENCE_TEMPERATURE = 0.6
AGGREGATOR_TEMPERATURE = 0.4

# Failure tolerance: minimum successful reference responses required before
# the aggregator is allowed to run.
MIN_SUCCESSFUL_REFERENCES = 1

# Safety floor — the orchestrator can ask for many models, but we cap
# concurrency per request to avoid hammering the upstream aggregator.
MAX_CONCURRENT_REQUESTS = 8

# Maximum fusion rounds (iterative refinement). 5 is plenty for the hardest
# published benchmarks; higher values tend to converge on the aggregator's
# prior rather than produce new signal.
MAX_ROUNDS = 5


# ---------------------------------------------------------------------------
# Aggregator system prompts
# ---------------------------------------------------------------------------
AGGREGATOR_SYSTEM_PROMPT = (
    "You are a synthesis engine. You have been provided with a set of "
    "independent responses from diverse frontier models to the same query. "
    "Your task is to produce a single, high-quality fused response.\n\n"
    "Principles:\n"
    "- Cross-check claims between models; resolve contradictions carefully.\n"
    "- Preserve the strongest reasoning chain from any source.\n"
    "- Do NOT produce a list of 'model A says X, model B says Y' — synthesize.\n"
    "- If models disagree on a factual claim, prefer the reasoning with the "
    "clearest derivation or the most cited grounding.\n"
    "- Produce a complete, self-contained answer. The user has NOT seen the "
    "individual model responses.\n"
)

AGGREGATOR_MULTI_ROUND_PROMPT = (
    "You are synthesizing a second-pass (or later) fused response. The "
    "'previous fused output' below is the best synthesis from the prior "
    "round. The numbered reference responses are freshly generated — they "
    "saw the prior fusion as additional context, so they may refine or "
    "diverge from it. Produce the best single fused response you can.\n\n"
)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _needs_temperature(model: str) -> bool:
    """Some model families reject custom temperature on sampling-only endpoints."""
    m = (model or "").lower()
    # OpenAI GPT family (o1, o3, gpt-5.x) enforces server-chosen temperature
    # on reasoning endpoints; sending a custom value errors the request.
    if m.startswith(("openai/o", "openai/gpt-5", "openai/gpt-4.1")):
        return False
    if m.startswith(("o1", "o3", "gpt-5")):
        return False
    return True


async def _run_reference_model_safe(
    model: str,
    user_prompt: str,
    temperature: float = REFERENCE_TEMPERATURE,
    max_tokens: int = 32000,
    max_retries: int = 4,
    prior_fusion: Optional[str] = None,
    model_label: Optional[str] = None,
    provider: str = "openrouter",
) -> Tuple[str, str, bool]:
    """Query a single reference model with retry + graceful failure.

    Args:
        model: OpenRouter model slug (e.g. "anthropic/claude-sonnet-4").
        user_prompt: The user's original problem.
        temperature: Sampling temperature (skipped for models that reject it).
        max_tokens: Hard output cap.
        max_retries: Total attempts before giving up.
        prior_fusion: If set, prepended to the prompt as "previous round's
            fused output" — used by round 2+ in iterative fusion.
        model_label: Display label; defaults to ``model``.

    Returns:
        ``(model_slug, content_or_error, success)``
    """
    label = model_label or model

    # Build the message once — it's static across retries.
    messages: List[Dict[str, str]] = []
    if prior_fusion:
        messages.append({
            "role": "system",
            "content": (
                "You are a reference expert collaborating with other frontier "
                "models in a multi-round mixture of agents. Below is the "
                "previous round's fused output from the synthesis layer. Use "
                "it to refine your reasoning — don't just repeat it, identify "
                "what's missing or wrong and improve on it.\n\n"
                "=== Previous fused output ===\n"
                f"{prior_fusion}\n"
                "=== End previous fused output ==="
            ),
        })
    messages.append({"role": "user", "content": user_prompt})

    api_params: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "extra_body": {"reasoning": {"enabled": True, "effort": "xhigh"}},
    }
    if _needs_temperature(model):
        api_params["temperature"] = temperature

    last_error: Optional[str] = None
    for attempt in range(max_retries):
        try:
            logger.info("[%s] querying %s via %s (attempt %d/%d)", label, model, provider, attempt + 1, max_retries)
            response = await _get_openrouter_client(provider).chat.completions.create(**api_params)
            content = extract_content_or_reasoning(response)
            if not content:
                if attempt < max_retries - 1:
                    logger.warning(
                        "%s returned empty content (attempt %d/%d), retrying",
                        model, attempt + 1, max_retries,
                    )
                    await asyncio.sleep(min(2 ** (attempt + 1), 60))
                    continue
                return model, f"{model} returned empty content after {max_retries} attempts", False
            logger.info("[%s] responded (%d chars)", label, len(content))
            return model, content, True
        except Exception as e:
            last_error = str(e)
            error_lower = last_error.lower()
            # Classify the failure for the warning message so logs are
            # scannable — same categories as the original implementation.
            if "invalid" in error_lower:
                logger.warning(
                    "%s invalid request error (attempt %d/%d): %s",
                    model, attempt + 1, max_retries, last_error,
                )
            elif "rate" in error_lower or "limit" in error_lower:
                logger.warning(
                    "%s rate limit error (attempt %d/%d): %s",
                    model, attempt + 1, max_retries, last_error,
                )
            else:
                logger.warning(
                    "%s error (attempt %d/%d): %s",
                    model, attempt + 1, max_retries, last_error,
                )

            if attempt < max_retries - 1:
                sleep_time = min(2 ** (attempt + 1), 60)
                logger.info("Retrying in %ds...", sleep_time)
                await asyncio.sleep(sleep_time)
            else:
                msg = f"{model} failed after {max_retries} attempts: {last_error}"
                logger.error("%s", msg, exc_info=True)
                return model, msg, False


def _build_aggregator_messages(
    user_prompt: str,
    reference_responses: List[Tuple[str, str]],
    prior_fusion: Optional[str] = None,
    *,
    label_responses: bool = True,
) -> List[Dict[str, str]]:
    """Construct the full message list for the aggregator pass.

    Args:
        user_prompt: Original user query (passed as the user turn).
        reference_responses: ``(model_slug, content)`` pairs from the reference layer.
        prior_fusion: If set, the fused output of the prior round (system preamble).
        label_responses: Prefix each response with ``[model_slug]:`` for traceability.
    """
    system_parts: List[str] = []
    if prior_fusion:
        system_parts.append(AGGREGATOR_MULTI_ROUND_PROMPT)
        system_parts.append(
            "=== Previous fused output ===\n"
            f"{prior_fusion}\n"
            "=== End previous fused output ===\n\n"
        )
    system_parts.append(AGGREGATOR_SYSTEM_PROMPT)
    system_parts.append("\n=== Reference responses ===\n")

    for i, (m, content) in enumerate(reference_responses, start=1):
        prefix = f"[{m}]: " if label_responses else ""
        system_parts.append(f"{i}. {prefix}{content}\n")

    system_parts.append("=== End reference responses ===")

    return [
        {"role": "system", "content": "\n".join(system_parts)},
        {"role": "user", "content": user_prompt},
    ]


async def _run_aggregator_model(
    messages: List[Dict[str, str]],
    aggregator_model: str,
    temperature: float = AGGREGATOR_TEMPERATURE,
    max_tokens: Optional[int] = None,
    provider: str = "openrouter",
) -> str:
    """Run the aggregator synthesis pass.

    Uses the centralized OpenRouter client so it inherits the same auth,
    rate-limit retry, and provider-preference plumbing as reference models.
    """
    logger.info("Fusion pass: aggregator=%s", aggregator_model)
    api_params: Dict[str, Any] = {
        "model": aggregator_model,
        "messages": messages,
        "extra_body": {"reasoning": {"enabled": True, "effort": "xhigh"}},
    }
    if max_tokens is not None:
        api_params["max_tokens"] = max_tokens
    if _needs_temperature(aggregator_model):
        api_params["temperature"] = temperature

    response = await _get_openrouter_client(provider).chat.completions.create(**api_params)
    content = extract_content_or_reasoning(response)
    if not content:
        # One retry on the aggregator — empty content is a reasoning-only
        # response artifact on some frontiers.
        logger.warning("Aggregator returned empty content, retrying once")
        response = await _get_openrouter_client(provider).chat.completions.create(**api_params)
        content = extract_content_or_reasoning(response)
        if not content:
            raise RuntimeError(
                f"Aggregator {aggregator_model} returned empty content after retry"
            )
    logger.info("Fusion output: %d chars", len(content))
    return content


# ---------------------------------------------------------------------------
# Public fusion entry-point
# ---------------------------------------------------------------------------

async def mixture_of_agents_tool(
    user_prompt: str,
    reference_models: Optional[List[str]] = None,
    aggregator_model: Optional[str] = None,
    rounds: int = 1,
    strategy: str = "parallel",
    max_tokens: Optional[int] = None,
    provider: str = "openrouter",
) -> str:
    """Fuse the reasoning of multiple LLMs into a single high-quality answer.

    Orchestrated by MUSE — every parameter is choosable at call time. There
    is no upper bound on ``len(reference_models)`` other than the concurrency
    cap per request (MAX_CONCURRENT_REQUESTS).

    Args:
        user_prompt: The problem to solve.
        reference_models: OpenRouter model slugs to poll. Defaults to
            ``REFERENCE_MODELS`` when None or empty.
        aggregator_model: OpenRouter model slug for synthesis. Defaults to
            ``AGGREGATOR_MODEL``. Ignored when ``strategy="single"``.
        rounds: Iterative fusion rounds (1..MAX_ROUNDS). Round 2+ feeds
            the prior round's fused output back to both reference models
            and the aggregator. Ignored when ``strategy="single"``.
        strategy: ``"parallel"`` (default, reference → aggregator fusion) or
            ``"single"`` (raw poll — return all responses unmodified for
            the orchestrator's own synthesis).
        max_tokens: Cap on final fused response length. Applies to the
            aggregator only.

    Returns:
        JSON-encoded string.
    """
    start = datetime.datetime.now()

    # --- Resolve parameters ---
    ref_models = list(reference_models) if reference_models else list(REFERENCE_MODELS)
    agg_model = aggregator_model or AGGREGATOR_MODEL
    if not ref_models:
        return json.dumps({
            "success": False,
            "error": "reference_models is empty and no defaults could be loaded.",
        })
    rounds = max(1, min(int(rounds or 1), MAX_ROUNDS))
    if strategy not in ("parallel", "single"):
        strategy = "parallel"

    debug_payload: Dict[str, Any] = {
        "parameters": {
            "user_prompt": (user_prompt[:200] + "…") if len(user_prompt) > 200 else user_prompt,
            "reference_models": ref_models,
            "aggregator_model": agg_model,
            "rounds": rounds,
            "strategy": strategy,
        },
        "rounds_executed": [],
        "success": False,
    }

    try:
        if not check_openrouter_api_key(provider):
            raise RuntimeError(f"{provider} provider credentials are not configured")

        logger.info(
            "MoA start — refs=%d agg=%s rounds=%d strategy=%s",
            len(ref_models), agg_model, rounds, strategy,
        )

        # Per-round state
        prior_fusion: Optional[str] = None
        all_round_summaries: List[Dict[str, Any]] = []
        final_response: Optional[str] = None

        # Concurrency limit — protects against upstream aggregator throttling
        # even when MUSE requests 20+ models.
        sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        async def _bounded_ref(model: str, prompt: str, prior: Optional[str], label: str):
            async with sem:
                return await _run_reference_model_safe(
                    model, prompt, REFERENCE_TEMPERATURE,
                    max_tokens=32000, max_retries=4,
                    prior_fusion=prior, model_label=label,
                    provider=provider,
                )

        for round_idx in range(rounds):
            round_num = round_idx + 1
            round_label = f"R{round_num}"
            logger.info(
                "[%s] Querying %d reference model(s)%s",
                round_label, len(ref_models),
                f" (with prior fusion context from R{round_num - 1})" if prior_fusion else "",
            )

            # Fan out reference models in parallel
            ref_tasks = [
                _bounded_ref(m, user_prompt, prior_fusion, f"{round_label}:{m}")
                for m in ref_models
            ]
            results: List[Tuple[str, str, bool]] = list(await asyncio.gather(*ref_tasks))

            successes = [(m, c) for (m, c, ok) in results if ok]
            failures = [m for (m, _c, ok) in results if not ok]

            logger.info(
                "[%s] %d/%d succeeded, %d failed",
                round_label, len(successes), len(ref_models), len(failures),
            )

            if len(successes) < MIN_SUCCESSFUL_REFERENCES:
                raise RuntimeError(
                    f"Insufficient successful references in round {round_num}: "
                    f"{len(successes)}/{len(ref_models)} "
                    f"(need ≥{MIN_SUCCESSFUL_REFERENCES}). Failed: {failures}"
                )

            all_round_summaries.append({
                "round": round_num,
                "succeeded": [m for m, _ in successes],
                "failed": failures,
                "reference_count": len(successes),
                "prior_fusion_used": prior_fusion is not None,
            })

            # --- Strategy: single (no aggregator, return raw) ---
            if strategy == "single":
                final_response = "\n\n---\n\n".join(
                    f"### {m}\n{c}" for m, c in successes
                )
                break  # single strategy ignores rounds > 1

            # --- Strategy: parallel (default) — aggregate ---
            messages = _build_aggregator_messages(
                user_prompt, successes, prior_fusion=prior_fusion,
            )
            fused = await _run_aggregator_model(
                messages, agg_model, AGGREGATOR_TEMPERATURE, max_tokens,
                provider=provider,
            )
            prior_fusion = fused

            if round_idx == rounds - 1:
                final_response = fused

        # Defensive — single-strategy branch already assigned; parallel loop
        # always ends on the last round which also assigns.
        if final_response is None:
            final_response = prior_fusion or ""

        elapsed = (datetime.datetime.now() - start).total_seconds()
        logger.info("MoA done — %.2fs, %d round(s), %d chars fused",
                    elapsed, rounds, len(final_response))

        result = {
            "success": True,
            "response": final_response,
            "metadata": {
                "reference_models": ref_models,
                "aggregator_model": agg_model if strategy != "single" else None,
                "strategy": strategy,
                "provider": provider,
                "rounds_requested": rounds,
                "rounds_executed": all_round_summaries,
                "total_api_calls": sum(
                    r["reference_count"] + (1 if strategy == "parallel" else 0)
                    for r in all_round_summaries
                ),
                "processing_time_seconds": round(elapsed, 2),
                "response_length": len(final_response),
            },
        }

        debug_payload["success"] = True
        debug_payload["rounds_executed"] = all_round_summaries
        debug_payload["processing_time_seconds"] = result["metadata"]["processing_time_seconds"]
        _debug.log_call("mixture_of_agents", debug_payload)
        _debug.save()

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        elapsed = (datetime.datetime.now() - start).total_seconds()
        detail = f"{type(e).__name__}: {e}"
        msg = f"Error in MoA processing: {detail}"
        logger.error("%s", msg, exc_info=True)

        error_payload = {
            "success": False,
            "error": msg,
            "metadata": {
                "reference_models": ref_models,
                "aggregator_model": agg_model,
                "provider": provider,
                "rounds_requested": rounds,
                "rounds_executed": all_round_summaries,
                "processing_time_seconds": round(elapsed, 2),
            },
        }
        debug_payload["error"] = msg
        debug_payload["rounds_executed"] = all_round_summaries
        _debug.log_call("mixture_of_agents", debug_payload)
        _debug.save()
        return json.dumps(error_payload, indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# Requirements + configuration helpers
# ---------------------------------------------------------------------------

def check_moa_requirements() -> bool:
    """MoA needs at least one configured fusion provider credential."""
    return check_openrouter_api_key("openrouter") or check_openrouter_api_key("nvidia")


def get_moa_configuration() -> Dict[str, Any]:
    """Return current module configuration (for diagnostics / tests)."""
    return {
        "reference_models": REFERENCE_MODELS,
        "aggregator_model": AGGREGATOR_MODEL,
        "reference_temperature": REFERENCE_TEMPERATURE,
        "aggregator_temperature": AGGREGATOR_TEMPERATURE,
        "min_successful_references": MIN_SUCCESSFUL_REFERENCES,
        "max_concurrent_requests": MAX_CONCURRENT_REQUESTS,
        "max_rounds": MAX_ROUNDS,
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
from tools.registry import registry  # noqa: E402 (must be after function defs)

MOA_SCHEMA = {
    "name": "mixture_of_agents",
    "description": (
        "Fuse reasoning from multiple LLMs into a single high-quality answer. "
        "You (MUSE) choose which models to poll, how many to query in parallel, "
        "and which model serves as the synthesis aggregator. There is no upper "
        "limit on the number of models — add more for harder problems. Supports "
        "multi-round iterative fusion where later rounds refine earlier output. "
        "Use sparingly on genuinely difficult problems: complex math, advanced "
        "algorithms, multi-step analytical reasoning, architecture decisions, "
        "or problems benefitting from diverse expert perspectives."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "user_prompt": {
                "type": "string",
                "description": (
                    "The complex query or problem to solve. State it as a complete, "
                    "self-contained prompt — each reference model receives this verbatim."
                ),
            },
            "reference_models": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "List of OpenRouter model slugs (e.g. 'anthropic/claude-sonnet-4', "
                    "'google/gemini-2.5-pro', 'deepseek/deepseek-r1', 'x-ai/grok-4', "
                    "'meta-llama/llama-3.3-70b-instruct') to poll for diverse initial "
                    "responses. Default: 4 frontier models. No upper limit — add more "
                    "for harder problems. Pick models from different families or "
                    "training paradigms for maximum diversity."
                ),
            },
            "aggregator_model": {
                "type": "string",
                "description": (
                    "OpenRouter model slug used to synthesize the final fused response. "
                    "Default: 'anthropic/claude-opus-4.6'. Use the strongest model you "
                    "have access to — the aggregator has to reconcile and improve on "
                    "all reference outputs."
                ),
            },
            "rounds": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_ROUNDS,
                "description": (
                    "Iterative fusion rounds. 1 = single pass (default). 2 or more: "
                    "each round feeds the previous round's fused output back to all "
                    "reference models as context, so later rounds refine earlier "
                    "consensus. Use rounds=2-3 for the hardest problems; returns "
                    "diminishing signal beyond 3 rounds."
                ),
            },
            "strategy": {
                "type": "string",
                "enum": ["parallel", "single"],
                "description": (
                    "'parallel' (default): reference models produce responses, then "
                    "the aggregator fuses them into a single answer. 'single': return "
                    "all raw reference responses unmodified — useful when you want to "
                    "do your own synthesis or just see a model poll."
                ),
            },
            "provider": {
                "type": "string",
                "description": "Provider client to use: openrouter (default), nvidia, or nvidia-all.",
            },
        },
        "required": ["user_prompt"],
    },
}

registry.register(
    name="mixture_of_agents",
    toolset="moa",
    schema=MOA_SCHEMA,
    handler=lambda args, **kw: mixture_of_agents_tool(
        user_prompt=args.get("user_prompt", ""),
        reference_models=args.get("reference_models"),
        aggregator_model=args.get("aggregator_model"),
        rounds=args.get("rounds", 1),
        strategy=args.get("strategy", "parallel"),
        max_tokens=args.get("max_tokens"),
        provider=args.get("provider", "openrouter"),
    ),
    check_fn=check_moa_requirements,
    requires_env=[],
    is_async=True,
    emoji="🧠",
)


# ---------------------------------------------------------------------------
# Direct run: quick sanity/diagnostic CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("MUSE Mixture-of-Agents — Unlimited Fusion")
    print("=" * 52)

    if not check_openrouter_api_key():
        print("OPENROUTER_API_KEY not set. Set it in ~/.hermes/.env or your shell.")
        print("Get a key at: https://openrouter.ai/")
        sys.exit(1)
    print("OPENROUTER_API_KEY: OK")

    cfg = get_moa_configuration()
    print(f"Default reference models ({len(cfg['reference_models'])}):")
    for m in cfg["reference_models"]:
        print(f"  - {m}")
    print(f"Default aggregator:  {cfg['aggregator_model']}")
    print(f"Max concurrent refs: {cfg['max_concurrent_requests']}")
    print(f"Max fusion rounds:   {cfg['max_rounds']}")
    print(f"Debug mode:          {'ON' if _debug.active else 'off (set MOA_TOOLS_DEBUG=true)'}")

    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        print(f"\nFusing: {prompt!r}")
        print("-" * 52)
        result = asyncio.run(mixture_of_agents_tool(user_prompt=prompt))
        data = json.loads(result)
        if data.get("success"):
            print(data["response"])
            print("-" * 52)
            print(f"Models: {data['metadata']['reference_models']}")
            print(f"Time:   {data['metadata']['processing_time_seconds']}s")
        else:
            print(f"FAILED: {data.get('error')}")
    else:
        print("\nUsage: python -m tools.mixture_of_agents_tool \"<your hard problem>\"")
