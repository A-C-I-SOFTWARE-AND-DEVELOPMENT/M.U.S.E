#!/usr/bin/env python3
"""Model-invocable Mixture-of-Agents fan-out tool.

Hermes already ships MoA as a *provider* (``provider: moa``, see
``agent/moa_loop.py`` and ``hermes_cli/moa_config.py``): selecting a MoA preset
turns every turn of the session into a reference fan-out plus an aggregator
synthesis. That is a session-level mode — the user opts in, and it applies to
the whole conversation.

This tool exposes the same machinery as a *tool the model can call*. Mid-turn,
the acting model can hand one self-contained sub-question to a panel of models,
get a single fused answer back, and carry on with its normal loop — without the
user having to switch the session onto the MoA provider, and without the rest of
the turn paying for a fan-out.

Rebased on the existing MoA runtime rather than talking to any one provider
directly:

- Model slots come from ``hermes_cli.moa_config`` presets, so the tool honours
  whatever the user configured with ``hermes moa`` — local models, Anthropic,
  Codex, OpenRouter, anything ``resolve_runtime_provider`` can reach.
- The fan-out runs through ``agent.moa_loop._run_references_parallel``, which
  resolves each slot's real API surface, trims to each reference's context
  window, applies prompt-cache decoration, and prices every advisor at its own
  model's rate.
- The synthesis call goes through ``agent.auxiliary_client.call_llm`` with the
  aggregator slot's resolved runtime and reasoning config, exactly like the
  provider path's aggregator.

What it adds on top of the provider path is the tool surface itself plus two
call-time knobs the provider facade has no place for: multi-round iterative
refinement (round N+1's advisors see round N's fusion) and a ``raw`` strategy
that returns the unfused panel when the caller wants to do its own synthesis.

Debug tracing: set ``MOA_TOOLS_DEBUG=true``.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from tools.debug_helpers import DebugSession

logger = logging.getLogger(__name__)

_debug = DebugSession("moa_tools", env_var="MOA_TOOLS_DEBUG")


# Upper bound on iterative fusion rounds. Beyond ~3 the panel converges on the
# aggregator's prior instead of producing new signal, and every extra round
# re-bills the whole panel.
MAX_ROUNDS = 5

# Upper bound on how many reference models ONE CALL may name. Matches
# ``agent.moa_loop._MAX_REFERENCE_WORKERS``, so a caller that names more than
# the fan-out can run at once gets a clear error instead of silently queueing.
# It bounds caller overrides only — a preset the user configured by hand is
# never rejected; the fan-out queues the surplus behind its worker pool.
MAX_REFERENCE_MODELS = 8


# The advisory system prompt lives in agent/moa_loop.py and frames a reference
# as "advise the acting agent about this conversation". This tool's references
# are answering a delegated self-contained question instead, so the user turn
# re-frames the task explicitly rather than forking that prompt.
_REFERENCE_TASK_FRAME = (
    "An agent has delegated the self-contained question below to you as one of "
    "several independent expert advisors working in parallel. Answer it "
    "directly and completely — do not ask for access to anything, and do not "
    "describe what someone else should do. A synthesis model will fuse your "
    "answer with the other advisors' answers into one final response.\n\n"
    "=== Question ===\n{prompt}\n=== End question ==="
)

_REFERENCE_REFINE_FRAME = (
    "The message above is the previous round's fused answer, produced by the "
    "synthesis model from the whole advisory panel (including you). Improve on "
    "it: say what is missing, wrong, or under-argued, then give your best "
    "complete answer to the original question. Do not simply restate the "
    "fusion."
)

_FUSION_PROMPT = (
    "You are the synthesis layer of a Mixture-of-Agents panel. Below are "
    "independent answers from several models to the same self-contained "
    "question. Produce ONE fused answer.\n\n"
    "Principles:\n"
    "- Cross-check claims between advisors and resolve contradictions "
    "deliberately rather than averaging them.\n"
    "- Keep the strongest reasoning chain from any source.\n"
    "- Do NOT narrate the panel ('advisor 1 says X, advisor 2 says Y') — "
    "synthesize a single voice.\n"
    "- Where advisors disagree on a fact, prefer the claim with the clearest "
    "derivation or the most specific grounding, and say so briefly.\n"
    "- The reader has NOT seen the individual answers. The fused answer must "
    "stand on its own.\n"
)

_FUSION_REFINE_PREAMBLE = (
    "This is a second-pass (or later) fusion. The previous round's fused "
    "answer is included below for reference; the advisor answers that follow "
    "are freshly generated and saw that fusion as context, so they may refine "
    "or contradict it. Produce the best single fused answer you can.\n\n"
)


# ---------------------------------------------------------------------------
# Slot resolution — everything comes from the configured MoA presets
# ---------------------------------------------------------------------------

def _moa_config() -> Any:
    """Return the live ``moa`` config section (``{}`` when unset)."""
    try:
        from hermes_cli.config import load_config

        return (load_config() or {}).get("moa") or {}
    except Exception:  # pragma: no cover - defensive; defaults still apply
        logger.debug("MoA tool: config load failed", exc_info=True)
        return {}


def _parse_slot(item: Any) -> dict[str, Any] | None:
    """Coerce one caller-supplied model spec into a MoA slot dict.

    Accepts the ``"provider:model"`` string form (split on the FIRST colon, so
    model ids containing colons like ``ollama:qwen3:8b`` survive) and the
    object form ``{"provider": ..., "model": ..., "reasoning_effort": ...}``.

    Returns ``None`` for anything incomplete or for ``provider: moa`` — a MoA
    preset inside a MoA slot is the recursion the provider path also rejects
    (``hermes_cli.moa_config._clean_slot``).
    """
    effort = ""
    if isinstance(item, dict):
        provider = str(item.get("provider") or "").strip()
        model = str(item.get("model") or "").strip()
        effort = str(item.get("reasoning_effort") or "").strip()
    elif isinstance(item, str):
        provider, sep, model = item.strip().partition(":")
        if not sep:
            return None
        provider, model = provider.strip(), model.strip()
    else:
        return None
    if not provider or not model or provider.lower() == "moa":
        return None
    slot: dict[str, Any] = {"provider": provider, "model": model, "enabled": True}
    if effort:
        slot["reasoning_effort"] = effort
    return slot


def _describe(item: Any) -> str:
    return item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)


def _as_override_list(value: Any) -> list[Any] | None:
    """Normalize a caller-supplied panel override into a list, or ``None``.

    The schema asks for an array, but models routinely emit a single string, a
    single object, or a JSON-encoded array instead. Coercing those is the
    difference between honouring the override and silently answering with the
    preset's panel — the exact silent fallback this tool promises not to do.
    ``None``/empty means "no override"; anything else unusable raises.
    """
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.startswith("["):
            try:
                return _as_override_list(json.loads(text))
            except (json.JSONDecodeError, ValueError):
                return [text]
        return [text]
    if isinstance(value, dict):
        return [value]
    if isinstance(value, (list, tuple)):
        return list(value) or None
    raise ValueError(
        "reference_models must be an array of 'provider:model' strings. "
        f"Rejected: {_describe(value)}"
    )


def _resolve_panel(
    preset_name: str | None,
    reference_models: Any,
    aggregator_model: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Resolve ``(preset, reference slots, aggregator slot)``.

    Raises ``ValueError`` with a model-readable message when a caller override
    cannot be parsed, so the tool answers with a fixable error instead of
    silently falling back to models the caller did not ask for.
    """
    from hermes_cli.moa_config import resolve_moa_preset

    preset = resolve_moa_preset(_moa_config(), preset_name)

    refs: list[dict[str, Any]]
    override = _as_override_list(reference_models)
    if override:
        refs = []
        bad: list[str] = []
        for item in override:
            slot = _parse_slot(item)
            if slot is None:
                bad.append(_describe(item))
            else:
                refs.append(slot)
        if bad:
            raise ValueError(
                "reference_models entries must be 'provider:model' strings or "
                "{provider, model} objects, and may not use the 'moa' provider "
                f"(recursive MoA). Rejected: {', '.join(bad)}"
            )
        # Bounds the *caller*, not the user: a model naming twenty panelists is
        # a mistake worth an error. A preset the user configured by hand is
        # never rejected — the fan-out queues slots past its worker cap.
        if len(refs) > MAX_REFERENCE_MODELS:
            raise ValueError(
                f"Too many reference models ({len(refs)}); name at most "
                f"{MAX_REFERENCE_MODELS}."
            )
    else:
        refs = [
            slot
            for slot in preset.get("reference_models") or []
            if slot.get("enabled", True)
        ]

    if not refs:
        raise ValueError(
            "No reference models are configured for this MoA preset. Run "
            "`hermes moa` to configure one, or pass reference_models."
        )

    if aggregator_model:
        aggregator = _parse_slot(aggregator_model)
        if aggregator is None:
            raise ValueError(
                "aggregator_model must be a 'provider:model' string or a "
                "{provider, model} object, and may not use the 'moa' provider. "
                f"Rejected: {_describe(aggregator_model)}"
            )
    else:
        aggregator = dict(preset.get("aggregator") or {})
    if not aggregator.get("provider") or not aggregator.get("model"):
        raise ValueError(
            "No aggregator model is configured for this MoA preset. Run "
            "`hermes moa` to configure one, or pass aggregator_model."
        )
    return preset, refs, aggregator


