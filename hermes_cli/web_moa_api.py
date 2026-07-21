"""
M.U.S.E. dashboard — Mixture-of-Agents (MoA) API routes.

Exposes the MoA council (tools/mixture_of_agents_tool.py) to the web UI:

    GET  /api/moa/status   — requirements, toolset state, council defaults
    POST /api/moa/run      — async council run: per-model lanes + fused output

Wiring (done by the integrator, NOT in this file)::

    from hermes_cli.web_moa_api import router as moa_router
    app.include_router(moa_router)   # before mount_spa(app)

Auth: this module deliberately does NOT import ``web_server`` (that would be
circular — web_server imports this router). Every route lives under ``/api/``
and none is listed in ``web_server._PUBLIC_API_PATHS``, so the global
``auth_middleware`` in ``hermes_cli/web_server.py`` already gates them with
the ephemeral dashboard session token (``X-Hermes-Session-Token`` header or
legacy ``Authorization: Bearer``). Error conventions mirror web_server:
``HTTPException`` with a plain ``detail`` string; unexpected failures are
logged and surfaced as 500.
"""

import asyncio
import datetime
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/moa", tags=["moa"])


# ---------------------------------------------------------------------------
# Lazy tool-module access — keeps import of this router cheap and lets the
# dashboard boot even if optional MoA dependencies are broken.
# ---------------------------------------------------------------------------

def _moa():
    """Import the MoA tool module on first use."""
    try:
        from tools import mixture_of_agents_tool as moa_module
    except Exception as exc:  # pragma: no cover - environment dependent
        _log.exception("Failed to import tools.mixture_of_agents_tool")
        raise HTTPException(
            status_code=500,
            detail=f"MoA tool module unavailable: {exc}",
        )
    return moa_module


def _toolset_state() -> Dict[str, Any]:
    """Report whether the ``moa`` toolset is enabled for the CLI platform.

    Mirrors the logic behind GET /api/tools/toolsets in web_server.py.
    ``enabled`` is None when the toolset configuration cannot be resolved
    (e.g. tools_config import failure) — the UI renders that as "unknown".
    """
    state: Dict[str, Any] = {
        "name": "moa",
        "default_off": None,
        "enabled": None,
        "configured": None,
    }
    try:
        from hermes_cli.tools_config import (
            _DEFAULT_OFF_TOOLSETS,
            _get_platform_tools,
            _toolset_has_keys,
        )
        from hermes_cli.config import load_config

        config = load_config()
        enabled_toolsets = _get_platform_tools(
            config, "cli", include_default_mcp_servers=False,
        )
        state["default_off"] = "moa" in _DEFAULT_OFF_TOOLSETS
        state["enabled"] = "moa" in enabled_toolsets
        state["configured"] = bool(_toolset_has_keys("moa", config))
    except Exception:
        _log.warning("Could not resolve moa toolset state", exc_info=True)
    return state


# ---------------------------------------------------------------------------
# GET /api/moa/status
# ---------------------------------------------------------------------------

@router.get("/status")
async def moa_status():
    """Requirements + configuration snapshot for the MoA tab.

    Read-only and cheap; the frontend polls this to render the requirements
    banner and pre-fill the council builder defaults.
    """
    moa = _moa()

    # Make sure ~/.hermes/.env has been folded into os.environ before
    # probing for the key (web_server does this at startup; do it again so
    # this route stays correct if the router is mounted elsewhere).
    try:
        from hermes_cli.config import load_env
        load_env()
    except Exception:
        pass

    key_present = bool(os.getenv("OPENROUTER_API_KEY"))
    requirements_met = False
    try:
        requirements_met = bool(moa.check_moa_requirements())
    except Exception:
        _log.warning("check_moa_requirements() raised", exc_info=True)

    cfg = moa.get_moa_configuration()

    return {
        "requirements_met": requirements_met,
        "requirements": [
            {
                "env_var": "OPENROUTER_API_KEY",
                "present": key_present,
                "url": "https://openrouter.ai/keys",
            },
        ],
        "toolset": _toolset_state(),
        "configuration": cfg,
        "defaults": {
            "strategy": "parallel",
            "strategies": ["parallel", "single"],
            "rounds": 1,
            "reference_models": cfg["reference_models"],
            "aggregator_model": cfg["aggregator_model"],
            "max_rounds": cfg["max_rounds"],
        },
    }


# ---------------------------------------------------------------------------
# POST /api/moa/run
# ---------------------------------------------------------------------------

