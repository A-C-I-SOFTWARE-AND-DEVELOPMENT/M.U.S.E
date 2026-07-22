"""
M.U.S.E. dashboard — "Night Desk" ops-console aggregate API routes.

One aggregated, real-data API powering the Night Desk dashboard redesign:

    GET  /api/nightdesk/overview                 — KPIs, council, automations, ledger, backends, axion
    GET  /api/nightdesk/throughput?hours=24      — token-volume series (15-min buckets)
    GET  /api/nightdesk/pathways                 — per-model usage + capability/cost join
    GET  /api/nightdesk/gates                    — the real 8-gate pipeline + validation artifact
    GET  /api/nightdesk/gated-actions            — pending owner-gated approvals + autonomy record
    POST /api/nightdesk/gated-actions/{id}/decide — approve/reject a bound grant (phrase-gated)
    POST /api/nightdesk/emergency-stop           — owner panic button (mirrors the cockpit handler)
    GET  /api/nightdesk/orchestration            — jobs, subagent delegations, kanban counts
    GET  /api/nightdesk/status                   — module liveness + route index

HARD RULE — NO MOCK DATA. Every field comes from a real source (state.db,
grants.db, cron jobs.json, decision ledgers, config.yaml, models.dev cache,
council registry, gates module, kanban.db). Where a source is empty or
absent, the payload carries honest empties (``[]``, ``null``,
``{"available": false}``) — never fabricated values.

Wiring (done by the integrator, NOT in this file)::

    from hermes_cli import web_nightdesk_api
    app.include_router(web_nightdesk_api.router)   # before mount_spa(app)

Auth: this module deliberately does NOT import ``web_server`` at module
scope (that would be circular — web_server imports this router). Reuse of
web_server helpers (session-DB opener, cron listing, terminal-backend
catalog/probes, messaging-platform payloads) is done via lazy in-function
imports, which are safe because no route executes before web_server has
finished loading. Every route lives under ``/api/nightdesk/`` and none is
listed in ``dashboard_auth.public_paths.PUBLIC_API_PATHS``, so the global
session-token auth middleware in ``hermes_cli/web_server.py`` gates them —
same convention as ``web_fusion_api`` / ``web_moa_api``.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/nightdesk", tags=["nightdesk"])

# Messaging-platform runtime-state → Night Desk status mapping. Source of
# the raw states: gateway/run.py (connected/connecting/retrying/paused/
# fatal) plus web_server._messaging_platform_payload derivations
# (disabled/not_configured/pending_restart/startup_failed/gateway_stopped).
_MESSAGING_STATE_MAP = {
    "connected": "online",
    "connecting": "standby",
    "retrying": "standby",
    "paused": "standby",
    "pending_restart": "standby",
    "fatal": "degraded",
    "startup_failed": "degraded",
}

# Pathway status recency thresholds (seconds). There is NO per-model health
# probe anywhere in the stack — status is honestly derived from last_used.
_PATHWAY_ACTIVE_S = 24 * 3600
_PATHWAY_IDLE_S = 7 * 24 * 3600

_THROUGHPUT_BUCKET_S = 900  # 15 minutes


# ---------------------------------------------------------------------------
# Shared lazy accessors
# ---------------------------------------------------------------------------

def _ws():
    """Import web_server lazily (circular-import guard). Only called from
    inside route handlers, i.e. after web_server has fully loaded."""
    from hermes_cli import web_server

    return web_server


def _hermes_home() -> Path:
    from hermes_constants import get_hermes_home

    return Path(get_hermes_home())


def _session_db():
    """Open the process profile's state.db via web_server's own helper so
    profile resolution stays identical to the rest of the dashboard."""
    ws = _ws()
    return ws._open_session_db_for_profile(None)


def _today_cutoff() -> float:
    """Unix timestamp of local midnight today — the 'started_at > today' edge."""
    now = datetime.datetime.now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


# ---------------------------------------------------------------------------
# /overview section builders (all sync — run via asyncio.to_thread)
# ---------------------------------------------------------------------------

def _kpis() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    cutoff = _today_cutoff()

    # --- tokens / turns / cost today (query pattern mirrors
    #     web_server._get_usage_analytics, with a midnight-today edge) ---
    db = _session_db()
    try:
        row = db._conn.execute(
            """
            SELECT SUM(input_tokens + output_tokens + reasoning_tokens) AS tokens,
                   COUNT(*) AS sessions,
                   SUM(COALESCE(api_call_count, 0)) AS turns,
                   COALESCE(SUM(estimated_cost_usd), 0) AS cost_est,
                   COALESCE(SUM(actual_cost_usd), 0) AS cost_actual
            FROM sessions WHERE started_at > ?
            """,
            (cutoff,),
        ).fetchone()
        out["tokens_today"] = int(row["tokens"] or 0)
        out["turns_today"] = int(row["turns"] or 0)
        out["sessions_today"] = int(row["sessions"] or 0)
        # actual_cost_usd is usually 0.0 on this stack — the estimate is the
        # honest number, so it is the headline and is labelled as estimated.
        out["cost_today_usd"] = float(row["cost_est"] or 0.0)
        out["cost_estimated"] = True
        out["cost_actual_usd"] = float(row["cost_actual"] or 0.0)
    finally:
        db.close()

    # --- learning-graph density (agent.learning_graph) ---
    try:
        from agent import learning_graph

        graph = learning_graph.build_learning_graph()
        stats = graph.get("stats") or {}
        out["graph_nodes"] = len(graph.get("nodes") or [])
        out["graph_edges"] = len(graph.get("edges") or [])
        out["graph_density"] = stats  # density_stats() + memory counters
    except Exception as exc:
        _log.warning("learning graph unavailable: %s", exc)
        out["graph_nodes"] = None
        out["graph_edges"] = None
        out["graph_density"] = None

    # --- active model/provider + fallback chain (config.yaml) ---
    try:
        from hermes_cli.config import load_config
        from hermes_cli.fallback_config import get_fallback_chain

        cfg = load_config()
        model_cfg = cfg.get("model", "")
        if isinstance(model_cfg, dict):
            out["active_model"] = model_cfg.get("default") or model_cfg.get("name") or ""
            out["active_provider"] = model_cfg.get("provider") or ""
        else:
            out["active_model"] = str(model_cfg) if model_cfg else ""
            out["active_provider"] = ""
        # Whitelist non-sensitive keys — raw entries can carry api_key.
        out["fallback_chain"] = [
            {
                "provider": e.get("provider") or "",
                "model": e.get("model") or "",
                "base_url": e.get("base_url") or "",
            }
            for e in get_fallback_chain(cfg)
        ]
    except Exception as exc:
        _log.warning("model config unavailable: %s", exc)
        out["active_model"] = None
        out["active_provider"] = None
        out["fallback_chain"] = []

    # --- autonomy state (hermes_cli.approval_policy) ---
    try:
        from hermes_cli import approval_policy

        record = approval_policy.load_record()
        out["autonomy"] = {
            "level": record.level.value,
            "emergency_stopped": bool(record.emergency_stopped),
            "set_by": record.set_by,
            "updated_at": record.updated_at or None,
        }
    except Exception as exc:
        _log.warning("autonomy record unavailable: %s", exc)
        out["autonomy"] = None

    out["as_of"] = time.time()
    return out


def _council() -> Dict[str, Any]:
    """AOS enterprise council roster from the operating registry."""
    try:
        from hermes_cli.jarvis_prime.aos_council import dispatcher

        roster = dispatcher.roster(dispatcher.load_registry())
        members: List[Dict[str, Any]] = []
        for m in roster.get("active_council", []):
            members.append(
                {
                    "id": m.id,
                    "role": m.role or m.domain or "",
                    "owner_gated": bool(m.owner_gated),
                    "kind": m.kind,
                }
            )
        for m in roster.get("domain_specialists", []):
            members.append(
                {
                    "id": m.id,
                    "role": m.role or m.domain or "",
                    "owner_gated": bool(m.owner_gated),
                    "kind": m.kind,
                }
            )
        return {"total": len(members), "members": members}
    except Exception as exc:
        _log.warning("council registry unavailable: %s", exc)
        return {"total": 0, "members": [], "available": False}


def _automations() -> List[Dict[str, Any]]:
    """Cron jobs across all profiles (web_server._list_cron_jobs_sync)."""
    try:
        ws = _ws()
        jobs = ws._list_cron_jobs_sync("all")
    except Exception as exc:
        _log.warning("cron listing unavailable: %s", exc)
        return []
    out: List[Dict[str, Any]] = []
    for job in jobs or []:
        out.append(
            {
                "id": job.get("id"),
                "name": job.get("name"),
                "schedule_display": job.get("schedule_display"),
                "deliver": job.get("deliver"),
                "enabled": bool(job.get("enabled", True)),
                "state": job.get("state"),
                "last_run_at": job.get("last_run_at"),
                "last_status": job.get("last_status"),
                "next_run_at": job.get("next_run_at"),
                "profile": job.get("profile"),
            }
        )
    return out


def _ledger(limit: int = 10) -> List[Dict[str, Any]]:
    """Newest decision-ledger entries across sessions."""
    try:
        from hermes_cli import decision_ledger as dl

        root = dl._hermes_home() / getattr(dl, "_DECISIONS_DIR_NAME", "decisions")
        if not root.is_dir():
            return []
        paths = dl.list_ledgers()
    except Exception as exc:
        _log.warning("decision ledger unavailable: %s", exc)
        return []

    entries: List[Dict[str, Any]] = []
    for path in paths:
        session = path.parent.name
        stem = path.stem  # e.g. "0004-run-swarm-job-…"
        m = re.match(r"^(\d{4})-(.*)$", stem)
        slug = m.group(2) if m else stem
        ts = 0.0
        try:
            rec = dl.read_ledger(path)
            ts = float(rec.created_at or 0.0)
        except Exception:
            pass
        if not ts:
            try:
                ts = path.stat().st_mtime
            except OSError:
                ts = 0.0
        entries.append(
            {
                "id": f"{session}:{stem}",
                "title": slug,
                "session": session,
                "ts": ts,
            }
        )
    entries.sort(key=lambda e: e["ts"], reverse=True)
    return entries[: max(1, int(limit))]


async def _backends() -> Dict[str, Any]:
    """Execution backends + messaging platforms + synthesized CLI/TUI row.

    The two source collections are produced by web_server's own route
    handlers (imported lazily, awaited in-loop) so catalog, probes and
    profile scoping stay identical to the existing dashboard pages.
    """
    out: Dict[str, Any] = {"execution": [], "messaging": [], "cli_tui": None}

    # --- terminal execution backends (web_server.get_terminal_backends) ---
    try:
        ws = _ws()
        payload = await ws.get_terminal_backends(None)
        out["execution"] = payload.get("backends", [])
        out["active_execution_backend"] = payload.get("active")
    except Exception as exc:
        _log.warning("terminal backends unavailable: %s", exc)
        out["execution"] = []
        out["active_execution_backend"] = None

    # --- messaging platforms (web_server.get_messaging_platforms) ---
    try:
        ws = _ws()
        payload = await ws.get_messaging_platforms(None)
        rows = []
        for p in payload.get("platforms", []):
            raw_state = p.get("state")
            rows.append(
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "enabled": bool(p.get("enabled")),
                    "configured": bool(p.get("configured")),
                    "raw_state": raw_state,
                    "status": _MESSAGING_STATE_MAP.get(raw_state or "", "offline"),
                    "error_code": p.get("error_code"),
                    "error_message": p.get("error_message"),
                }
            )
        out["messaging"] = rows
    except Exception as exc:
        _log.warning("messaging platforms unavailable: %s", exc)
        out["messaging"] = []

    # --- synthesized CLI/TUI row ---
    # The dashboard server is up by definition when this handler runs. The
    # tui_gateway WS (/api/ws) is served in-process by this same server, so
    # the honest reachability probe is that its handler module imports here.
    ws_served = False
    try:
        import tui_gateway.ws  # noqa: F401

        ws_served = True
    except Exception:
        ws_served = False
    out["cli_tui"] = {
        "id": "cli_tui",
        "name": "CLI / TUI",
        "status": "online" if ws_served else "degraded",
        "detail": (
            "dashboard server up; tui_gateway WS served in-process at /api/ws"
            if ws_served
            else "dashboard server up; tui_gateway WS module unavailable in-process"
        ),
        "dashboard_up": True,
        "tui_gateway_ws_served": ws_served,
    }
    return out


def _axion() -> Dict[str, Any]:
    """Static Axiom identity excerpt (agent/axiom_prompt.AXIOM_SYSTEM_PROMPT)."""
    try:
        from agent.axiom_prompt import AXIOM_SYSTEM_PROMPT

        return {
            "identity_excerpt": AXIOM_SYSTEM_PROMPT[:300],
            "wired": False,
        }
    except Exception as exc:
        _log.warning("axiom prompt unavailable: %s", exc)
        return {"identity_excerpt": None, "wired": False, "available": False}


# ---------------------------------------------------------------------------
# GET /api/nightdesk/overview
# ---------------------------------------------------------------------------

@router.get("/overview")
async def nightdesk_overview() -> Dict[str, Any]:
    """One aggregate payload for the Night Desk landing view."""
    kpis, council, automations, ledger, backends = await asyncio.gather(
        asyncio.to_thread(_kpis),
        asyncio.to_thread(_council),
        asyncio.to_thread(_automations),
        asyncio.to_thread(_ledger, 10),
        _backends(),
    )
    return {
        "kpis": kpis,
        "council": council,
        "automations": automations,
        "ledger": ledger,
        "backends": backends,
        "axion": _axion(),
        "generated_at": time.time(),
    }


# ---------------------------------------------------------------------------
# GET /api/nightdesk/throughput
# ---------------------------------------------------------------------------

def _throughput(hours: int) -> Dict[str, Any]:
    now = time.time()
    window_start = now - hours * 3600
    first_bucket = int(window_start // _THROUGHPUT_BUCKET_S) * _THROUGHPUT_BUCKET_S

    db = _session_db()
    try:
        rows = db._conn.execute(
            """
            SELECT CAST(timestamp / ? AS INTEGER) * ? AS bucket,
                   SUM(COALESCE(token_count, 0)) AS tokens
            FROM messages
            WHERE timestamp >= ?
            GROUP BY bucket
            ORDER BY bucket
            """,
            (_THROUGHPUT_BUCKET_S, _THROUGHPUT_BUCKET_S, window_start),
        ).fetchall()
    finally:
        db.close()

    by_bucket = {int(r["bucket"]): int(r["tokens"] or 0) for r in rows}
    series: List[Dict[str, Any]] = []
    t = first_bucket
    while t <= now:
        series.append({"t": t, "tokens": by_bucket.get(t, 0)})
        t += _THROUGHPUT_BUCKET_S

    return {
        "series": series,
        "unit": "message tokens per 15min",
        "bucket_seconds": _THROUGHPUT_BUCKET_S,
        "window_hours": hours,
        "note": (
            "Tokens are messages.token_count recorded per message at write "
            "time in state.db. Generation speed (tok/s) is NOT persisted "
            "anywhere in the stack and is intentionally not computed. "
            "token_count is NULL for many historical rows; a zero bucket "
            "means no tokens were recorded in that 15-minute window."
        ),
    }


@router.get("/throughput")
async def nightdesk_throughput(hours: int = 24) -> Dict[str, Any]:
    """Token-volume series bucketed per 15 minutes over the window."""
    try:
        hours = max(1, min(int(hours), 24 * 7))
    except (TypeError, ValueError):
        hours = 24
    return await asyncio.to_thread(_throughput, hours)


# ---------------------------------------------------------------------------
# GET /api/nightdesk/pathways
# ---------------------------------------------------------------------------

def _pathways() -> Dict[str, Any]:
    db = _session_db()
    try:
        rows = db._conn.execute(
            """
            SELECT model,
                   billing_provider,
                   COUNT(*) AS turns,
                   COALESCE(SUM(estimated_cost_usd), 0) AS est_cost,
                   MAX(started_at) AS last_used
            FROM sessions
            WHERE model IS NOT NULL AND model != ''
            GROUP BY model, billing_provider
            ORDER BY turns DESC
            """
        ).fetchall()
    finally:
        db.close()

    now = time.time()
    out_rows: List[Dict[str, Any]] = []
    for r in rows:
        model = r["model"]
        provider = r["billing_provider"] or ""

        # Capability/cost join against the models.dev cache. get_model_info
        # carries context window AND per-1M costs; get_model_capabilities
        # (same source) is the context-window fallback.
        ctx: Optional[int] = None
        cost_in: Optional[float] = None
        cost_out: Optional[float] = None
        try:
            from agent.models_dev import get_model_capabilities, get_model_info

            info = get_model_info(provider, model)
            if info is not None:
                ctx = int(info.context_window) if info.context_window else None
                cost_in = float(info.cost_input) if info.cost_input else None
                cost_out = float(info.cost_output) if info.cost_output else None
            if ctx is None:
                caps = get_model_capabilities(provider=provider, model=model)
                if caps is not None and caps.context_window:
                    ctx = int(caps.context_window)
        except Exception:
            pass

        last_used = float(r["last_used"] or 0.0) or None
        age = (now - last_used) if last_used else None
        if age is None:
            status = "dormant"
        elif age < _PATHWAY_ACTIVE_S:
            status = "active"
        elif age < _PATHWAY_IDLE_S:
            status = "idle"
        else:
            status = "dormant"

        out_rows.append(
            {
                "model": model,
                "provider": provider,
                "ctx": ctx,
                "cost_input_1m": cost_in,
                "cost_output_1m": cost_out,
                "turns": int(r["turns"] or 0),
                "est_cost": float(r["est_cost"] or 0.0),
                "last_used": last_used,
                "status": status,
            }
        )

    return {
        "pathways": out_rows,
        "status_basis": (
            "No per-model health probe exists in this stack. status is "
            "derived from sessions.started_at recency: last use <24h → "
            "'active', <7d → 'idle', otherwise 'dormant'."
        ),
        "cost_basis": (
            "ctx / cost_input_1m / cost_output_1m come from the models.dev "
            "cache (agent.models_dev) per 1M tokens; null when the model is "
            "not present in the cache. est_cost is SUM(estimated_cost_usd) "
            "over all-time sessions."
        ),
    }


@router.get("/pathways")
async def nightdesk_pathways() -> Dict[str, Any]:
    """Model pathways: per-(model, provider) usage joined with capabilities."""
    return await asyncio.to_thread(_pathways)


# ---------------------------------------------------------------------------
# GET /api/nightdesk/gates
# ---------------------------------------------------------------------------

def _gate_descriptions() -> Dict[str, str]:
    """One-line description per gate, parsed from the gates module docstring
    (the doc's numbered 'Name gate — description' lines)."""
    from hermes_cli.jarvis_prime import gates as gates_mod

    descriptions: Dict[str, str] = {}
    doc = gates_mod.__doc__ or ""
    for line in doc.splitlines():
        m = re.match(r"^\s*\d+\.\s+(.+?)\s+gate\s+—\s+(.+)$", line.strip())
        if not m:
            continue
        key = m.group(1).strip().lower().replace(" ", "_")
        descriptions[key] = m.group(2).strip().rstrip(".")
    return descriptions


def _gates() -> Dict[str, Any]:
    from hermes_cli.jarvis_prime import gates as gates_mod

    descriptions = _gate_descriptions()
    gate_rows = [
        {
            "name": gate.name,
            "description": descriptions.get(gate.name),
        }
        for gate in gates_mod.GATES
    ]

    # Validation artifact: <repo>/validation/results.json, written by
    # hermes_cli.validation.ValidationRunner. gates.py is at
    # hermes_cli/jarvis_prime/gates.py → parents[2] is the repo root.
    validation: Optional[Dict[str, Any]] = None
    repo_root = Path(gates_mod.__file__).resolve().parents[2]
    results_path = repo_root / "validation" / "results.json"
    if results_path.is_file():
        try:
            import json

            data = json.loads(results_path.read_text(encoding="utf-8"))
            checks = data.get("checks") or []
            status_counts: Dict[str, int] = {}
            for c in checks:
                s = str(c.get("status") or "unknown")
                status_counts[s] = status_counts.get(s, 0) + 1
            validation = {
                "publish_allowed": data.get("publish_allowed"),
                "status_counts": status_counts,
                "total_checks": len(checks),
            }
        except Exception as exc:
            _log.warning("validation results unreadable: %s", exc)
            validation = None

    return {
        "gates": gate_rows,
        "validation": validation,
        "note": (
            "Gate names are the real engine's (hermes_cli.jarvis_prime.gates."
            "GATES): planning, build, review, test, security, release, "
            "owner_approval, rollback. Mockup gate names were intentionally "
            "remapped to this real pipeline. Descriptions are parsed from "
            "the gates module docstring. validation is null when "
            "<repo>/validation/results.json does not exist."
        ),
    }


@router.get("/gates")
async def nightdesk_gates() -> Dict[str, Any]:
    """The real 8-gate verification pipeline + validation artifact."""
    return await asyncio.to_thread(_gates)


# ---------------------------------------------------------------------------
# GET /api/nightdesk/gated-actions
# ---------------------------------------------------------------------------

def _grants_db_path() -> Path:
    return _hermes_home() / "approvals" / "grants.db"


def _gated_actions() -> Dict[str, Any]:
    from hermes_cli import approval_grants
    from hermes_cli import approval_policy
    from hermes_cli.jarvis_prime.owner_auth import OWNER_GATED_ACTIONS

    pending: List[Dict[str, Any]] = []
    db_path = _grants_db_path()
    store_present = db_path.is_file()
    if store_present:
        for rec in approval_grants.list_bound_approvals(state="pending"):
            action = rec.action
            pending.append(
                {
                    "id": rec.approval_id,
                    "action": action,
                    "realm_id": rec.realm_id,
                    "state": rec.state.value,
                    "issued_at": rec.issued_at,
                    "expires_at": rec.expires_at,
                    "subject_hash": rec.subject_hash,
                    # No risk tier is persisted on bound approvals — honest null.
                    "risk_tier": None,
                    "category": action.replace("_", " ").title(),
                    "category_known": action in OWNER_GATED_ACTIONS,
                    "description": (
                        f"Owner-gated action '{action}' requested in realm "
                        f"'{rec.realm_id}'."
                    ),
                }
            )

    record = approval_policy.load_record()
    autonomy = {
        "level": record.level.value,
        "emergency_stopped": bool(record.emergency_stopped),
        "set_by": record.set_by,
        "updated_at": record.updated_at or None,
    }

    return {
        "pending": pending,
        "autonomy": autonomy,
        "store": str(db_path),
        "store_present": store_present,
        "note": (
            "Read directly from the approvals store (grants.db); the cockpit "
            "server is not required. risk_tier is null because bound "
            "approvals persist no risk classification."
        ),
    }


@router.get("/gated-actions")
async def nightdesk_gated_actions() -> Dict[str, Any]:
    """Pending owner-gated bound approvals + the current autonomy record."""
    return await asyncio.to_thread(_gated_actions)


# ---------------------------------------------------------------------------
# POST /api/nightdesk/gated-actions/{approval_id}/decide
# ---------------------------------------------------------------------------

class GatedActionDecision(BaseModel):
    decision: str = Field(...)  # "approve" | "reject"
    authorization: str = ""


@router.post("/gated-actions/{approval_id}/decide")
async def nightdesk_gated_action_decide(
    approval_id: str, body: GatedActionDecision
) -> Dict[str, Any]:
    """Approve or reject a pending bound approval.

    Requires the exact owner authorization phrase for BOTH decisions
    (stricter than the cockpit, which gates only approve). Supersession is
    enforced inside the store; any records this decision supersedes (or the
    record's own superseder) are surfaced in the response.
    """
    decision = (body.decision or "").lower().strip()
    if decision not in ("approve", "reject"):
        raise HTTPException(
            status_code=400, detail="decision must be 'approve' or 'reject'"
        )

    from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

    if (body.authorization or "").strip() != AUTHORIZATION_PHRASE:
        raise HTTPException(status_code=403, detail="owner authorization required")

    from hermes_cli import approval_grants as ag

    def _decide():
        return ag.decide_bound_approval(
            approval_id,
            approve=decision == "approve",
            decided_by="nightdesk-owner",
        )

    try:
        decided = await asyncio.to_thread(_decide)
    except ag.ApprovalNotFoundError:
        raise HTTPException(status_code=404, detail="approval not found")
    except ag.ApprovalExpiredError:
        raise HTTPException(status_code=410, detail="approval expired")
    except ag.ApprovalCorruptionError:
        raise HTTPException(status_code=500, detail="approval store unavailable")
    except ag.ApprovalStateError:
        raise HTTPException(status_code=409, detail="approval cannot be decided")
    except (ag.ApprovalGrantError, ValueError):
        raise HTTPException(status_code=409, detail="approval decision rejected")
    except Exception:
        _log.exception("gated-action decide failed")
        raise HTTPException(status_code=500, detail="approval store unavailable")

    # Surface supersession: records this grant supersedes, and this record's
    # own superseder (when it was itself superseded before the decision).
    superseded: List[str] = []
    try:
        all_records = await asyncio.to_thread(ag.list_bound_approvals)
        superseded = [
            r.approval_id for r in all_records if r.superseded_by == decided.approval_id
        ]
    except Exception:
        pass

    return {
        "id": decided.approval_id,
        "kind": "bound_grant",
        "action": decided.action,
        "realm_id": decided.realm_id,
        "state": decided.state.value,
        "decision": decision,
        "decided_at": decided.decided_at,
        "decided_by": decided.decided_by,
        "expires_at": decided.expires_at,
        "subject_hash": decided.subject_hash,
        "superseded_by": decided.superseded_by,
        "supersedes": superseded,
    }


# ---------------------------------------------------------------------------
# POST /api/nightdesk/emergency-stop
# ---------------------------------------------------------------------------

class EmergencyStopBody(BaseModel):
    reason: Optional[str] = None


@router.post("/emergency-stop")
async def nightdesk_emergency_stop(body: EmergencyStopBody) -> Dict[str, Any]:
    """Owner panic button — mirrors gateway/cockpit/handlers.py::emergency_stop.

    Three effects, same imports as the cockpit handler:
      1. JarvisPrime().stop(reason) — clears owner gates, disables the
         proactive tick, releases worker branch leases. This is a
         live-runtime object: when it cannot be constructed in-process the
         effect is recorded under skipped_effects, not faked.
      2. JobQueue.cancel_job on every non-terminal job.
      3. approval_policy.engage_emergency_stop(set_by="nightdesk").
    """
    reason = (body.reason or "").strip() or "owner_requested"

    def _stop() -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "engaged": True,
            "reason": reason,
            "cleared_actions": [],
            "branch_leases_cleared": 0,
            "tick_disabled": False,
            "cancelled_jobs": [],
            "cancelled_count": 0,
            "autonomy_level": None,
            "skipped_effects": [],
            "errors": [],
        }

        # 1) Runtime halt.
        try:
            from hermes_cli.jarvis_prime.runtime import JarvisPrime

            stop_result = JarvisPrime().stop(reason=reason)
            result["cleared_actions"] = stop_result.get("cleared_actions", [])
            result["branch_leases_cleared"] = stop_result.get(
                "branch_leases_cleared", 0
            )
            result["tick_disabled"] = bool(stop_result.get("tick_disabled", False))
            if stop_result.get("ledger_record_hash"):
                result["ledger_record_hash"] = stop_result["ledger_record_hash"]
            if stop_result.get("ledger_warning"):
                result["errors"].append(
                    f"runtime ledger: {stop_result['ledger_warning']}"
                )
        except Exception as exc:
            result["skipped_effects"].append("jarvis_prime_runtime_stop")
            result["errors"].append(f"runtime: {exc}")

        # 2) Cancel every non-terminal queue entry.
        cancelled: List[str] = []
        try:
            from hermes_cli.job_queue import JobQueue, QueueState

            queue = JobQueue()
            for entry in queue.list_jobs():
                if entry.state in QueueState.TERMINAL:
                    continue
                try:
                    queue.cancel_job(entry.job_id, note=f"emergency stop: {reason}")
                    cancelled.append(entry.job_id)
                except Exception as exc:
                    result["errors"].append(f"{entry.job_id}: {exc}")
        except Exception as exc:
            result["skipped_effects"].append("job_queue_cancel")
            result["errors"].append(f"queue: {exc}")
        result["cancelled_jobs"] = cancelled
        result["cancelled_count"] = len(cancelled)

        # 3) Latch autonomy to the safe floor.
        try:
            from hermes_cli import approval_policy as ap

            record = ap.engage_emergency_stop(set_by="nightdesk")
            result["autonomy_level"] = getattr(
                getattr(record, "level", None), "value", "read_only"
            )
        except Exception as exc:
            result["skipped_effects"].append("autonomy_emergency_stop")
            result["errors"].append(f"autonomy: {exc}")

        result["halted_at"] = (
            datetime.datetime.now(datetime.timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
        return result

    return await asyncio.to_thread(_stop)


# ---------------------------------------------------------------------------
# GET /api/nightdesk/orchestration
# ---------------------------------------------------------------------------

def _orchestration() -> Dict[str, Any]:
    # --- jobs: orchestrator jobs.json ⊕ job_queue entries ---
    jobs: List[Dict[str, Any]] = []
    try:
        from hermes_cli import orchestrator

        for job in orchestrator.list_jobs(limit=10000):
            # orchestrator._now() persists MICROseconds (see its docstring);
            # normalize to the seconds-based unix float every other Night
            # Desk timestamp uses.
            jobs.append(
                {
                    "id": job.id,
                    "title": (job.prompt or "")[:80],
                    "status": job.status,
                    "created_at": (job.created_at / 1_000_000) or None,
                    "updated_at": (job.updated_at / 1_000_000) or None,
                    "source": "orchestrator",
                }
            )
    except Exception as exc:
        _log.warning("orchestrator jobs unavailable: %s", exc)

    queue_root: Optional[str] = None
    try:
        from hermes_cli.job_queue import JobQueue

        queue = JobQueue()
        queue_root = str(queue.root)
        for entry in queue.list_jobs():
            jobs.append(
                {
                    "id": entry.job_id,
                    "title": (entry.prompt or "")[:80],
                    "status": entry.state,
                    "created_at": entry.created_at or None,
                    "updated_at": entry.updated_at or None,
                    "source": "job_queue",
                }
            )
    except Exception as exc:
        _log.warning("job queue unavailable: %s", exc)
    jobs.sort(key=lambda j: (j.get("created_at") or 0), reverse=True)

    # --- subagents: state.db async_delegations ---
    subagents: List[Dict[str, Any]] = []
    try:
        db = _session_db()
        try:
            rows = db._conn.execute(
                """
                SELECT delegation_id, origin_session, state,
                       dispatched_at, completed_at
                FROM async_delegations
                ORDER BY dispatched_at DESC
                LIMIT 100
                """
            ).fetchall()
            subagents = [dict(r) for r in rows]
        finally:
            db.close()
    except Exception as exc:
        _log.warning("async delegations unavailable: %s", exc)

    # --- kanban: task counts by status ---
    kanban: Dict[str, Any] = {"available": False}
    try:
        from hermes_cli import kanban_db

        path = kanban_db.kanban_db_path()
        if path.is_file():
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                counts = {
                    str(status): int(n)
                    for status, n in conn.execute(
                        "SELECT status, COUNT(*) FROM tasks GROUP BY status"
                    ).fetchall()
                }
            finally:
                conn.close()
            kanban = {
                "available": True,
                "path": str(path),
                "counts": counts,
                "total": sum(counts.values()),
            }
        else:
            kanban = {"available": False, "path": str(path)}
    except Exception as exc:
        _log.warning("kanban unavailable: %s", exc)
        kanban = {"available": False}

    return {
        "jobs": jobs,
        "subagents": subagents,
        "kanban": kanban,
        "note": (
            "jobs merges the hermes-home orchestrator/jobs.json (source "
            "'orchestrator'; its persisted microsecond timestamps are "
            "normalized to seconds here) with the cwd-anchored job_queue "
            f"(source 'job_queue', root {queue_root}). subagents come from "
            "state.db async_delegations. kanban counts are null-absent when "
            "kanban.db does not exist."
        ),
    }


@router.get("/orchestration")
async def nightdesk_orchestration() -> Dict[str, Any]:
    """Orchestrator jobs, subagent delegations, and kanban task counts."""
    return await asyncio.to_thread(_orchestration)


# ---------------------------------------------------------------------------
# GET /api/nightdesk/status
# ---------------------------------------------------------------------------

@router.get("/status")
async def nightdesk_status() -> Dict[str, Any]:
    """Liveness + route index for the Night Desk module (smoke-test target)."""
    return {
        "ok": True,
        "module": "hermes_cli.web_nightdesk_api",
        "routes": [
            "/api/nightdesk/overview",
            "/api/nightdesk/throughput",
            "/api/nightdesk/pathways",
            "/api/nightdesk/gates",
            "/api/nightdesk/gated-actions",
            "/api/nightdesk/gated-actions/{approval_id}/decide",
            "/api/nightdesk/emergency-stop",
            "/api/nightdesk/orchestration",
            "/api/nightdesk/status",
        ],
    }