# ---------------------------------------------------------------------------
# Round mechanics
# ---------------------------------------------------------------------------

def _reference_view(user_prompt: str, prior_fusion: str | None) -> list[dict[str, Any]]:
    """Build the advisory conversation handed to every reference model."""
    view: list[dict[str, Any]] = [
        {"role": "user", "content": _REFERENCE_TASK_FRAME.format(prompt=user_prompt)}
    ]
    if prior_fusion:
        view.append({"role": "assistant", "content": prior_fusion})
        view.append({"role": "user", "content": _REFERENCE_REFINE_FRAME})
    return view


def _fusion_messages(
    user_prompt: str,
    answers: list[tuple[str, str]],
    prior_fusion: str | None,
) -> list[dict[str, Any]]:
    """Build the synthesis request for one round."""
    parts: list[str] = []
    if prior_fusion:
        parts.append(_FUSION_REFINE_PREAMBLE)
        parts.append(
            "=== Previous fused answer ===\n"
            f"{prior_fusion}\n"
            "=== End previous fused answer ===\n"
        )
    parts.append(_FUSION_PROMPT)
    parts.append(f"\n=== Question ===\n{user_prompt}\n=== End question ===\n")
    parts.append("=== Advisor answers ===")
    for idx, (label, text) in enumerate(answers, start=1):
        parts.append(f"{idx}. [{label}]\n{text}\n")
    parts.append("=== End advisor answers ===")
    return [{"role": "user", "content": "\n".join(parts)}]