class MoaRunRequest(BaseModel):
    """Council run parameters — field names mirror the tool's kwargs."""

    prompt: str = Field(..., min_length=1)
    models: Optional[List[str]] = None      # reference model slugs
    rounds: int = 1
    strategy: str = "parallel"              # "parallel" | "single"
    aggregator: Optional[str] = None        # aggregator model slug


@router.post("/run")
async def moa_run(body: MoaRunRequest):
    """Run a Mixture-of-Agents council and return structured lanes.

    Returns per-reference responses (per round), the fused output, and the
    failed-models list. Orchestration reuses the tool module's own reference
    fan-out / aggregator helpers so retry, backoff, concurrency caps, and
    temperature quirks stay identical to CLI behaviour — while still giving
    the UI per-model content that ``mixture_of_agents_tool``'s JSON string
    folds away.
    """
    moa = _moa()

    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    strategy = (body.strategy or "parallel").strip().lower()
    if strategy not in ("parallel", "single"):
        raise HTTPException(
            status_code=400, detail="strategy must be 'parallel' or 'single'",
        )

    max_rounds = int(getattr(moa, "MAX_ROUNDS", 5))
    rounds = max(1, min(int(body.rounds or 1), max_rounds))

    ref_models = [m.strip() for m in (body.models or []) if m and m.strip()]
    if not ref_models:
        ref_models = list(moa.REFERENCE_MODELS)
    if not ref_models:
        raise HTTPException(
            status_code=400,
            detail="no reference models selected and no defaults available",
        )
    agg_model = (body.aggregator or "").strip() or moa.AGGREGATOR_MODEL

    if not os.getenv("OPENROUTER_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail=(
                "OPENROUTER_API_KEY is not set — add it on the Keys page "
                "or in ~/.hermes/.env"
            ),
        )

    start = datetime.datetime.now()
    sem = asyncio.Semaphore(int(getattr(moa, "MAX_CONCURRENT_REQUESTS", 8)))

    async def _bounded_ref(model: str, prior: Optional[str], label: str):
        async with sem:
            return await moa._run_reference_model_safe(
                model,
                prompt,
                moa.REFERENCE_TEMPERATURE,
                max_tokens=32000,
                max_retries=4,
                prior_fusion=prior,
                model_label=label,
            )

    rounds_out: List[Dict[str, Any]] = []
    failed_models: List[str] = []
    prior_fusion: Optional[str] = None
    final_response: Optional[str] = None

    try:
        for round_idx in range(rounds):
            round_num = round_idx + 1
            results = await asyncio.gather(
                *(
                    _bounded_ref(m, prior_fusion, f"R{round_num}:{m}")
                    for m in ref_models
                )
            )

            responses = [
                {"model": m, "content": c, "ok": ok} for (m, c, ok) in results
            ]
            successes = [(m, c) for (m, c, ok) in results if ok]
            failures = [m for (m, _c, ok) in results if not ok]
            failed_models.extend(failures)

            if len(successes) < int(getattr(moa, "MIN_SUCCESSFUL_REFERENCES", 1)):
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"All reference models failed in round {round_num} "
                        f"(need ≥{getattr(moa, 'MIN_SUCCESSFUL_REFERENCES', 1)} "
                        f"successful). Failed: {failures}"
                    ),
                )

            fused: Optional[str] = None
            if strategy == "single":
                # Raw poll — concatenate like the tool does, stop after R1.
                final_response = "\n\n---\n\n".join(
                    f"### {m}\n{c}" for m, c in successes
                )
                rounds_out.append({
                    "round": round_num,
                    "responses": responses,
                    "fused": None,
                })
                break

            messages = moa._build_aggregator_messages(
                prompt, successes, prior_fusion=prior_fusion,
            )
            fused = await moa._run_aggregator_model(
                messages, agg_model, moa.AGGREGATOR_TEMPERATURE,
            )
            prior_fusion = fused
            if round_idx == rounds - 1:
                final_response = fused

            rounds_out.append({
                "round": round_num,
                "responses": responses,
                "fused": fused,
            })

        if final_response is None:
            final_response = prior_fusion or ""

        elapsed = (datetime.datetime.now() - start).total_seconds()
        return {
            "success": True,
            "prompt": prompt,
            "strategy": strategy,
            "aggregator_model": agg_model if strategy == "parallel" else None,
            "rounds": rounds_out,
            "fused_output": final_response,
            "failed_models": sorted(set(failed_models)),
            "elapsed_seconds": round(elapsed, 2),
        }
    except HTTPException:
        raise
    except Exception as exc:
        _log.exception("POST /api/moa/run failed")
        raise HTTPException(status_code=500, detail=f"MoA run failed: {exc}")
