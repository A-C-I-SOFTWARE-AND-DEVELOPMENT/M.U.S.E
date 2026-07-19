"""Feature-status probes for the M.U.S.E. TUI gateway (Wave 1, PY-Gateway).

Import-guarded readers for the fusion / MOA / cron / memory subsystems that
back the new JSON-RPC methods in ``server.py`` (``fusion.status``,
``fusion.set``, ``cron.list``, ``memory.status``) plus the ``fusion.progress``
event hook.

Design contract (design.md Part 1.4): every probe must degrade gracefully.
No public function in this module ever raises — when the underlying agent
module is absent or errors, the payload carries ``"available": false`` with
safe default fields so TUI consumers can render a "feature absent" hint.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

# ── Event emission ────────────────────────────────────────────────────
# server.py injects its `_emit(event, sid, payload)` here so this module
# never imports the server (avoids a circular import).
_EVENT_EMITTER: Optional[Callable[[str, str, dict], None]] = None


def set_event_emitter(fn: Optional[Callable[[str, str, dict], None]]) -> None:
    """Register the gateway's event emitter (server.py `_emit`)."""
    global _EVENT_EMITTER
    _EVENT_EMITTER = fn


def _emit_event(event: str, payload: dict) -> None:
    try:
        if _EVENT_EMITTER is not None:
            _EVENT_EMITTER(event, "", payload)
    except Exception:
        pass


# ── Live fusion activity tracker ──────────────────────────────────────
# Updated by the progress hook below; read by fusion_status() so the TUI
# can show the round currently being fused (0/idle when no turn is fusing).
_activity_lock = threading.Lock()
_FUSION_ACTIVITY: dict[str, Any] = {
    "current_round": 0,
    "rounds": 0,
    "role": "idle",
    "model": "",
    "depth": "",
    "started_at": None,
}


def _set_activity(round_: int, role: str, model: str, rounds: int) -> None:
    with _activity_lock:
        _FUSION_ACTIVITY.update(
            {
                "current_round": round_,
                "rounds": rounds,
                "role": role,
                "model": model,
                "started_at": time.time() if role != "idle" else None,
            }
        )


def _get_activity() -> dict:
    with _activity_lock:
        return dict(_FUSION_ACTIVITY)


# ── fusion.progress hook ──────────────────────────────────────────────
# The actual per-round loop lives inside tools/mixture_of_agents_tool.py
# (`for round_idx in range(rounds)` — one monolithic async function, no
# callback), which is OUTSIDE tui_gateway ownership, so true per-round
# events are not cheaply hookable.  What IS cheap and additive: a guarded
# wrapper around agent.fusion_router.fuse_response_sync (the exact entry
# point agent/conversation_loop.py imports per-turn) that emits
# fusion.progress on round-loop START ({round: 0, role: "aggregate"}) and
# COMPLETION ({round: rounds, role: "done"}).  The wrapper calls through
# to the original unmodified function and never raises.
_progress_hook_lock = threading.Lock()
_progress_hook_installed = False


def install_fusion_progress_hook() -> bool:
    """Wrap agent.fusion_router.fuse_response_sync to emit fusion.progress.

    Idempotent; returns True when the hook is active.  Any failure (module
    absent, signature drift) leaves the router untouched and returns False.
    """
    global _progress_hook_installed
    with _progress_hook_lock:
        if _progress_hook_installed:
            return True
        try:
            from agent import fusion_router

            original = fusion_router.fuse_response_sync
            if getattr(original, "_muse_tui_progress_wrapped", False):
                _progress_hook_installed = True
                return True

            def wrapped(
                user_prompt,
                original_response=None,
                config=None,
                tool_iterations=0,
            ):
                rounds, agg = 1, ""
                try:
                    cfg = config or fusion_router.get_fusion_config()
                    rounds = int(cfg.get("rounds", 1) or 1)
                    agg = str(cfg.get("aggregator_model", "") or "")
                except Exception:
                    pass
                _set_activity(0, "aggregate", agg, rounds)
                _emit_event(
                    "fusion.progress",
                    {"round": 0, "rounds": rounds, "role": "aggregate", "model": agg},
                )
                try:
                    return original(
                        user_prompt,
                        original_response,
                        config,
                        tool_iterations=tool_iterations,
                    )
                finally:
                    _set_activity(0, "idle", "", 0)
                    _emit_event(
                        "fusion.progress",
                        {
                            "round": rounds,
                            "rounds": rounds,
                            "role": "done",
                            "model": agg,
                        },
                    )

            wrapped._muse_tui_progress_wrapped = True  # type: ignore[attr-defined]
            fusion_router.fuse_response_sync = wrapped
            _progress_hook_installed = True
            return True
        except Exception:
            return False