def _run_fusion(
    aggregator: dict[str, Any],
    messages: list[dict[str, Any]],
    *,
    temperature: float | None,
    max_tokens: int | None,
) -> str:
    """Run the synthesis call on the aggregator slot's resolved runtime.

    Mirrors ``agent.moa_loop.aggregate_moa_context``'s aggregator call: the
    slot is resolved through ``_slot_runtime`` (the real base_url/api_key/
    api_mode for that provider), its reasoning depth resolves slot > per-model
    > global, and the request carries the same Anthropic-style cache_control
    decoration the provider path uses, so a repeated fusion on a cache-honoring
    route is not re-billed in full.
    """
    from agent.auxiliary_client import call_llm
    from agent.moa_loop import (
        _aggregator_reasoning_config,
        _extract_text,
        _maybe_apply_moa_cache_control,
        _slot_runtime,
    )

    runtime = _slot_runtime(aggregator)
    response = call_llm(
        task="moa_aggregator",
        messages=_maybe_apply_moa_cache_control(messages, runtime),
        temperature=temperature,
        # None by default: call_llm omits max_tokens entirely, so the fused
        # answer uses the aggregator's own maximum. A hardcoded cap here
        # truncates long syntheses (the provider path hit exactly that).
        max_tokens=max_tokens,
        reasoning_config=_aggregator_reasoning_config(aggregator),
        **runtime,
    )
    return _extract_text(response)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def mixture_of_agents_tool(
    user_prompt: str,
    reference_models: Any = None,
    aggregator_model: Any = None,
    preset: str | None = None,
    rounds: Any = 1,
    strategy: str = "fused",
) -> str:
    """Fan one question out to a panel of models and fuse their answers.

    Args:
        user_prompt: The self-contained question. Every reference model
            receives it verbatim, so it must carry its own context.
        reference_models: Optional override of the panel — ``"provider:model"``
            strings or ``{provider, model}`` objects. Defaults to the preset's
            enabled reference slots.
        aggregator_model: Optional override of the synthesis model. Defaults to
            the preset's aggregator. Unused when ``strategy="raw"``.
        preset: Name of a configured MoA preset (``hermes moa list``). Defaults
            to the configured default preset.
        rounds: Iterative fusion rounds, 1..``MAX_ROUNDS``. Round 2+ shows the
            panel the previous round's fusion. Ignored when ``strategy="raw"``.
        strategy: ``"fused"`` (default) or ``"raw"`` (return the unfused panel).

    Returns:
        A JSON string: ``{"success", "response", "metadata"}`` on success, or
        ``{"success": false, "error"}``.
    """
    from agent.moa_loop import (
        _degraded_notice,
        _failed_reference_labels,
        _run_references_parallel,
        _slot_label,
        _successful_references,
    )
    from hermes_cli.moa_config import _coerce_int

    started = time.monotonic()
    prompt = str(user_prompt or "").strip()

    debug_payload: dict[str, Any] = {
        "parameters": {
            "user_prompt": prompt[:200] + ("…" if len(prompt) > 200 else ""),
            "preset": preset,
            "rounds": rounds,
            "strategy": strategy,
        },
        "rounds_executed": [],
        "success": False,
    }

    def _fail(message: str) -> str:
        debug_payload["error"] = message
        _debug.log_call("mixture_of_agents", debug_payload)
        _debug.save()
        return json.dumps(
            {"success": False, "error": message}, indent=2, ensure_ascii=False
        )

    if not prompt:
        return _fail("user_prompt is required and must be a non-empty question.")

    strategy = str(strategy or "fused").strip().lower()
    if strategy not in ("fused", "raw"):
        strategy = "fused"
    rounds_requested = max(1, min(_coerce_int(rounds, 1), MAX_ROUNDS))
    if strategy == "raw":
        # Refinement rounds only exist to improve a fusion; without one there
        # is nothing to feed back, so extra rounds would just re-bill the panel.
        rounds_requested = 1

    try:
        panel_preset, refs, aggregator = _resolve_panel(
            preset, reference_models, aggregator_model
        )
    except ValueError as exc:
        return _fail(str(exc))
    except Exception as exc:
        # MoAPresetNotFoundError already names the available presets.
        return _fail(f"{type(exc).__name__}: {exc}")

    ref_labels = [_slot_label(slot) for slot in refs]
    agg_label = _slot_label(aggregator)
    debug_payload["parameters"]["reference_models"] = ref_labels
    debug_payload["parameters"]["aggregator_model"] = agg_label

    degraded_policy = str(panel_preset.get("degraded_reference_policy") or "loud")
    round_summaries: list[dict[str, Any]] = []
    prior_fusion: str | None = None
    response_text = ""
    failed: list[str] = []

    logger.info(
        "MoA tool: %d reference(s) %s, aggregator=%s, rounds=%d, strategy=%s",
        len(refs), ref_labels, agg_label, rounds_requested, strategy,
    )

    try:
        for round_idx in range(rounds_requested):
            round_num = round_idx + 1
            outputs = _run_references_parallel(
                refs,
                _reference_view(prompt, prior_fusion),
                temperature=panel_preset.get("reference_temperature"),
                max_tokens=panel_preset.get("reference_max_tokens"),
                reference_timeout=panel_preset.get("reference_timeout"),
            )
            answers = [
                (label, text) for label, text, _acct in _successful_references(outputs)
            ]
            failed = _failed_reference_labels(outputs)
            round_summaries.append({
                "round": round_num,
                "succeeded": [label for label, _text in answers],
                "failed": failed,
                "refined_previous_round": prior_fusion is not None,
            })
            logger.info(
                "MoA tool: round %d — %d/%d references answered",
                round_num, len(answers), len(refs),
            )

            if not answers:
                if prior_fusion:
                    # An earlier round already produced — and paid for — a
                    # fused answer. A later round losing the whole panel means
                    # no *refinement*, not no answer; the degraded notice
                    # appended below discloses which advisors dropped out.
                    logger.warning(
                        "MoA tool: round %d lost the whole panel — returning "
                        "round %d's fusion",
                        round_num, round_num - 1,
                    )
                    response_text = prior_fusion
                    break
                notice = (
                    _degraded_notice(failed, degraded_policy)
                    or "[Reference models unavailable]"
                )
                return _fail(
                    "Every reference model failed, so there was nothing to "
                    f"fuse. {notice}"
                )

            if strategy == "raw":
                response_text = "\n\n---\n\n".join(
                    f"### {label}\n{text}" for label, text in answers
                )
                break

            fused = _run_fusion(
                aggregator,
                _fusion_messages(prompt, answers, prior_fusion),
                temperature=panel_preset.get("aggregator_temperature"),
                max_tokens=None,
            )
            if not fused:
                # Synthesis produced nothing — hand back the panel rather than
                # losing a whole round of paid advisor output.
                logger.warning("MoA tool: aggregator %s returned empty text", agg_label)
                fused = "\n\n---\n\n".join(
                    f"### {label}\n{text}" for label, text in answers
                )
            prior_fusion = fused
            response_text = fused

        notice = _degraded_notice(failed, degraded_policy)
        if notice:
            response_text = f"{response_text}\n\n{notice}"

        elapsed = round(time.monotonic() - started, 2)
        result = {
            "success": True,
            "response": response_text,
            "metadata": {
                "preset": preset or None,
                "reference_models": ref_labels,
                "aggregator_model": agg_label if strategy == "fused" else None,
                "strategy": strategy,
                "rounds_requested": rounds_requested,
                "rounds_executed": round_summaries,
                "failed_models": failed,
                "processing_time_seconds": elapsed,
                "response_length": len(response_text),
            },
        }
        debug_payload["success"] = True
        debug_payload["rounds_executed"] = round_summaries
        debug_payload["processing_time_seconds"] = elapsed
        _debug.log_call("mixture_of_agents", debug_payload)
        _debug.save()
        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as exc:
        logger.exception("MoA tool failed")
        debug_payload["rounds_executed"] = round_summaries
        return _fail(f"Mixture-of-Agents run failed: {type(exc).__name__}: {exc}")


