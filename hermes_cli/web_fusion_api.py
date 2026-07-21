"""
Fusion API — exposes agent.fusion_router to the dashboard over HTTP.

Routes (all under /api/fusion/):
    GET  /api/fusion/status   — current fusion mode + mechanism flags
    GET  /api/fusion/config   — effective fusion configuration (config.yaml ⊕ defaults)
    POST /api/fusion/override — force fusion on/off, or clear the override {enabled: bool|null}
    POST /api/fusion/run      — run a prompt through the fusion council, synchronously

Auth: the web server's ``auth_middleware`` already gates every /api/ path
that is not in ``_PUBLIC_API_PATHS`` with the ephemeral session token
(X-Hermes-Session-Token). These routes are intentionally NOT public, so no
per-route dependency is needed — same convention as /api/model/set et al.

Wiring (done by the integrator, not this file):

    from hermes_cli import web_fusion_api
    app.include_router(web_fusion_api.router)

NOTE: ``POST /run`` is a sync ``def`` route. FastAPI executes it in a
threadpool where no event loop is running, so ``fuse_response_sync`` takes
its plain ``asyncio.run`` path — no artificial 120s cap — which suits
multi-round council runs that can take several minutes.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class FusionOverrideBody(BaseModel):
    # True = force fusion on, False = force off, null = clear override
    # (fall back to config.yaml `fusion.mode`).
    enabled: Optional[bool] = None


class FusionRunBody(BaseModel):
    prompt: str


def _fusion():
    """Import agent.fusion_router lazily so the web server still starts
    even if the fusion stack has an import-time problem."""
    try:
        from agent import fusion_router
    except Exception as exc:  # pragma: no cover — environment dependent
        logger.error("Fusion router unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Fusion pipeline unavailable: {exc}",
        )
    return fusion_router


def _round_schedule(total_rounds: int) -> List[str]:
    """Per-round specialization schedule (Mythos LoRA-adapter analog).

    Mirrors the role selection in agent.fusion_round_specialization:
    DIVERSE → SYNTHESIZE → VERIFY → POLISH.
    """
    if total_rounds <= 1:
        return ["DIVERSE"]
    schedule: List[str] = []
    for idx in range(total_rounds):
        if idx == 0:
            schedule.append("DIVERSE")
        elif idx == 1:
            schedule.append("SYNTHESIZE")
        elif idx == total_rounds - 1 and total_rounds >= 4:
            schedule.append("POLISH")
        else:
            schedule.append("VERIFY")
    return schedule


@router.get("/api/fusion/status")
def get_fusion_status() -> Dict[str, Any]:
    """Current fusion mode, active flag, council membership, and the
    on/off state of each Mythos-inspired mechanism."""
    fusion = _fusion()
    try:
        status = fusion.get_fusion_status()
        status["override"] = fusion.get_fusion_override()
        status["effective_active"] = fusion.should_use_fusion()
        return status
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to read fusion status: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to read fusion status")


@router.get("/api/fusion/config")
def get_fusion_config() -> Dict[str, Any]:
    """Effective fusion configuration — config.yaml `fusion:` section
    merged over the built-in defaults."""
    fusion = _fusion()
    try:
        cfg = fusion.get_fusion_config()
        # Strip private run-time annotations (set during a fusion run).
        return {k: v for k, v in cfg.items() if not k.startswith("_")}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to read fusion config: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to read fusion config")


@router.post("/api/fusion/override")
def set_fusion_override(body: FusionOverrideBody) -> Dict[str, Any]:
    """Force fusion on/off for this process, or clear the override with
    ``{"enabled": null}`` so config.yaml decides again."""
    fusion = _fusion()
    try:
        fusion.set_fusion_override(body.enabled)
        return {
            "ok": True,
            "override": fusion.get_fusion_override(),
            "effective_active": fusion.should_use_fusion(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to set fusion override: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to set fusion override")


@router.post("/api/fusion/run")
def run_fusion(body: FusionRunBody) -> Dict[str, Any]:
    """Run a prompt through the fusion council and return the fused output
    plus council detail (selected models, MoE routing scores, round
    schedule).

    A mutable config dict is passed into the fusion pipeline so MoE model
    routing annotations (``_moe_query_type`` / ``_moe_scores``) and any
    depth-adjusted model/round choices made inside the pipeline are
    captured here for display.

    NOTE: with no ``original_response`` seed, ACT difficulty routing does
    not halt early — from-scratch prompts always get the full configured
    council. Long-running: multi-round runs can take minutes; this route
    deliberately imposes no extra timeout beyond the MoA tool's own.
    """
    prompt = (body.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    fusion = _fusion()
    try:
        cfg = fusion.get_fusion_config()
        started = time.monotonic()
        fused = fusion.fuse_response_sync(user_prompt=prompt, config=cfg)
        elapsed = time.monotonic() - started

        moe_query_type = cfg.get("_moe_query_type")
        moe_scores = cfg.get("_moe_scores")
        rounds = int(cfg.get("rounds", 1))

        return {
            "ok": True,
            "prompt": prompt,
            "fused_response": fused,
            "elapsed_seconds": round(elapsed, 2),
            "council": {
                "models": cfg.get("reference_models", []),
                "aggregator": cfg.get("aggregator_model", ""),
                "rounds": rounds,
                "strategy": cfg.get("strategy", "parallel"),
                "moe_query_type": moe_query_type,
                "moe_scores": moe_scores,
            },
            "round_schedule": _round_schedule(rounds),
            "mechanisms": {
                "difficulty_aware": bool(cfg.get("difficulty_aware", True)),
                "moe_routing": bool(cfg.get("moe_routing", True)),
                "lti_stable": bool(cfg.get("lti_stable", True)),
                "round_specialization": bool(
                    cfg.get("round_specialization", True)
                ),
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Fusion run failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Fusion run failed")