# ── fusion.status / fusion.set helpers ────────────────────────────────
def _moa_key_present() -> bool:
    try:
        return bool(os.environ.get("OPENROUTER_API_KEY"))
    except Exception:
        return False


def _model_router_rows(cfg: dict) -> list[dict]:
    """Per-model router rows: {model, specialty, ema_bias, calls}.

    MoEModelRouter is instantiated per fusion call (agent/fusion_router.py
    L191-198) — there is no persistent router instance, so EMA bias and
    call counts are per-turn ephemera and reported as 0.  Specialty is the
    argmax query-type from the static MODEL_SPECIALIZATIONS table.
    """
    specs: dict = {}
    try:
        from agent.fusion_model_router import MODEL_SPECIALIZATIONS

        specs = MODEL_SPECIALIZATIONS
    except Exception:
        specs = {}

    models: list[str] = []
    for m in list(cfg.get("reference_models") or []) + [cfg.get("aggregator_model")]:
        if m and isinstance(m, str) and m not in models:
            models.append(m)

    rows = []
    for model in models:
        specialty = ""
        try:
            table = specs.get(model) or {}
            if table:
                best = max(table.items(), key=lambda kv: kv[1])
                specialty = getattr(best[0], "value", str(best[0]))
        except Exception:
            specialty = ""
        rows.append(
            {"model": model, "specialty": specialty, "ema_bias": 0.0, "calls": 0}
        )
    return rows


def _lti_alpha() -> Optional[float]:
    try:
        from agent.fusion_lti import compute_alpha

        return round(float(compute_alpha()), 4)
    except Exception:
        return None


def fusion_status(cfg_file: Optional[dict] = None) -> dict:
    """Build the fusion.status payload.  Never raises.

    ``cfg_file`` is the gateway's parsed config.yaml dict (server.py
    ``_load_cfg()``); used only for the MOA toolset check so this module
    stays free of server imports.
    """
    payload: dict[str, Any] = {
        "available": False,
        "enabled": False,
        "depth": "standard",
        "rounds_planned": 1,
        "current_round": 0,
        "role": "idle",
        "lti_alpha": None,
        "moa": {"enabled": False, "key_present": _moa_key_present()},
        "model_router": [],
    }

    try:
        from agent import fusion_router

        status = fusion_router.get_fusion_status()
        cfg = fusion_router.get_fusion_config()
        try:
            # Honors the per-thread override AND config mode.
            enabled = bool(fusion_router.should_use_fusion())
        except Exception:
            enabled = bool(status.get("active"))

        depth = str(cfg.get("depth", "")).strip().lower()
        if not depth:
            # No static depth key exists in FUSION_CONFIG; with
            # difficulty_aware routing the depth is chosen per turn
            # (ACT analog), so report "adaptive".
            depth = "adaptive" if cfg.get("difficulty_aware", True) else "standard"

        activity = _get_activity()
        payload.update(
            {
                "available": True,
                "enabled": enabled,
                "depth": depth,
                "rounds_planned": int(cfg.get("rounds", 1) or 1),
                "current_round": int(activity.get("current_round") or 0),
                "role": str(activity.get("role") or "idle"),
                "lti_alpha": _lti_alpha(),
                "model_router": _model_router_rows(cfg),
            }
        )
    except Exception as e:
        payload["error"] = f"{type(e).__name__}: {e}"

    # MOA toolset state is config-driven and readable even when agent
    # modules are absent, so probe it independently of the block above.
    try:
        pt = (cfg_file or {}).get("platform_toolsets") or {}
        cli = pt.get("cli") or []
        key_present = payload["moa"]["key_present"]
        payload["moa"] = {
            "enabled": bool(key_present and "moa" in cli),
            "key_present": key_present,
        }
    except Exception:
        pass

    return payload