def check_moa_requirements() -> bool:
    """Available whenever a MoA preset resolves to a usable panel.

    There is no single API key to check: each slot carries its own provider,
    and ``_slot_runtime`` resolves that provider's credentials at call time —
    exactly like the ``provider: moa`` path.
    """
    try:
        from hermes_cli.moa_config import resolve_moa_preset

        preset = resolve_moa_preset(_moa_config(), None)
    except Exception:
        return False
    refs = [s for s in preset.get("reference_models") or [] if s.get("enabled", True)]
    aggregator = preset.get("aggregator") or {}
    return bool(refs and aggregator.get("provider") and aggregator.get("model"))


def get_moa_tool_configuration() -> dict[str, Any]:
    """Resolved panel for diagnostics: which models a default call would use."""
    try:
        preset, refs, aggregator = _resolve_panel(None, None, None)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    from agent.moa_loop import _slot_label

    return {
        "reference_models": [_slot_label(slot) for slot in refs],
        "aggregator_model": _slot_label(aggregator),
        "reference_temperature": preset.get("reference_temperature"),
        "aggregator_temperature": preset.get("aggregator_temperature"),
        "reference_max_tokens": preset.get("reference_max_tokens"),
        "reference_timeout": preset.get("reference_timeout"),
        "max_reference_models": MAX_REFERENCE_MODELS,
        "max_rounds": MAX_ROUNDS,
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
from tools.registry import registry  # noqa: E402 (must follow the definitions)

MOA_SCHEMA = {
    "name": "mixture_of_agents",
    "description": (
        "Fan one hard, self-contained question out to a panel of models in "
        "parallel and get back a single fused answer. The panel and the "
        "synthesis model come from the user's configured Mixture-of-Agents "
        "presets, so they may be local, hosted, or a mix; you can override "
        "them per call. Supports multi-round refinement, where each round's "
        "panel sees the previous round's fusion. Expensive — every call bills "
        "every model on the panel — so use it only for genuinely difficult "
        "problems where diverse expert perspectives help: subtle math, "
        "algorithm design, multi-step analysis, architecture trade-offs, or a "
        "claim worth cross-checking independently. Do not use it for routine "
        "questions you can answer yourself."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "user_prompt": {
                "type": "string",
                "description": (
                    "The question to solve. Each panel model receives this "
                    "verbatim and sees nothing else from the conversation, so "
                    "state it as a complete, self-contained prompt including "
                    "any code, data, or constraints they need."
                ),
            },
            "preset": {
                "type": "string",
                "description": (
                    "Name of a configured Mixture-of-Agents preset to draw the "
                    "panel from. Omit to use the user's default preset."
                ),
            },
            "reference_models": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional override of the panel, as 'provider:model' "
                    "strings (e.g. 'openrouter:deepseek/deepseek-v4-pro', "
                    "'anthropic:claude-opus-4-5', 'ollama:qwen3:8b'). Omit to "
                    f"use the preset's panel. At most {MAX_REFERENCE_MODELS} "
                    "models. Pick different model families for real diversity, "
                    "and only name providers the user has configured."
                ),
            },
            "aggregator_model": {
                "type": "string",
                "description": (
                    "Optional override of the synthesis model, as a "
                    "'provider:model' string. Omit to use the preset's "
                    "aggregator. Prefer a strong model — it has to reconcile "
                    "and improve on every panel answer."
                ),
            },
            "rounds": {
                "type": "integer",
                "minimum": 1,
                "maximum": MAX_ROUNDS,
                "description": (
                    "Iterative fusion rounds. 1 (default) is a single pass. "
                    "With 2 or more, each later round shows the panel the "
                    "previous round's fused answer and asks them to improve on "
                    "it. Each round re-bills the whole panel and returns "
                    "diminishing signal past 3."
                ),
            },
            "strategy": {
                "type": "string",
                "enum": ["fused", "raw"],
                "description": (
                    "'fused' (default): the aggregator synthesizes one answer. "
                    "'raw': skip synthesis and return every panel answer "
                    "labelled by model, for when you want to compare them or "
                    "do your own synthesis."
                ),
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
        preset=args.get("preset"),
        rounds=args.get("rounds", 1),
        strategy=args.get("strategy", "fused"),
    ),
    check_fn=check_moa_requirements,
    is_async=False,
    emoji="🧠",
)
