"""Teacher interface — capability-aware provider selection over M.U.S.E.'s
actual provider registry (directive §14).

No provider is hard-coded. Available teachers are discovered from
`config/model-catalog.yaml` + env presence, then ranked by a policy vector.
Teacher identity is recorded per generated example (§16) but never leaks
secrets: only provider id + model id are stored, never keys.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class TeacherCandidate:
    provider_id: str
    model_id: str
    model_slug: str
    context: int
    params_b: Optional[float]
    tags: list[str]
    requires_env: Optional[str]
    available: bool
    estimated_cost_rank: int  # 0 = local/free, 1 = cheap API, 2 = premium API
    reason: str = ""


def discover_teachers(catalog_path: Path) -> list[TeacherCandidate]:
    with open(catalog_path, encoding="utf-8") as f:
        catalog = yaml.safe_load(f)

    out: list[TeacherCandidate] = []
    for provider_id, pdata in (catalog.get("providers") or {}).items():
        requires_env = pdata.get("requires_env")
        available = (requires_env is None) or bool(os.environ.get(requires_env))
        for m in pdata.get("models", []):
            tags = list(m.get("tags") or [])
            cost_rank = 0 if provider_id in ("ollama-local", "llamacpp-local") else (
                1 if "fast" in tags else 2
            )
            out.append(TeacherCandidate(
                provider_id=provider_id,
                model_id=str(m.get("id")),
                model_slug=str(m.get("model")),
                context=int(m.get("context") or 0),
                params_b=m.get("params_b"),
                tags=tags,
                requires_env=requires_env,
                available=available,
                estimated_cost_rank=cost_rank,
            ))
    return out


def rank_teachers(
    candidates: list[TeacherCandidate],
    *,
    require_tools: bool = True,
    min_context: int = 8192,
    prefer_local: bool = True,
) -> list[TeacherCandidate]:
    """Rank available teachers for dataset generation.

    Policy: tool-capable + sufficient context first; local preferred when
    `prefer_local` (privacy + zero marginal cost); cheaper rank breaks ties.
    """
    def key(c: TeacherCandidate):
        return (
            not c.available,
            require_tools and "tools" not in c.tags,
            c.context < min_context,
            0 if (prefer_local and c.estimated_cost_rank == 0) else c.estimated_cost_rank,
            -(c.params_b or 0),
        )
    return sorted(candidates, key=key)


def teacher_plan(candidates: list[TeacherCandidate], shares: dict[str, float]) -> dict[str, Any]:
    """Multi-teacher split (§15). `shares` maps a role label -> fraction; the
    best-ranked available candidate fills each role. Identity is recorded per
    role, never credentials."""
    ranked = rank_teachers(candidates)
    plan: dict[str, Any] = {}
    used: set[str] = set()
    for role, share in shares.items():
        pick = next((c for c in ranked if c.available and c.model_id not in used), None)
        if pick is None:
            plan[role] = {"share": share, "teacher": None, "status": "UNAVAILABLE"}
            continue
        used.add(pick.model_id)
        plan[role] = {
            "share": share,
            "teacher": f"{pick.provider_id}/{pick.model_id}",
            "status": "READY",
        }
    return plan