def apply_fusion_override(enabled: Optional[bool]) -> bool:
    """Best-effort set_fusion_override() call.  Returns True if applied.

    NOTE: the override is thread-local in agent/fusion_router.py, so it
    only affects fusion checks running on THIS thread.  The durable,
    cross-thread path is the config.yaml write (fusion.mode) performed by
    the fusion.set RPC handler in server.py; this call is kept for parity
    with the design contract.
    """
    try:
        from agent.fusion_router import set_fusion_override

        set_fusion_override(enabled)
        return True
    except Exception:
        return False


# ── cron.list ─────────────────────────────────────────────────────────
def cron_list() -> dict:
    """Read the cron job store.  Never raises.

    Primary path: cron.jobs.load_jobs() (the scheduler's own store API).
    Fallback: direct read of ~/.hermes/cron/jobs.json so the listing still
    works when the cron package cannot be imported but the file exists.
    """
    jobs: Any = None
    try:
        from cron.jobs import load_jobs

        jobs = load_jobs()
    except Exception as import_err:
        try:
            from hermes_constants import get_hermes_home

            store = Path(get_hermes_home()) / "cron" / "jobs.json"
            if not store.exists():
                return {
                    "available": False,
                    "jobs": [],
                    "error": f"cron store unavailable: {import_err}",
                }
            jobs = json.loads(store.read_text(encoding="utf-8"))
        except Exception as e:
            return {
                "available": False,
                "jobs": [],
                "error": f"{type(e).__name__}: {e}",
            }

    out: list[dict] = []
    try:
        for job in jobs or []:
            if not isinstance(job, dict):
                continue
            sched = job.get("schedule_display") or job.get("schedule") or ""
            if isinstance(sched, dict):
                sched = sched.get("expr") or sched.get("raw") or json.dumps(sched)
            out.append(
                {
                    "id": str(job.get("id") or ""),
                    "name": str(job.get("name") or ""),
                    "schedule": str(sched),
                    "enabled": bool(job.get("enabled", True))
                    and job.get("state") != "paused",
                    "next_run": job.get("next_run_at"),
                    "last_run": job.get("last_run_at"),
                    "last_status": job.get("last_status"),
                }
            )
    except Exception as e:
        return {"available": False, "jobs": [], "error": f"{type(e).__name__}: {e}"}
    return {"available": True, "jobs": out}


# ── memory.status ─────────────────────────────────────────────────────
def memory_status() -> dict:
    """Best-effort memory-layer probe.  Never raises; {layers: []} is valid.

    agent/memory_layers/ exposes no aggregate stats API, so this scans the
    raw event log directory (one JSONL file per layer/scope) for entry
    counts and last-write times.
    """
    layers: list[dict] = []
    available = False
    try:
        from agent.memory_layers import raw_event_log

        base = raw_event_log._base_dir()  # Path(hermes_home)/"memory-raw"
        available = True
        if base.exists():
            for f in sorted(base.iterdir()):
                try:
                    if not f.is_file():
                        continue
                    entries = 0
                    with open(f, "r", encoding="utf-8", errors="replace") as fh:
                        for line in fh:
                            if line.strip():
                                entries += 1
                    layers.append(
                        {
                            "name": f.stem,
                            "entries": entries,
                            "last_write": time.strftime(
                                "%Y-%m-%dT%H:%M:%S", time.localtime(f.stat().st_mtime)
                            ),
                        }
                    )
                except Exception:
                    continue
    except Exception:
        pass
    return {"available": available, "layers": layers}
