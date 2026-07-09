"""Cockpit route handlers — each backed by a real Hermes subsystem.

Handlers are pure functions of a :class:`Request` returning a
:class:`JsonResponse` (buffered JSON) or, for chat, a stream generator.
Every handler is defensive: a missing optional subsystem degrades to an
honest empty/typed response (never a crash, never fake data).

Stdlib-only at import time; subsystems are imported lazily inside each
handler so the module loads under Termux / slim installs.
"""

from __future__ import annotations

import platform
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Request / response model
# ---------------------------------------------------------------------------


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)
    path_params: dict[str, str] = field(default_factory=dict)


@dataclass
class JsonResponse:
    status: int
    payload: dict[str, Any]


# Whether the server is bound beyond loopback (``--allow-external``). Agentic
# *execute* dispatch (running Codex/Claude against the repo) is refused when
# this is True — a second guard on top of the owner-approval phrase, so a
# remotely-reachable cockpit can never trigger repo-editing execution.
_ALLOW_REMOTE_EXECUTE = False


def configure_runtime(*, allow_remote_execute: bool) -> None:
    """Set runtime guards from ``server.serve`` (called once at startup)."""
    global _ALLOW_REMOTE_EXECUTE
    _ALLOW_REMOTE_EXECUTE = bool(allow_remote_execute)


# Which chat engine POST /v1/agent/chat serves: "jarvis" (default; the route
# answers 409) or "full" (the complete AIAgent with tools + approvals).
# Surfaced in /v1/health as "agent" so clients pick their chat lane.
_AGENT_MODE = "jarvis"


def configure_agent_mode(mode: str) -> None:
    """Set the cockpit chat agent mode from ``server.serve`` (startup)."""
    global _AGENT_MODE
    _AGENT_MODE = mode if mode in ("jarvis", "full") else "jarvis"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Health + runtime
# ---------------------------------------------------------------------------

COCKPIT_API_VERSION = "1.0.0"


def health(_req: Request) -> JsonResponse:
    """Unauthenticated liveness + version probe (contract §2)."""
    version = _gateway_version()
    return JsonResponse(
        200,
        {
            "ok": True,
            "service": "hermes-cockpit",
            "api_version": COCKPIT_API_VERSION,
            "gateway_version": version,
            "agent": _AGENT_MODE,
            "time": _now_iso(),
        },
    )


# ---------------------------------------------------------------------------
# Full-agent chat companions (/v1/agent/*)
# ---------------------------------------------------------------------------


def agent_approval_decide(req: Request) -> JsonResponse:
    """Resolve a pending owner approval raised by a /v1/agent/chat run.

    Body: ``{"session_key": ..., "choice": "once"|"session"|"always"|"deny"}``
    (the ``approval`` chunk carries the session key back to the client).
    """
    if _AGENT_MODE != "full":
        return JsonResponse(409, {"error": "full agent mode is not enabled on this gateway"})
    session_key = str(req.body.get("session_key") or "").strip()
    choice = str(req.body.get("choice") or "").strip().lower()
    if not session_key or not choice:
        return JsonResponse(400, {"error": "session_key and choice are required"})
    from gateway.cockpit import agent_full

    try:
        resolved = agent_full.resolve_approval(session_key, choice)
    except ValueError as exc:
        return JsonResponse(400, {"error": str(exc)})
    if resolved == 0:
        return JsonResponse(404, {"error": "no pending approval for that session"})
    return JsonResponse(200, {"ok": True, "resolved": resolved, "choice": choice})


def agent_stop(req: Request) -> JsonResponse:
    """Interrupt the in-flight /v1/agent/chat run for a session.

    Body: ``{"session_key": ...}``. Graceful: the agent finishes its current
    step and the stream closes with an interrupted result.
    """
    if _AGENT_MODE != "full":
        return JsonResponse(409, {"error": "full agent mode is not enabled on this gateway"})
    session_key = str(req.body.get("session_key") or "").strip()
    if not session_key:
        return JsonResponse(400, {"error": "session_key is required"})
    from gateway.cockpit import agent_full

    if not agent_full.interrupt_run(session_key):
        return JsonResponse(404, {"error": "no active run for that session"})
    return JsonResponse(200, {"ok": True, "stopped": session_key})


def channels(_req: Request) -> JsonResponse:
    """Read-only messaging-channel status (Telegram/Discord/Slack/…).

    Derived from the live runtime status the gateway already publishes — so
    the cockpit's Channels view shows which surfaces are actually connected
    instead of a static sample list. No writes: toggling a channel on/off is
    a gateway config operation, not a cockpit action.
    """
    try:
        from gateway.status import read_runtime_status

        runtime = read_runtime_status() or {}
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"channels": [], "connected_count": 0, "error": str(exc)})

    platforms = runtime.get("platforms", {}) or {}
    items = []
    for name, info in sorted(platforms.items()):
        info = info if isinstance(info, dict) else {}
        state = str(info.get("state") or info.get("status") or "").lower()
        connected = bool(
            info.get("connected")
            or state in ("connected", "running", "online", "ready", "active")
        )
        items.append(
            {
                "id": name,
                "name": name.replace("_", " ").title(),
                "connected": connected,
                "state": state or ("connected" if connected else "idle"),
                "detail": info.get("detail") or info.get("note") or "",
            }
        )
    return JsonResponse(
        200,
        {"channels": items, "connected_count": sum(1 for c in items if c["connected"])},
    )


def schedules(_req: Request) -> JsonResponse:
    """Read-only list of scheduled (cron) jobs the gateway will run unattended.

    Wraps ``cron.jobs.list_jobs`` so the Schedules view shows real automations
    (their cadence + enabled state) instead of a static sample. Creating or
    pausing a schedule stays a gateway/CLI operation for now (kept out of the
    remotely-reachable cockpit surface).
    """
    try:
        from cron.jobs import list_jobs

        raw = list_jobs(include_disabled=True)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"schedules": [], "count": 0, "error": str(exc)})

    items = []
    for j in raw or []:
        j = j if isinstance(j, dict) else {}
        items.append(
            {
                "id": j.get("id") or j.get("name") or "",
                "name": j.get("name") or j.get("prompt") or j.get("id") or "(unnamed)",
                "when": j.get("schedule") or j.get("cron") or j.get("when") or "",
                "to": j.get("target") or j.get("platform") or j.get("to") or "",
                "enabled": bool(j.get("enabled", True)),
            }
        )
    return JsonResponse(
        200,
        {"schedules": items, "count": len(items), "enabled_count": sum(1 for s in items if s["enabled"])},
    )


def runtime_status(_req: Request) -> JsonResponse:
    """Real runtime status: gateway, host, and live queue snapshot."""
    return JsonResponse(
        200,
        {
            "gateway": {
                "version": _gateway_version(),
                "started_at": _process_start_iso(),
                "pid": _safe(lambda: __import__("os").getpid()),
                "mode": "local",
            },
            "host": {
                "platform": platform.system() or "unknown",
                "arch": platform.machine() or "unknown",
                "hostname": _safe(socket.gethostname) or "unknown",
            },
            "queue": _queue_snapshot(),
        },
    )


def axiom_panel(_req: Request) -> JsonResponse:
    """Axiom panel: chain audit, recent events, pending improvements.

    One read-only snapshot for the cockpit's chain-status chip
    (``audit.chain_valid`` ✔/✘/–), event tail, and the
    pending-improvement count from the flywheel.
    """
    audit: dict[str, Any] = {}
    status: dict[str, Any] = {}
    tail: list[dict[str, Any]] = []
    pending_count = 0
    try:
        from hermes_cli.jarvis_prime.axiom_bridge import get_bridge

        bridge = get_bridge()
        status = bridge.status()
        audit = bridge.audit()
        tail = bridge.tail(10)
    except Exception as exc:
        audit = {"chain_valid": None, "error": str(exc)}
    try:
        from hermes_cli.jarvis_prime import flywheel

        pending_count = len(flywheel.pending())
    except Exception:
        pending_count = 0
    return JsonResponse(
        200,
        {
            "status": status,
            "audit": audit,
            "tail": tail,
            "pending_improvements": pending_count,
            "time": _now_iso(),
        },
    )


def runtime_workers(_req: Request) -> JsonResponse:
    """Detected worker lanes (Claude Code / Codex) — detection only, no keys."""
    workers: list[dict[str, Any]] = []
    try:
        from hermes_cli.jarvis_prime import worker_registry as wr

        for status in wr.detect_lanes():
            workers.append({
                "id": status.lane.id,
                "display_name": status.lane.display_name,
                "kind": status.lane.role,
                "available": status.available,
                "version": status.version,
                "path": status.path,
                "notes": status.detail or None,
            })
    except Exception:  # pragma: no cover - defensive
        pass
    return JsonResponse(200, {"workers": workers})


# ---------------------------------------------------------------------------
# Diagnostics + models
# ---------------------------------------------------------------------------


def diagnostics(_req: Request) -> JsonResponse:
    """Launch-readiness diagnostics (reuses the JARVIS launch doctor)."""
    try:
        from hermes_cli.jarvis_prime.launch_doctor import run_launch_doctor

        report = run_launch_doctor()
        payload = report.to_dict()
    except Exception as exc:  # pragma: no cover - defensive
        payload = {"ok": False, "checks": [], "error": str(exc)}
    payload["generated_at"] = _now_iso()
    return JsonResponse(200, payload)


def trace_summary(req: Request) -> JsonResponse:
    """Read-only summary of recent per-request observability traces.

    Folds the ``request_trace`` / ``model_lifecycle`` records from the cockpit
    event log into latency percentiles, tool-failure / fallback rates, and
    endpoint / model distributions. Honest-empty when tracing is off or no
    traces exist (``observability.request_trace`` / ``HERMES_REQUEST_TRACE``).
    """
    try:
        from gateway.cockpit import event_log
        from hermes_cli.request_trace import summarize

        try:
            limit = max(1, min(5000, int(req.query.get("limit", "500"))))
        except (TypeError, ValueError):
            limit = 500
        records = event_log.read(source="hook", limit=limit)
        payload = summarize(records)
    except Exception as exc:  # pragma: no cover - defensive
        payload = {"request_count": 0, "error": str(exc)}
    payload["generated_at"] = _now_iso()
    return JsonResponse(200, payload)


def models(_req: Request) -> JsonResponse:
    """Read-only model policy (free-first routing). Never accepts API keys."""
    try:
        from hermes_cli.jarvis_prime import model_bootstrap as mb

        policy = mb.load_policy()
        if policy is None:
            result = mb.bootstrap(dry_run=True, record_memory=False)
            policy = result.config
            policy["_note"] = "policy not yet written; this is a dry-run preview"
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"routes": {}, "error": str(exc)})
    return JsonResponse(200, policy)


def model_routes(_req: Request) -> JsonResponse:
    """Evidence-backed per-task-class model routes (read-only).

    Each task class carries its chosen model, route tier, fallback chain, a
    human-readable ``why``, the scorecard evidence behind it, and the current
    owner overrides + paid state. Never accepts or returns API keys.
    """
    try:
        from hermes_cli.jarvis_prime import task_router as tr

        overrides = tr.load_overrides()
        decisions = tr.all_routes(overrides=overrides)
        payload = {
            "routes": [d.to_dict() for d in decisions],
            "task_classes": [t.value for t in tr.TaskClass],
            "paid_enabled": bool(decisions[0].paid_enabled) if decisions else False,
            "overrides": {
                "task_overrides": overrides.get("task_overrides", {}),
                "paid_enabled": overrides.get("paid_enabled"),
                "updated_at": overrides.get("updated_at"),
            },
            "generated_at": _now_iso(),
        }
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"routes": [], "error": str(exc)})
    return JsonResponse(200, payload)


def _is_credential_key(name: str) -> bool:
    """Credential-shaped env names only — never the cockpit's own token/state."""
    upper = name.upper()
    if upper in {"HERMES_COCKPIT_TOKEN", "COCKPIT_TOKEN", "HERMES_TOKEN", "HERMES_HOME", "HERMES_REPO_DIR"}:
        return False
    return any(
        upper.endswith(suffix)
        for suffix in ("_API_KEY", "_TOKEN", "_KEY", "_SECRET", "_URL", "_CMD", "_AUTH", "_PASSWORD", "_WEBHOOK")
    )


def secrets_import(_req: Request) -> JsonResponse:
    """Owner-gated, **opt-in** export of the user's existing credential keys from
    ``~/.hermes/.env`` so a paired client (NEXUS) can import them instead of
    re-typing every key.

    Guards (defence in depth):
      * **Disabled by default** — returns 403 unless ``HERMES_COCKPIT_SECRET_IMPORT``
        is set to ``1``/``true``/``yes``/``on`` on the gateway. The default cockpit
        posture (no secret export) is therefore unchanged.
      * **Bearer-authenticated** — the route requires auth (owner-paired token).
      * **Loopback-only** — refused whenever the cockpit is bound beyond loopback
        (``--allow-external``); secrets only ever leave over the loopback interface.
      * **Credential-shaped names only** — never the cockpit's own bearer token,
        which lives in a separate file under ``cockpit/token`` (not ``.env``).
    """
    import os

    if str(os.environ.get("HERMES_COCKPIT_SECRET_IMPORT", "")).strip().lower() not in {"1", "true", "yes", "on"}:
        return JsonResponse(
            403,
            {
                "error": "secret import disabled",
                "hint": "set HERMES_COCKPIT_SECRET_IMPORT=1 on the gateway to allow importing ~/.hermes/.env keys",
            },
        )
    if _ALLOW_REMOTE_EXECUTE:
        return JsonResponse(403, {"error": "secret import refused on a non-loopback cockpit"})

    env_path = _hermes_state_dir() / ".env"
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return JsonResponse(200, {"keys": {}, "count": 0, "present": False, "source": str(env_path)})

    keys: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        if name.startswith("export "):
            name = name[len("export ") :].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if name and value and _is_credential_key(name):
            keys[name] = value
    return JsonResponse(200, {"keys": keys, "count": len(keys), "present": True, "source": str(env_path)})


def credentials_summary(_req: Request) -> JsonResponse:
    """Read-only multi-provider credential inventory (names + configured yes/no).

    Never returns secret values. Lets the Omni UI / paired clients show which
    providers are ready without enabling ``HERMES_COCKPIT_SECRET_IMPORT``.
    """
    import os

    from hermes_cli.auth import (
        PROVIDER_REGISTRY,
        get_api_key_provider_status,
        has_usable_secret,
    )

    providers: list[dict] = []
    seen: set[str] = set()
    for pid, pconfig in PROVIDER_REGISTRY.items():
        if pid in seen or pconfig.id in seen:
            continue
        seen.add(pid)
        seen.add(pconfig.id)
        if pconfig.auth_type != "api_key":
            continue
        status = get_api_key_provider_status(pconfig.id)
        configured = bool(status.get("configured"))
        # Mirror resolve_provider("auto"): a bare GITHUB_TOKEN is for Skills Hub
        # / git tooling and must not advertise Copilot as inference-ready.
        if pconfig.id == "copilot":
            configured = any(
                has_usable_secret(os.getenv(v, ""))
                for v in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN")
            )
        providers.append(
            {
                "id": pconfig.id,
                "name": pconfig.name,
                "configured": configured,
                "env_vars": list(pconfig.api_key_env_vars),
            }
        )

    # Aggregators / specials not always in PROVIDER_REGISTRY as api_key rows.
    for pid, env_names in (
        ("openrouter", ("OPENROUTER_API_KEY", "OPENAI_API_KEY")),
        ("anthropic", ("ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN")),
    ):
        if any(p["id"] == pid for p in providers):
            continue
        configured = any(has_usable_secret(os.getenv(v, "")) for v in env_names)
        providers.append(
            {
                "id": pid,
                "name": pid,
                "configured": configured,
                "env_vars": list(env_names),
            }
        )

    providers.sort(key=lambda p: (not p["configured"], p["id"]))
    return JsonResponse(
        200,
        {
            "providers": providers,
            "configured_count": sum(1 for p in providers if p["configured"]),
            "total": len(providers),
        },
    )


def model_route_override(req: Request) -> JsonResponse:
    """Set/clear an owner model override, or flip paid routing (owner-gated).

    Body (any of):
      * ``task_class`` + ``model`` — pin a task to a model (``model`` empty or
        null clears the override). Reversible preference; token-authenticated.
      * ``paid_enabled`` (bool) — flip paid routing. Money-spend gate: requires
        ``authorization`` to equal the exact owner phrase. Audited via the
        override store (``authorized_by`` + ``updated_at``).
    Never accepts API keys.
    """
    from hermes_cli.jarvis_prime import task_router as tr

    body = req.body or {}
    changed: dict[str, Any] = {}

    # Validate the *entire* body before mutating anything. A combined body
    # (paid flip + a bad task class) must not leave the money-spend gate
    # changed while the request as a whole returns an error.
    want_paid = "paid_enabled" in body and body["paid_enabled"] is not None
    want_task = "task_class" in body

    if not (want_paid or want_task):
        return JsonResponse(
            400,
            {"error": "provide 'task_class'(+'model') and/or 'paid_enabled'"},
        )

    if want_paid:
        from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

        phrase = str(body.get("authorization", "")).strip()
        if phrase != AUTHORIZATION_PHRASE:
            return JsonResponse(
                403,
                {
                    "error": "owner authorization required to change paid routing",
                    "hint": f"reply exactly: {AUTHORIZATION_PHRASE!r}",
                },
            )

    pending_task: tuple[str, str | None] | None = None
    if want_task:
        task_class = str(body.get("task_class", "")).strip()
        try:
            tr.TaskClass.from_value(task_class)
        except ValueError:
            return JsonResponse(400, {"error": f"unknown task class: {task_class!r}"})
        raw_model = body.get("model")
        model = str(raw_model).strip() if raw_model else None
        pending_task = (task_class, model)

    # All inputs validated — now apply the mutations.
    if want_paid:
        try:
            tr.set_paid_enabled(bool(body["paid_enabled"]), authorized=True)
            changed["paid_enabled"] = bool(body["paid_enabled"])
        except Exception as exc:  # pragma: no cover - defensive
            return JsonResponse(500, {"error": str(exc)})

    if pending_task is not None:
        task_class, model = pending_task
        try:
            tr.set_task_override(task_class, model)
            changed["task_class"] = task_class
            changed["model"] = model
        except Exception as exc:  # pragma: no cover - defensive
            return JsonResponse(500, {"error": str(exc)})

    overrides = tr.load_overrides()
    return JsonResponse(
        200,
        {
            "ok": True,
            "changed": changed,
            "overrides": {
                "task_overrides": overrides.get("task_overrides", {}),
                "paid_enabled": overrides.get("paid_enabled"),
                "updated_at": overrides.get("updated_at"),
            },
        },
    )


def _local_name_match(installed: str, routed: str) -> bool:
    """Fuzzy match an installed Ollama tag against a router model id.

    Ollama tags ("gemma3:latest") and catalog ids ("gemma3", "qwen3:8b") never
    match exactly, so compare on a normalized stem (drop ``:latest``, lowercase)
    with prefix tolerance either way. Conservative: a non-match just means the
    model isn't *labelled* promoted, never a fabricated promotion.
    """
    def norm(s: str) -> str:
        s = s.strip().lower()
        return s[: -len(":latest")] if s.endswith(":latest") else s

    a, b = norm(installed), norm(routed)
    if not a or not b:
        return False
    return a == b or a.startswith(b) or b.startswith(a)


def models_local(_req: Request) -> JsonResponse:
    """Local model runtimes + installed variants + per-task promotion, with an
    **honest** status label per model.

    Read-only; never accepts or returns API keys. The strongest label this
    endpoint emits is ``promoted_for_task`` / ``variant_installed`` — a model is
    only ``smoke_tested`` after the explicit :func:`models_local_smoke` POST the
    owner triggers, so the cockpit never shows "ready" without evidence.
    """
    from hermes_cli.jarvis_prime import model_bootstrap as mb
    from hermes_cli.jarvis_prime import task_router as tr

    from . import generate

    # 1. Which runtimes' binaries are present (detection only — not "running").
    runtimes: list[dict[str, Any]] = []
    try:
        for name, info in mb.detect_local_runtimes().items():
            runtimes.append(
                {"name": name, "available": bool(info.get("available")), "path": info.get("path")}
            )
    except Exception:  # pragma: no cover - defensive
        runtimes = []
    ollama_available = any(r["name"] == "ollama" and r["available"] for r in runtimes)

    # 2. Is the Ollama runtime actually reachable, and what is installed?
    base = generate._ollama_base()
    reachable = False
    reach_error: str | None = None
    installed_names: list[str] = []
    try:
        installed_names = generate.installed_chat_models(base)
        reachable = True
    except Exception as exc:
        reach_error = str(exc)

    # 3. Per-task promotion + fallback from the free-first router (local tier).
    promoted: dict[str, list[str]] = {}
    fallback: dict[str, set[str]] = {}
    promotions_by_task: dict[str, str] = {}
    try:
        for decision in tr.all_routes():
            dd = decision.to_dict()
            tc = str(dd.get("task_class") or "")
            chosen = dd.get("chosen")
            if chosen and dd.get("route_tier") == "local_oss":
                promoted.setdefault(str(chosen), []).append(tc)
                promotions_by_task[tc] = str(chosen)
            for fb in dd.get("fallback_chain") or []:
                fallback.setdefault(str(fb), set()).add(tc)
    except Exception:  # pragma: no cover - defensive
        pass

    installed: list[dict[str, Any]] = []
    for name in installed_names:
        promoted_for = sorted(
            {t for m, tasks in promoted.items() for t in tasks if _local_name_match(name, m)}
        )
        fallback_for = sorted(
            {t for m, tasks in fallback.items() for t in tasks if _local_name_match(name, m)}
        )
        status = (
            "promoted_for_task"
            if promoted_for
            else ("fallback_only" if fallback_for else "variant_installed")
        )
        installed.append(
            {
                "name": name,
                "promoted_for": promoted_for,
                "fallback_for": fallback_for,
                "status": status,
            }
        )

    runtime_status = (
        "runtime_reachable" if reachable else ("configured" if ollama_available else "not_configured")
    )

    return JsonResponse(
        200,
        {
            "ollama_base": base,
            "runtime_status": runtime_status,
            "reachable": reachable,
            "reach_error": reach_error,
            "runtimes": runtimes,
            "installed": installed,
            "promotions": promotions_by_task,
            "generated_at": _now_iso(),
        },
    )


def models_local_smoke(req: Request) -> JsonResponse:
    """Explicit, owner-initiated tiny local generation — the **only** path that
    earns a model the ``smoke_tested`` label.

    Local, non-mutating, loopback (token-authenticated). Picks the policy/installed
    model when ``model`` is omitted. Never accepts API keys. A failure returns a
    200 with ``ok=false`` + reason so the cockpit can show "blocked", not crash.
    """
    import time

    from . import generate

    model = str((req.body or {}).get("model", "")).strip()
    base = generate._ollama_base()
    started = time.monotonic()
    try:
        chosen = model or generate.pick_model(base)
        reply = generate.ollama_generate(
            "Reply with the single word: ok", "", chosen, base=base, timeout=30.0
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        return JsonResponse(
            200,
            {
                "ok": bool(reply),
                "model": chosen,
                "reply_excerpt": reply[:200],
                "latency_ms": latency_ms,
            },
        )
    except Exception as exc:
        return JsonResponse(
            200,
            {"ok": False, "model": model or "(auto)", "error": str(exc)},
        )


# ---------------------------------------------------------------------------
# Memory (real JARVIS memory store; secret-rejection preserved)
# ---------------------------------------------------------------------------


def memory_list(req: Request) -> JsonResponse:
    """List memory as canonical cockpit ``MemoryItem`` objects (contract)."""
    query = req.query.get("q") or req.query.get("query")
    try:
        from hermes_cli.jarvis_prime.memory import MemoryStore

        from . import contract

        store = MemoryStore()
        if query:
            records = store.recollect(query, limit=int(req.query.get("limit", "50")))
        else:
            records = list(store.durable) + list(store.session)
        items = [contract.memory_item(r) for r in records]
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"items": [], "error": str(exc)})
    return JsonResponse(200, {"items": items})


def memory_create(req: Request) -> JsonResponse:
    """Create memory from a canonical ``MemoryItem`` body.

    Accepts the canonical UI fields (``title``/``content``/``category``/
    ``durability`` enum/``confidence`` enum/``tags``/``hidden``) and, for
    backward compatibility, the legacy flat ``key``/``value``. Returns the
    enriched item on success, or 422 when the store rejects it (secret-like
    or below the durable-confidence floor) — honest, never faked.
    """
    body = req.body
    key = str(body.get("title") or body.get("key") or "").strip()
    value = str(body.get("content") or body.get("value") or "").strip()
    if not key or not value:
        return JsonResponse(400, {"error": "title/content (or key/value) are required"})
    try:
        from hermes_cli.jarvis_prime.memory import MemoryStore

        from . import contract

        normalized = contract.normalize_category(body.get("category"))
        store = MemoryStore()
        record = store.remember(
            key=key,
            value=value,
            durability=contract.durability_to_store(body.get("durability")),
            source=str(body.get("source") or "cockpit"),
            confidence=contract.confidence_to_float(body.get("confidence", 1.0)),
            tags=tuple(str(t) for t in (body.get("tags") or ())),
            category=None if normalized == "UNCATEGORIZED" else normalized,
            hidden=bool(body.get("hidden", False)),
        )
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    if record is None:
        # Rejected (secret-like or below confidence floor) — honest, not fake.
        return JsonResponse(
            422, {"stored": False, "reason": "rejected (secret-like or low confidence)"}
        )
    return JsonResponse(201, {"stored": True, "item": contract.memory_item(record)})


def memory_delete(req: Request) -> JsonResponse:
    key = req.path_params.get("id") or str(req.body.get("key", ""))
    if not key:
        return JsonResponse(400, {"error": "memory key required"})
    try:
        from hermes_cli.jarvis_prime.memory import MemoryStore

        removed = MemoryStore().forget(key)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(200, {"removed": removed})


# ---------------------------------------------------------------------------
# Evidence Engine (real Research Vault; hybrid retrieval + citation verify)
# ---------------------------------------------------------------------------


def evidence_list(req: Request) -> JsonResponse:
    """List/search evidence as canonical ``EvidenceItem`` objects (contract §10d).

    A ``q`` runs the hybrid retrieval engine (BM25 over the vault blended with
    Memory-Tree hits); without it, the full vault is listed. Honest empty on
    any failure — never fabricated.
    """
    query = req.query.get("q") or req.query.get("query")
    try:
        from hermes_cli.jarvis_prime import evidence_engine as ee
        from hermes_cli.jarvis_prime.memory_tree import MemoryTreeStore
        from hermes_cli.jarvis_prime.research_vault import ResearchVault

        from . import contract

        vault = ResearchVault.load()
        if query:
            store = MemoryTreeStore.load()
            hits = ee.retrieve(query, vault=vault, memory_store=store,
                               limit=int(req.query.get("limit", "20")))
            items = [contract.evidence_hit(h) for h in hits]
            return JsonResponse(200, {"items": [], "hits": items})
        items = [contract.evidence_card(a) for a in vault.entries()]
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"items": [], "error": str(exc)})
    return JsonResponse(200, {"items": items})


def evidence_detail(req: Request) -> JsonResponse:
    """Return one evidence artifact by id."""
    art_id = req.path_params.get("id", "")
    if not art_id:
        return JsonResponse(400, {"error": "evidence id required"})
    try:
        from hermes_cli.jarvis_prime.research_vault import ResearchVault

        from . import contract

        vault = ResearchVault.load()
        art = vault.artifacts.get(art_id)
        if art is None:
            return JsonResponse(404, {"error": f"unknown evidence: {art_id}"})
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(200, {"item": contract.evidence_card(art)})


def evidence_verify(req: Request) -> JsonResponse:
    """Verify claims against evidence: citations, uncertain, contradictions.

    Body: ``{"claims": [...], "query": "optional retrieval query"}``. Secrets
    and chain-of-thought in claims are rejected (never become evidence).
    """
    claims = req.body.get("claims") or []
    if isinstance(claims, str):
        claims = [claims]
    if not isinstance(claims, list) or not claims:
        return JsonResponse(400, {"error": "claims (non-empty list) required"})
    query = str(req.body.get("query") or " ".join(str(c) for c in claims))
    try:
        from hermes_cli.jarvis_prime import evidence_engine as ee
        from hermes_cli.jarvis_prime.memory_tree import MemoryTreeStore
        from hermes_cli.jarvis_prime.research_vault import ResearchVault

        from . import contract

        vault = ResearchVault.load()
        store = MemoryTreeStore.load()
        hits = ee.retrieve(query, vault=vault, memory_store=store, limit=20)
        result = ee.CitationVerifier().verify(
            [str(c) for c in claims], hits, memory_store=store
        )
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(200, contract.evidence_verify_result(result))


def evidence_promote(req: Request) -> JsonResponse:
    """Promote an evidence artifact into durable Memory Tree.

    Routes through ``MemoryTreeStore.write`` so the write policy (secret /
    chain-of-thought rejection, durable confidence floor, provenance) is
    preserved. A low-confidence promotion needs the owner authorization
    phrase — otherwise it is honestly rejected (422), never auto-promoted.
    """
    art_id = req.path_params.get("id", "")
    if not art_id:
        return JsonResponse(400, {"error": "evidence id required"})
    authorization = str(req.body.get("authorization") or "")
    try:
        from hermes_cli.jarvis_prime import evidence_engine as ee
        from hermes_cli.jarvis_prime.memory_tree import MemoryTreeStore
        from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE
        from hermes_cli.jarvis_prime.research_vault import ResearchVault

        vault = ResearchVault.load()
        art = vault.artifacts.get(art_id)
        if art is None:
            return JsonResponse(404, {"error": f"unknown evidence: {art_id}"})

        owner_approved = authorization == AUTHORIZATION_PHRASE
        store = MemoryTreeStore.load()
        result = ee.promote_to_memory(art, store, owner_approved=owner_approved)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})

    if not result.ok:
        return JsonResponse(
            422,
            {
                "promoted": False,
                "reasons": list(result.reasons),
                "hint": f"send authorization exactly: {AUTHORIZATION_PHRASE!r}",
            },
        )
    payload: dict[str, Any] = {"promoted": True, "node_id": result.node.id if result.node else None}
    if result.contradiction is not None:
        payload["contradiction"] = result.contradiction.to_dict()
    return JsonResponse(201, payload)


def evidence_demote(req: Request) -> JsonResponse:
    """Remove an evidence artifact from the vault (demotion)."""
    art_id = req.path_params.get("id", "")
    if not art_id:
        return JsonResponse(400, {"error": "evidence id required"})
    try:
        from hermes_cli.jarvis_prime.research_vault import ResearchVault

        vault = ResearchVault.load()
        removed = 1 if vault.artifacts.pop(art_id, None) is not None else 0
        if removed:
            vault.save()
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(200, {"removed": removed})
# Memory Tree (MEM-2): proposed inbox, owner decisions, contradictions,
# freshness. Backed by the provenance-first MemoryTreeStore — the same store
# the live JARVIS loop captures into. The flat /memory endpoints above are
# untouched (backward compatible).
# ---------------------------------------------------------------------------


def _load_memory_tree():
    """Load the live Memory Tree from the HERMES_HOME-aware default path."""
    from hermes_cli.jarvis_prime.memory_tree import MemoryTreeStore

    return MemoryTreeStore.load()


def memory_tree_search(req: Request) -> JsonResponse:
    """Ranked Memory Tree search (contested excluded unless asked)."""
    query = req.query.get("q") or req.query.get("query") or ""
    include_contested = str(
        req.query.get("include_contested", "")
    ).strip().lower() in ("1", "true", "yes")
    limit = int(req.query.get("limit", "25"))
    try:
        from . import contract

        store = _load_memory_tree()
        hits = store.search(query, include_contested=include_contested, limit=limit)
        nodes = [contract.memory_tree_node(h.node) for h in hits]
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"nodes": [], "error": str(exc)})
    return JsonResponse(200, {"nodes": nodes})


def memory_tree_proposed(req: Request) -> JsonResponse:
    """The proposed-memory inbox: candidates awaiting an owner decision."""
    try:
        from . import contract

        store = _load_memory_tree()
        nodes = [contract.memory_tree_node(n) for n in store.proposed()]
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"nodes": [], "error": str(exc)})
    return JsonResponse(200, {"nodes": nodes})


def memory_tree_decision(req: Request) -> JsonResponse:
    """Owner decision on a proposed node: approve | reject | supersede.

    - ``approve`` promotes to durable. If promotion conflicts with an existing
      durable fact the contradiction is returned — never a silent overwrite.
    - ``reject`` marks the node rejected (excluded from recall).
    - ``supersede`` requires ``supersedes_id`` (the older node this replaces).
    """
    node_id = req.path_params.get("id", "")
    decision = str(req.body.get("decision", "")).strip().lower()
    if decision not in ("approve", "reject", "supersede"):
        return JsonResponse(
            400, {"error": "decision must be approve, reject, or supersede"}
        )
    try:
        from hermes_cli.jarvis_prime.memory_tree import ApprovalState

        from . import contract

        store = _load_memory_tree()
        if store.get(node_id) is None:
            return JsonResponse(404, {"error": f"unknown memory node: {node_id}"})

        if decision == "approve":
            result = store.promote_to_durable(node_id)
            payload: dict[str, Any] = {
                "decided": "approve",
                "node": contract.memory_tree_node(result.node),
            }
            if result.contradiction is not None:
                payload["contradiction"] = contract.contradiction_view(
                    result.contradiction
                )
            return JsonResponse(200, payload)

        if decision == "reject":
            node = store.set_approval(node_id, ApprovalState.REJECTED)
            return JsonResponse(
                200, {"decided": "reject", "node": contract.memory_tree_node(node)}
            )

        # supersede
        supersedes_id = str(req.body.get("supersedes_id", "")).strip()
        if not supersedes_id:
            return JsonResponse(
                400, {"error": "supersede requires supersedes_id"}
            )
        if store.get(supersedes_id) is None:
            return JsonResponse(
                404, {"error": f"unknown node to supersede: {supersedes_id}"}
            )
        note = str(req.body.get("note", ""))
        loser = store.supersede(supersedes_id, node_id, note=note)
        # The approving node is also owner-confirmed by the supersession.
        store.set_approval(node_id, ApprovalState.OWNER_APPROVED)
        return JsonResponse(
            200,
            {
                "decided": "supersede",
                "winner": contract.memory_tree_node(store.get(node_id)),
                "superseded": contract.memory_tree_node(loser),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})


def memory_contradictions(req: Request) -> JsonResponse:
    """Open (contested) contradiction reports awaiting resolution."""
    try:
        from . import contract

        store = _load_memory_tree()
        items = [contract.contradiction_view(r) for r in store.open_contradictions()]
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"contradictions": [], "error": str(exc)})
    return JsonResponse(200, {"contradictions": items})


def memory_contradiction_resolve(req: Request) -> JsonResponse:
    """Resolve a contradiction: the winner stays, the loser is superseded."""
    report_id = req.path_params.get("id", "")
    winner_id = str(req.body.get("winner_id", "")).strip()
    if not winner_id:
        return JsonResponse(400, {"error": "winner_id is required"})
    try:
        from . import contract

        store = _load_memory_tree()
        if report_id not in store.contradictions:
            return JsonResponse(404, {"error": f"unknown contradiction: {report_id}"})
        report = store.resolve_contradiction(
            report_id, winner_id=winner_id, note=str(req.body.get("note", ""))
        )
    except ValueError as exc:
        return JsonResponse(400, {"error": str(exc)})
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(200, {"resolved": contract.contradiction_view(report)})


def memory_freshness(req: Request) -> JsonResponse:
    """Nodes overdue (or within ``within_days``) for a freshness review."""
    within_days = int(req.query.get("within_days", "0"))
    try:
        from . import contract

        store = _load_memory_tree()
        nodes = [
            contract.memory_tree_node(n) for n in store.due_for_review(within_days)
        ]
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"nodes": [], "error": str(exc)})
    return JsonResponse(200, {"nodes": nodes})


# ---------------------------------------------------------------------------
# Audit (decision ledger) + tasks (job queue)
# ---------------------------------------------------------------------------


def audit_events(req: Request) -> JsonResponse:
    """Leveled cockpit events (contract §9) from the structured event log.

    Returns ``{"events": [...], "next_cursor": null}`` in the ``CockpitEvent``
    shape (ts/level/source/job_id/message/attributes), filtered by the §9 query
    params (``since``/``level``/``source``/``job_id``/``limit``). Honest-empty
    until events are emitted. (Decision-ledger summaries live at
    ``GET /v1/cockpit/audit``.)
    """
    from . import event_log

    try:
        limit = max(1, min(int(req.query.get("limit", "100")), 500))
    except ValueError:
        limit = 100
    events = event_log.read(
        since=req.query.get("since"),
        level=req.query.get("level"),
        source=req.query.get("source"),
        job_id=req.query.get("job_id"),
        limit=limit,
    )
    return JsonResponse(200, {"events": events, "next_cursor": None})


def audit_list(req: Request) -> JsonResponse:
    """Audit records (canonical ``AuditRecord``) from the decision ledger."""
    limit = int(req.query.get("limit", "100"))
    records: list[dict[str, Any]] = []
    try:
        from hermes_cli import decision_ledger as dl

        from . import contract

        for path in dl.list_ledgers()[:limit]:
            try:
                ledger = dl.read_ledger(path)
                records.append(contract.audit_record(ledger, path))
            except Exception:
                continue
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"records": [], "error": str(exc)})
    return JsonResponse(200, {"records": records})


def audit_proof(req: Request) -> JsonResponse:
    """Full proof bundle (canonical ``ProofRecord``) for one audit id."""
    proof_id = req.path_params.get("id", "")
    try:
        from hermes_cli import decision_ledger as dl

        from . import contract

        for path in dl.list_ledgers():
            try:
                ledger = dl.read_ledger(path)
            except Exception:
                continue
            if contract.ledger_id(ledger, path) == proof_id:
                return JsonResponse(200, contract.audit_proof(ledger, path))
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(404, {"error": f"unknown proof: {proof_id}"})


def _collect_jobs() -> list[dict[str, Any]]:
    """Merge JobQueue + orchestrator jobs into canonical ``CockpitJob`` dicts.

    Shared by the ``/jobs/stream`` SSE diff so the live stream and the REST
    ``jobs_list`` project through the same adapters and cannot drift. Best-effort
    per store — one failing never blanks the other. (Keep in sync with
    ``jobs_list``.)
    """
    from . import contract

    jobs: list[dict[str, Any]] = []
    try:
        from hermes_cli.job_queue import JobQueue

        for entry in JobQueue().list_jobs():
            jobs.append(contract.cockpit_job(entry))
    except Exception:  # pragma: no cover - defensive
        pass
    try:
        from hermes_cli import orchestrator as _orch

        for job in _orch.list_jobs():
            jobs.append(contract.orchestrator_job(job))
    except Exception:  # pragma: no cover - defensive
        pass
    jobs.sort(key=lambda j: j.get("created_at") or "", reverse=True)
    return jobs


def jobs_list(_req: Request) -> JsonResponse:
    """List jobs as canonical cockpit ``CockpitJob`` objects (contract §4)."""
    jobs: list[dict[str, Any]] = []
    try:
        from hermes_cli.job_queue import JobQueue

        from . import contract

        for entry in JobQueue().list_jobs():
            jobs.append(contract.cockpit_job(entry))
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(
            200,
            {"jobs": [], "next_cursor": None, "prev_cursor": None, "error": str(exc)},
        )
    # Also surface orchestrator (/orchestrate) jobs — a separate store from the
    # JobQueue — so the app's Jobs list reflects the whole pipeline, not just
    # queue entries. Best-effort: an orchestrator read failure must not blank
    # out the JobQueue jobs already collected.
    try:
        from hermes_cli import orchestrator as _orch

        for job in _orch.list_jobs():
            jobs.append(contract.orchestrator_job(job))
    except Exception:  # pragma: no cover - defensive
        pass
    jobs.sort(key=lambda j: j.get("created_at") or "", reverse=True)
    return JsonResponse(200, {"jobs": jobs, "next_cursor": None, "prev_cursor": None})


def job_get(req: Request) -> JsonResponse:
    """Return one canonical ``CockpitJob`` (contract §4)."""
    job_id = req.path_params.get("id", "")
    try:
        from hermes_cli.job_queue import JobQueue, JobQueueNotFoundError

        from . import contract

        try:
            entry = JobQueue().get_job(job_id)
        except JobQueueNotFoundError:
            # Fall back to the orchestrator store (/orchestrate jobs live there,
            # not in the JobQueue) before declaring the id unknown.
            from hermes_cli import orchestrator as _orch

            ojob = _orch.get_job(job_id)
            if ojob is not None:
                return JsonResponse(200, contract.orchestrator_job(ojob))
            return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(200, contract.cockpit_job(entry))


def jobs_dispatch(req: Request) -> JsonResponse:
    """Dispatch (enqueue) a new job (contract §4).

    Enqueues a ``queued`` entry only — nothing executes here; a worker
    runner advances it. ``watch`` is a cockpit-side intent and ignored.
    """
    body = req.body
    title = str(body.get("title", "")).strip()
    prompt = str(body.get("prompt", "")).strip()
    worker_id = str(body.get("worker_id", "")).strip()
    if not title or not prompt:
        return JsonResponse(400, {"error": "title and prompt are required"})
    try:
        import secrets as _secrets

        from hermes_cli.job_queue import JobQueue, WorkerQueueEntry

        from . import contract

        job_id = "job_" + _secrets.token_hex(8)
        workspace = str(body.get("workspace_path") or "")
        metadata: dict[str, Any] = {"title": title, "source": "cockpit"}
        if worker_id:
            metadata["worker_id"] = worker_id
        if workspace:
            metadata["workspace_path"] = workspace
        if body.get("branch_hint"):
            metadata["branch"] = str(body["branch_hint"])
        workers = [WorkerQueueEntry(worker_id=worker_id)] if worker_id else []
        entry = JobQueue().add_job(
            job_id=job_id,
            prompt=prompt,
            repo_root=workspace,
            workers=workers,
            metadata=metadata,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    from . import event_log

    event_log.emit("info", "gateway", f"job dispatched: {title}", job_id=job_id)
    return JsonResponse(201, contract.cockpit_job(entry))


def job_run(req: Request) -> JsonResponse:
    """Run a job on a worker via the orchestrator's gated 5-step contract.

    This is the bridge that gives the app **real agentic reasoning**: it
    dispatches to a worker lane (e.g. ``codex-execute`` / ``claude-execute``,
    which run the official Codex / Claude Code CLIs) and returns the job plus
    its worker ledger trail.

    Double-gated for execute lanes (``requires_approval``):
      1. **Owner phrase** — ``authorization`` must equal the exact owner phrase;
         on match the job's ``execute`` phase is granted, then dispatched.
      2. **Loopback-only** — refused when the server is bound beyond loopback
         (``--allow-external``), so a network-reachable cockpit can't trigger
         repo-editing execution.
    Non-gated lanes (local planner / handoff) dispatch directly.
    """
    job_id = req.path_params.get("id", "")
    worker_id = str(req.body.get("worker_id", "")).strip() or "hermes-local-planner"
    authorization = str(req.body.get("authorization", "")).strip()
    try:
        from hermes_cli import orchestrator as orch

        from . import contract

        job = orch.get_job(job_id)
        if job is None:
            return JsonResponse(404, {"error": f"unknown job: {job_id}"})

        gate = _evaluate_execute_gate(worker_id, authorization)
        if gate.error is not None:
            return gate.error
        if gate.requires_approval and not gate.authorized:
            return JsonResponse(
                403,
                {
                    "error": "owner approval required to run an execute lane",
                    "hint": gate.authorization_hint,
                },
            )
        if gate.requires_approval:
            orch.approve_phase(job_id, "execute")

        out = orch.dispatch_job(job_id, worker_id=worker_id)
        if out is None:
            return JsonResponse(404, {"error": f"unknown job: {job_id}"})
        trail = [
            e
            for e in orch.get_ledger(job_id).get(job_id, [])
            if str(e.get("kind", "")).startswith("worker_")
        ]
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(
        200, {"job": contract.orchestrator_job(out), "worker_trail": trail[-6:]}
    )


def job_lanes(_req: Request) -> JsonResponse:
    """The **runnable** worker lanes that ``job_run`` accepts (contract §4).

    These are the built-in worker adapters (``hermes_cli.workers``) — e.g.
    ``codex-execute`` / ``claude-execute`` / ``hermes-local-planner`` — NOT the
    detection lanes from ``runtime_workers`` (a different registry used only to
    show which CLIs are installed). The cockpit dispatch/run picker must source
    worker ids from here so a selected lane is one ``job_run`` will accept;
    ``requires_approval`` tells the app which lanes need the owner phrase.
    """
    lanes: list[dict[str, Any]] = []
    try:
        from hermes_cli.workers import builtin_worker_classes

        for cls in builtin_worker_classes():
            lanes.append({
                "id": getattr(cls, "id", ""),
                "display_name": getattr(cls, "display_name", "") or getattr(cls, "id", ""),
                "requires_approval": bool(getattr(cls, "requires_approval", True)),
            })
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"lanes": [], "error": str(exc)})
    return JsonResponse(200, {"lanes": lanes})


def orchestrate_submit(req: Request) -> JsonResponse:
    """Create a real **orchestrator** job from a prompt (the ``/orchestrate``
    path), so the app's *new backend job* is one ``job_run`` can actually run.

    Unlike ``jobs_dispatch`` (which enqueues a ``JobQueue`` entry that ``job_run``
    cannot find), this records the job in the orchestrator store via
    :func:`hermes_cli.orchestrator.submit_job`. It spawns nothing — running a
    worker is a separate, owner-gated ``job_run`` call. Returns the canonical
    ``CockpitJob`` (orchestrator projection) so the new job appears in the list
    and is immediately runnable.
    """
    prompt = str(req.body.get("prompt", "")).strip()
    if not prompt:
        return JsonResponse(400, {"error": "prompt is required"})
    try:
        from hermes_cli import orchestrator as orch

        from . import contract

        job = orch.submit_job(prompt)
    except ValueError as exc:
        return JsonResponse(400, {"error": str(exc)})
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(201, contract.orchestrator_job(job))


# ---------------------------------------------------------------------------
# Per-device pairing (Sprint 6) — additive credential path that runs
# ALONGSIDE the shared cockpit token (gateway.cockpit.auth), never replacing
# it. These two routes are gated exactly like /v1/health (no shared-token
# requirement) so a brand-new device can obtain its OWN per-device token; the
# pairing code + lockout/rate-limit are the protection, and tokens are stored
# only as hashes (gateway.cockpit.device_pairing). The raw device token is
# returned exactly once, here, and never logged.
# ---------------------------------------------------------------------------


def pair_start(req: Request) -> JsonResponse:
    """Begin pairing a new device — returns a short-lived pairing code.

    Body: ``{"device_name": "Jeremiah's Pixel"}`` (optional). Returns the
    ``pairing_code`` and its ``expires_at`` epoch. A 429 is returned when the
    request is refused (rate-limited, locked out after repeated bad confirms,
    or too many codes already pending) — honest, never a fabricated code.
    """
    from . import device_pairing as dp

    device_name = str((req.body or {}).get("device_name", "")).strip()
    result = dp.start_pairing(device_name)
    if result is None:
        return JsonResponse(
            429,
            {
                "error": "pairing temporarily unavailable",
                "hint": "rate-limited, locked out, or too many pending codes; "
                "wait and retry",
            },
        )
    from . import event_log

    # Audit only — the pairing code itself is deliberately NOT logged.
    event_log.emit("info", "gateway", "device pairing started")
    return JsonResponse(
        201,
        {
            "pairing_code": result.pairing_code,
            "expires_at": result.expires_at,
            "expires_in": dp.CODE_TTL_SECONDS,
        },
    )


def pair_confirm(req: Request) -> JsonResponse:
    """Confirm a pairing code — returns a fresh per-device token ONCE.

    Body: ``{"pairing_code": "ABCD2345", "authorization": "<owner phrase>"}``.
    On a loopback-only cockpit (default ``--host 127.0.0.1``) the owner phrase
    is NOT required: anything that can reach 127.0.0.1 is already on the device,
    so the gate was friction without security benefit. When the cockpit is
    launched ``--allow-external`` (remote-reachable), the exact owner phrase IS
    required so a remote caller can never self-issue a credential. On a valid,
    unexpired code a new ``device_id`` + raw ``token`` are returned; only the
    token's hash is kept at rest. A bad/expired code (or a locked-out store) is
    a 401 — and counts toward the brute-force lockout. A missing/wrong phrase in
    external mode is a 403 and short-circuits before the code is consumed. The
    raw token is never logged.
    """
    from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

    from . import device_pairing as dp

    code = str((req.body or {}).get("pairing_code", "")).strip()
    if not code:
        return JsonResponse(400, {"error": "pairing_code is required"})

    # Owner gate: pair/start only mints a short-lived, rate-limited code (no
    # credential), so it stays open; the device token is issued only here.
    # On a loopback-only cockpit (default) the gate is skipped because nothing
    # outside this device can reach the route; if the server was started with
    # ``--allow-external`` (remote-reachable), the exact owner phrase is still
    # required so a remote caller can never self-issue a credential.
    phrase = str((req.body or {}).get("authorization", "")).strip()
    if _ALLOW_REMOTE_EXECUTE and phrase != AUTHORIZATION_PHRASE:
        return JsonResponse(
            403,
            {
                "error": "owner authorization required",
                "hint": f"reply exactly: {AUTHORIZATION_PHRASE!r}",
            },
        )

    result = dp.confirm_pairing(code)
    if result is None:
        return JsonResponse(
            401, {"error": "invalid or expired pairing code"}
        )
    from . import event_log

    # Audit the device id only — never the token.
    event_log.emit(
        "info", "gateway", "device paired", attributes={"device_id": result.device_id}
    )
    return JsonResponse(
        201,
        {
            "device_id": result.device_id,
            "token": result.token,
            "token_type": "Bearer",
        },
    )


def avatar_persona_get(_req: Request) -> JsonResponse:
    """The companion's adopted persona (e.g. 'Goku'), or null if default."""
    from gateway.cockpit import persona_store as ps

    return JsonResponse(200, ps.load_persona() or {"persona": None})


def avatar_persona_set(req: Request) -> JsonResponse:
    """Adopt a persona from a description: the model researches the character
    and writes the persona the chat then speaks in. ``{"description": "Goku
    from Dragon Ball", "name": "Goku"}``; empty description clears it."""
    from gateway.cockpit import persona_store as ps

    description = str(req.body.get("description", "")).strip()
    name = str(req.body.get("name", "")).strip()
    if not description:
        ps.clear_persona()
        return JsonResponse(200, {"persona": None, "cleared": True})
    try:
        data = ps.generate_persona(description, name=name)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(201, data)


def room_list(_req: Request) -> JsonResponse:
    """The companion's room items (AI-generated furniture), with images."""
    from gateway.cockpit import room_store as rs

    return JsonResponse(
        200,
        {"items": rs.list_items(), "image_generation": rs.image_generation_available()},
    )


def room_generate(req: Request) -> JsonResponse:
    """Generate a room item from a text prompt ('a Victorian desk') via the
    image model. 503 when no image model is configured (honest, not faked)."""
    from gateway.cockpit import room_store as rs

    prompt = str(req.body.get("prompt", "")).strip()
    if not prompt:
        return JsonResponse(400, {"error": "prompt is required"})
    try:
        item = rs.generate_item(prompt)
    except RuntimeError as exc:
        return JsonResponse(503, {"error": str(exc)})
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(201, item)


def room_delete(req: Request) -> JsonResponse:
    from gateway.cockpit import room_store as rs

    ok = rs.delete_item(req.path_params.get("id", ""))
    return JsonResponse(200 if ok else 404, {"deleted": ok})


def room_place(req: Request) -> JsonResponse:
    """Persist a furniture item's normalized (x, y) placement in the room."""
    from gateway.cockpit import room_store as rs

    try:
        x = float(req.body.get("x", 0.5))
        y = float(req.body.get("y", 0.6))
    except (TypeError, ValueError):
        return JsonResponse(400, {"error": "x and y must be numbers (0..1)"})
    ok = rs.set_position(req.path_params.get("id", ""), x, y)
    return JsonResponse(200 if ok else 404, {"placed": ok})


def job_cancel(req: Request) -> JsonResponse:
    """Cancel a job (contract §4). 409 if already terminal.

    Resolves the id against both stores so the Job Detail cockpit's Cancel
    control works for either: a JobQueue entry cancels via
    ``JobQueue.cancel_job``; an orchestrator (/orchestrate) job via
    ``orchestrator.cancel_job`` (which leaves an already-published job alone
    so the publish record stays honest). 404 only when the id is in neither.
    """
    job_id = req.path_params.get("id", "")
    reason = req.body.get("reason")
    kind, obj = _resolve_job(job_id)
    if obj is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    from . import contract

    if kind == "queue":
        try:
            from hermes_cli.job_queue import JobQueue, QueueState

            if obj.state in QueueState.TERMINAL:
                return JsonResponse(409, {"error": f"job already {obj.state}"})
            entry = JobQueue().cancel_job(job_id, note=str(reason) if reason else None)
        except Exception as exc:  # pragma: no cover - defensive
            return JsonResponse(500, {"error": str(exc)})
        return JsonResponse(200, contract.cockpit_job(entry))
    try:
        from hermes_cli import orchestrator as _orch

        out = _orch.cancel_job(job_id)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    if out is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    return JsonResponse(200, contract.orchestrator_job(out))


# ---------------------------------------------------------------------------
# Job detail + controls (read-only ledger; pause/resume/rerun/approve/diff/validate)
# ---------------------------------------------------------------------------
#
# A job id addresses one of two stores: the JobQueue (cockpit-dispatched
# queue entries) or the orchestrator (/orchestrate flow). Every control
# resolves the id against both — JobQueue first, orchestrator as fallback —
# exactly like ``job_get``. We never invent a third store.


def _resolve_job(job_id: str) -> tuple[Optional[str], Any]:
    """Return ``("queue"|"orchestrator", obj)`` or ``(None, None)`` if unknown."""
    try:
        from hermes_cli.job_queue import JobQueue, JobQueueNotFoundError

        try:
            return "queue", JobQueue().get_job(job_id)
        except JobQueueNotFoundError:
            pass
    except Exception:  # pragma: no cover - defensive (queue import/load failure)
        pass
    try:
        from hermes_cli import orchestrator as _orch

        ojob = _orch.get_job(job_id)
        if ojob is not None:
            return "orchestrator", ojob
    except Exception:  # pragma: no cover - defensive
        pass
    return None, None


def job_ledger(req: Request) -> JsonResponse:
    """Read-only job detail + decision-ledger timeline (contract §4).

    Surfaces the execution story the Job Detail screen renders: objective,
    plan, worker assignments, current step, evidence, files touched, commands
    run, test results, approvals, timeline, rollback. Honest derivation only.
    """
    job_id = req.path_params.get("id", "")
    kind, obj = _resolve_job(job_id)
    if obj is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    from . import contract

    if kind == "queue":
        return JsonResponse(200, contract.queue_job_detail(obj))
    try:
        from hermes_cli import orchestrator as _orch

        entries = _orch.get_ledger(job_id).get(job_id, [])
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(200, contract.orchestrator_job_detail(obj, entries))


def job_pause(req: Request) -> JsonResponse:
    """Pause a running/queued job (contract §4). Queue jobs only.

    Orchestrator (/orchestrate) jobs have no scheduler-side pause — they
    advance only on explicit owner approval — so pausing one is an honest
    409 rather than a fabricated no-op.
    """
    job_id = req.path_params.get("id", "")
    kind, obj = _resolve_job(job_id)
    if obj is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    if kind != "queue":
        return JsonResponse(
            409,
            {"error": "pause applies to queue jobs; orchestrator jobs pause by "
             "withholding approval, not by a scheduler toggle"},
        )
    try:
        from hermes_cli.job_queue import JobQueue, JobQueueError

        from . import contract

        reason = req.body.get("reason")
        entry = JobQueue().pause_job(job_id, note=str(reason) if reason else None)
    except JobQueueError as exc:
        return JsonResponse(409, {"error": str(exc)})
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(200, contract.cockpit_job(entry))


def job_resume(req: Request) -> JsonResponse:
    """Resume a paused/blocked/disconnected/failed job (contract §4).

    The unblock action for a blocked job. Re-queues a queue entry (the
    dispatcher claims it next) or re-queues an orchestrator job. Reversible
    and local — no owner phrase required to *resume* already-approved work.
    """
    job_id = req.path_params.get("id", "")
    kind, obj = _resolve_job(job_id)
    if obj is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    from . import contract

    if kind == "queue":
        try:
            from hermes_cli.job_queue import JobQueue, JobQueueError

            reason = req.body.get("reason")
            entry = JobQueue().resume_job(job_id, note=str(reason) if reason else None)
        except JobQueueError as exc:
            return JsonResponse(409, {"error": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive
            return JsonResponse(500, {"error": str(exc)})
        return JsonResponse(200, contract.cockpit_job(entry))
    try:
        from hermes_cli import orchestrator as _orch

        out = _orch.resume_job(job_id)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    if out is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    return JsonResponse(200, contract.orchestrator_job(out))


def job_rerun(req: Request) -> JsonResponse:
    """Rerun a failed/disconnected step (contract §4). Queue jobs only.

    Resets one failed worker so the dispatcher runs it again. ``worker_id``
    may be passed explicitly; otherwise the first non-successful worker is
    chosen. Reversible and local.
    """
    job_id = req.path_params.get("id", "")
    kind, obj = _resolve_job(job_id)
    if obj is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    if kind != "queue":
        return JsonResponse(
            409, {"error": "rerun applies to queue jobs (per-worker retry)"}
        )
    try:
        from hermes_cli.job_queue import (
            JobQueue,
            JobQueueError,
            WorkerNotFoundError,
            WorkerStatus,
        )

        from . import contract

        worker_id = str(req.body.get("worker_id", "")).strip()
        if not worker_id:
            retryable = {
                WorkerStatus.FAILED,
                WorkerStatus.DISCONNECTED,
                WorkerStatus.BLOCKED,
            }
            for w in getattr(obj, "workers", None) or []:
                if getattr(w, "status", "") in retryable:
                    worker_id = w.worker_id
                    break
        if not worker_id:
            return JsonResponse(
                400,
                {"error": "no failed/blocked worker to rerun; pass worker_id"},
            )
        entry = JobQueue().retry_worker(job_id, worker_id)
    except WorkerNotFoundError as exc:
        return JsonResponse(404, {"error": str(exc)})
    except JobQueueError as exc:
        return JsonResponse(409, {"error": str(exc)})
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(200, contract.cockpit_job(entry))


def job_approve(req: Request) -> JsonResponse:
    """Approve a gated job phase (contract §4) — owner gate preserved.

    Double-gated exactly like ``job_run``:
      1. **Owner phrase** — ``authorization`` must equal the exact owner phrase.
      2. **Loopback-only** — refused on a non-loopback (``--allow-external``)
         cockpit, so a network-reachable cockpit can't grant execute.
    Targets orchestrator job phases (``execute``/``publish``/``remote``/…).
    """
    job_id = req.path_params.get("id", "")
    phase = str(req.body.get("phase", "execute")).strip() or "execute"
    authorization = str(req.body.get("authorization", "")).strip()
    kind, obj = _resolve_job(job_id)
    if obj is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    if _ALLOW_REMOTE_EXECUTE:
        return JsonResponse(
            403,
            {"error": "owner approvals are disabled on a non-loopback cockpit; "
             "run the runtime locally (loopback) to approve gated phases"},
        )
    from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

    if authorization != AUTHORIZATION_PHRASE:
        return JsonResponse(
            403,
            {"error": "owner approval required to grant a gated phase",
             "hint": f"send authorization exactly: {AUTHORIZATION_PHRASE!r}"},
        )
    if kind != "orchestrator":
        return JsonResponse(
            409, {"error": "approve targets orchestrator job phases"}
        )
    try:
        from hermes_cli import orchestrator as _orch

        from . import contract

        out = _orch.approve_phase(job_id, phase)
    except ValueError as exc:
        return JsonResponse(400, {"error": str(exc)})
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    if out is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    return JsonResponse(200, contract.orchestrator_job(out))


def job_diff(req: Request) -> JsonResponse:
    """Read-only working-tree diff for a job's workspace (contract §4/§6).

    "Open patch" on mobile. Runs ``git diff`` in the job's workspace (vs the
    job's base branch when recorded). Honest empty when the job has no
    workspace (orchestrator jobs don't carry one). Read-only — never edits.
    """
    job_id = req.path_params.get("id", "")
    kind, obj = _resolve_job(job_id)
    if obj is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    workspace = ""
    base: Optional[str] = None
    if kind == "queue":
        workspace = str(getattr(obj, "repo_root", "") or "")
        base = (dict(getattr(obj, "metadata", None) or {})).get("base_branch")
    if not workspace:
        return JsonResponse(200, {"files": [], "diff": "", "truncated": False})
    return JsonResponse(200, _git_diff(workspace, base))


def job_validate(req: Request) -> JsonResponse:
    """Run verification gates against a job's workspace (contract §4/§7).

    "Run verification" on mobile. Executes the real ``ValidationRunner`` and
    projects its report into the canonical ``ValidationSnapshot`` shape — pass/
    fail come from the actual checks, never fabricated. Honest 409 when the job
    has no workspace to validate.
    """
    job_id = req.path_params.get("id", "")
    kind, obj = _resolve_job(job_id)
    if obj is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    workspace = str(getattr(obj, "repo_root", "") or "") if kind == "queue" else ""
    if not workspace:
        return JsonResponse(
            409, {"error": "job has no workspace to validate"}
        )
    try:
        from hermes_cli.validation import ValidationRunner

        from . import contract

        report = ValidationRunner(workspace).run()
        payload = contract.validation_snapshot(report.to_dict())
    except Exception as exc:  # pragma: no cover - defensive (runner/env failure)
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(200, payload)


def _git_diff(workspace: str, base: Optional[str], *, limit: int = 200_000) -> dict[str, Any]:
    """Run ``git diff`` (and ``--numstat``) in ``workspace``; honest on failure."""
    import subprocess
    from pathlib import Path

    ws = Path(workspace)
    if not ws.is_dir():
        return {"files": [], "diff": "", "truncated": False}
    rev = f"{base}...HEAD" if base else None

    def _run(args: list[str]) -> str:
        try:
            out = subprocess.run(
                ["git", "-C", str(ws), *args],
                capture_output=True,
                text=True,
                timeout=20,
            )
            return out.stdout if out.returncode == 0 else ""
        except Exception:
            return ""

    diff_args = ["diff"] + ([rev] if rev else [])
    diff_text = _run(diff_args)
    numstat = _run(["diff", "--numstat"] + ([rev] if rev else []))
    files: list[dict[str, Any]] = []
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        added, removed, path = parts
        files.append({
            "path": path,
            "additions": int(added) if added.isdigit() else 0,
            "deletions": int(removed) if removed.isdigit() else 0,
        })
    truncated = len(diff_text) > limit
    return {"files": files, "diff": diff_text[:limit], "truncated": truncated}


# Read-only job-workspace browsers. All four resolve the job exactly like
# ``job_diff``/``job_validate``, read strictly inside the workspace, and never
# require the owner phrase (they only surface already-approved local work).

_JOB_FILE_MAX_BYTES = 1_000_000  # 1 MB preview cap (contract §6)


def _job_workspace(kind: Optional[str], obj: Any) -> str:
    """The on-disk workspace for a job, or ``""``. Only queue jobs carry one."""
    if kind != "queue":
        return ""
    return str(getattr(obj, "repo_root", "") or "")


def _safe_workspace_target(workspace: str, rel: str):
    """Resolve ``rel`` under ``workspace``; return ``(root, target)``.

    Path-traversal safe (same idiom as ``inline_tools.repo_read``): the resolved
    target must stay under the resolved workspace root, else ``target`` is
    ``None`` (the caller answers 400 — never follows the escape).
    """
    from pathlib import Path

    root = Path(workspace).resolve()
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return root, None
    return root, target


def _hermes_state_dir() -> Path:
    """Resolved ``${HERMES_HOME:-~/.hermes}`` — the cockpit's own secret/state dir.

    The job-workspace file readers must never expose this tree: it holds the
    provider keys (``.env``), the cockpit bearer token, memory, and job state.
    The cockpit's contract is that the client holds *only* the bearer token —
    a workspace pointed at (or above) ``~/.hermes`` must not turn the readers
    into an exfiltration path for those secrets.
    """
    import os
    from pathlib import Path

    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base).resolve()


def _within(path: Path, base: Path) -> bool:
    """True if ``path`` is ``base`` or sits under it (both already resolved)."""
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def job_files_changed(req: Request) -> JsonResponse:
    """Files changed in a job's workspace (contract §6) — read-only.

    The Job Detail "files changed" list. Reuses the same git ``--numstat``
    machinery as ``/diff`` but omits the patch body. Honest empty when the job
    has no git workspace (orchestrator jobs don't carry one).
    """
    job_id = req.path_params.get("id", "")
    kind, obj = _resolve_job(job_id)
    if obj is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    workspace = _job_workspace(kind, obj)
    if not workspace:
        return JsonResponse(200, {"files": []})
    base = (dict(getattr(obj, "metadata", None) or {})).get("base_branch")
    return JsonResponse(200, {"files": _git_diff(workspace, base)["files"]})


def _read_validation_results(workspace: str) -> Optional[dict[str, Any]]:
    """The persisted ``validation/results.json`` for a workspace, or ``None``."""
    import json
    from pathlib import Path

    path = Path(workspace) / "validation" / "results.json"
    try:
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                return loaded
    except Exception:  # pragma: no cover - defensive (corrupt/unreadable)
        pass
    return None


def _read_validation_overrides(workspace: str) -> dict[str, Any]:
    """Persisted gate overrides for a workspace (``{}`` when none)."""
    import json
    from pathlib import Path

    path = Path(workspace) / "validation" / "overrides.json"
    try:
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                return loaded
    except Exception:  # pragma: no cover - defensive
        pass
    return {}


def job_validation(req: Request) -> JsonResponse:
    """Latest verification-gate results for a job (contract §7) — read-only.

    The read companion to ``POST .../validate``: returns the persisted
    ``<workspace>/validation/results.json`` projected into the same snapshot
    shape, **without** re-running the gates, with any recorded gate overrides
    applied. Honest empty gates when the job hasn't been validated yet.
    """
    job_id = req.path_params.get("id", "")
    kind, obj = _resolve_job(job_id)
    if obj is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    from . import contract

    workspace = _job_workspace(kind, obj)
    report = _read_validation_results(workspace) if workspace else None
    overrides = _read_validation_overrides(workspace) if workspace else {}
    return JsonResponse(200, contract.validation_snapshot(report, overrides=overrides))


def job_revalidate(req: Request) -> JsonResponse:
    """Re-run verification gates for a job (contract §7).

    Semantically identical to ``POST .../validate`` — a re-run that persists a
    fresh ``validation/results.json`` and returns the new snapshot. Provided as
    the contract's explicit "revalidate" verb.
    """
    return job_validate(req)


def job_override(req: Request) -> JsonResponse:
    """Override non-critical failed validation gates with a note (contract §7).

    Records an owner override for the named ``gate_ids`` (each must be
    ``override_allowed`` — never a critical gate) so they no longer block
    publish. Requires a non-empty ``note`` (policy: override_requires_note).
    Persists to ``<workspace>/validation/overrides.json`` and returns the updated
    snapshot with ``publish_allowed`` recomputed. ``403`` if any gate is critical.
    """
    job_id = req.path_params.get("id", "")
    kind, obj = _resolve_job(job_id)
    if obj is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    workspace = _job_workspace(kind, obj)
    if not workspace:
        return JsonResponse(409, {"error": "job has no workspace to override"})
    gate_ids = [str(g).strip() for g in (req.body.get("gate_ids") or []) if str(g).strip()]
    note = str(req.body.get("note", "")).strip()
    if not gate_ids:
        return JsonResponse(400, {"error": "gate_ids is required"})
    if not note:
        return JsonResponse(
            403, {"error": "override requires a note (policy: override_requires_note)"}
        )
    from . import contract

    report = _read_validation_results(workspace)
    if report is None:
        return JsonResponse(
            409, {"error": "no validation results to override; run validate first"}
        )
    by_id = {g["id"]: g for g in contract.validation_snapshot(report)["gates"]}
    for gid in gate_ids:
        gate = by_id.get(gid)
        if gate is None:
            return JsonResponse(404, {"error": f"unknown gate: {gid}"})
        if not gate.get("override_allowed", False):
            return JsonResponse(403, {"error": f"gate is critical and not overridable: {gid}"})

    import json
    from pathlib import Path

    overrides = _read_validation_overrides(workspace)
    ts = _now_iso()
    for gid in gate_ids:
        overrides[gid] = {"note": note, "ts": ts}
    try:
        path = Path(workspace) / "validation" / "overrides.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(overrides, indent=2, sort_keys=True), encoding="utf-8")
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": f"failed to record override: {exc}"})
    return JsonResponse(200, contract.validation_snapshot(report, overrides=overrides))


def job_tree(req: Request) -> JsonResponse:
    """One directory level inside a job's workspace (contract §6) — read-only.

    Path-sandboxed to the workspace root: a ``path`` that escapes it is a 400,
    never followed. Honest empty when the job has no workspace. Lists name,
    kind (file/dir), size, and mtime for each child.

    Two guards beyond the traversal sandbox (the workspace root is unvalidated
    client input from job dispatch): disabled on a non-loopback cockpit, and
    refuses any path resolving into ``~/.hermes`` (the cockpit's own secrets).
    """
    job_id = req.path_params.get("id", "")
    kind, obj = _resolve_job(job_id)
    if obj is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    if _ALLOW_REMOTE_EXECUTE:
        return JsonResponse(
            403, {"error": "workspace browsing is disabled on a non-loopback cockpit"}
        )
    workspace = _job_workspace(kind, obj)
    rel = (req.query.get("path") or ".").strip() or "."
    if not workspace:
        return JsonResponse(200, {"path": rel, "entries": []})
    root, target = _safe_workspace_target(workspace, rel)
    if target is None:
        return JsonResponse(400, {"error": "path escapes the job workspace"})
    if _within(target, _hermes_state_dir()):
        return JsonResponse(
            403, {"error": "refusing to browse the Hermes state directory (~/.hermes)"}
        )
    if not root.is_dir():
        return JsonResponse(200, {"path": rel, "entries": []})
    if not target.is_dir():
        return JsonResponse(404, {"error": f"not a directory: {rel}"})
    try:
        children = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except OSError as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": f"listing failed: {exc}"})
    entries: list[dict[str, Any]] = []
    for child in children:
        is_dir = child.is_dir()
        size: Optional[int] = None
        mtime: Optional[str] = None
        try:
            st = child.stat()
            size = None if is_dir else int(st.st_size)
            mtime = datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat()
        except OSError:  # pragma: no cover - defensive (race/permission)
            pass
        entries.append({
            "name": child.name,
            "kind": "dir" if is_dir else "file",
            "size": size,
            "mtime": mtime,
        })
    rel_out = "." if target == root else str(target.relative_to(root))
    return JsonResponse(200, {"path": rel_out, "entries": entries})


def job_file(req: Request) -> JsonResponse:
    """Single-file preview inside a job's workspace (contract §6) — read-only.

    Path-sandboxed like ``/tree``. Caps at 1 MB; a larger or binary (non-UTF-8)
    file returns ``truncated=true`` with ``content=null`` — a 200, per contract,
    not an error. Never writes.

    Two guards beyond the traversal sandbox (the workspace root is unvalidated
    client input from job dispatch): disabled on a non-loopback cockpit, and
    refuses any path resolving into ``~/.hermes`` (so the cockpit's own
    ``.env`` / token can't be exfiltrated through a job workspace).
    """
    job_id = req.path_params.get("id", "")
    kind, obj = _resolve_job(job_id)
    if obj is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    if _ALLOW_REMOTE_EXECUTE:
        return JsonResponse(
            403, {"error": "file preview is disabled on a non-loopback cockpit"}
        )
    workspace = _job_workspace(kind, obj)
    rel = (req.query.get("path") or "").strip()
    if not rel:
        return JsonResponse(400, {"error": "path query parameter required"})
    if not workspace:
        return JsonResponse(404, {"error": "job has no workspace"})
    root, target = _safe_workspace_target(workspace, rel)
    if target is None:
        return JsonResponse(400, {"error": "path escapes the job workspace"})
    if _within(target, _hermes_state_dir()):
        return JsonResponse(
            403,
            {"error": "refusing to read inside the Hermes state directory (~/.hermes)"},
        )
    if not target.is_file():
        return JsonResponse(404, {"error": f"not a file: {rel}"})
    try:
        size = int(target.stat().st_size)
        with target.open("rb") as fh:
            raw = fh.read(_JOB_FILE_MAX_BYTES + 1)
    except OSError as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": f"read failed: {exc}"})
    rel_out = str(target.relative_to(root))
    if size > _JOB_FILE_MAX_BYTES:
        return JsonResponse(200, {
            "path": rel_out, "size": size, "truncated": True,
            "content": None, "encoding": "utf-8",
        })
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        return JsonResponse(200, {
            "path": rel_out, "size": size, "truncated": True,
            "content": None, "encoding": "utf-8",
        })
    return JsonResponse(200, {
        "path": rel_out, "size": size, "truncated": False,
        "content": content, "encoding": "utf-8",
    })


def templates_list(_req: Request) -> JsonResponse:
    """Owner-defined prompt templates (contract §3) — read-only.

    Templates live at ``${HERMES_HOME:-~/.hermes}/cockpit/templates.json`` as a
    list of ``{"id","title","body"}`` objects (or ``{"templates": [...]}``).
    Honest-empty list when the file is absent/unreadable — the cockpit then
    falls back to its bundled defaults. Malformed entries are skipped, never
    guessed or fabricated.
    """
    import json
    import os
    from pathlib import Path

    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    path = Path(base) / "cockpit" / "templates.json"
    items: list[dict[str, Any]] = []
    try:
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            raw = loaded.get("templates") if isinstance(loaded, dict) else loaded
            for t in raw or []:
                if not isinstance(t, dict):
                    continue
                tid = str(t.get("id", "") or "").strip()
                title = str(t.get("title", "") or "").strip()
                body = str(t.get("body", "") or "")
                if tid and title and body:
                    items.append({"id": tid, "title": title, "body": body})
    except Exception:  # pragma: no cover - defensive (corrupt/unreadable)
        items = []
    return JsonResponse(200, {"templates": items})


def _git_commits(workspace: str, base: Optional[str]) -> list[dict[str, Any]]:
    """``git log base..HEAD`` subjects in ``workspace``; honest-empty on failure."""
    import subprocess
    from pathlib import Path

    ws = Path(workspace)
    if not ws.is_dir():
        return []
    rng = f"{base}..HEAD" if base else "HEAD"
    try:
        out = subprocess.run(
            ["git", "-C", str(ws), "log", "--pretty=format:%h%x09%s", rng],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if out.returncode != 0:
            return []
    except Exception:  # pragma: no cover - defensive (git missing / bad range)
        return []
    commits: list[dict[str, Any]] = []
    for line in out.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            commits.append({"sha": parts[0], "subject": parts[1]})
    return commits


def _publish_preview_payload(kind: Optional[str], obj: Any) -> dict[str, Any]:
    """Derive the read-only publish preview from git in the job's workspace.

    remote/branch/base, the commits on the branch vs its base, and a default PR
    title/body — no network, no writes. Honest nulls/empty without a git
    workspace or commits ahead of base. Shared by ``job_publish_preview`` and the
    ``approval_required`` staging of ``job_publish`` so they can't drift.
    """
    md = dict(getattr(obj, "metadata", None) or {})
    workspace = str(getattr(obj, "repo_root", "") or "") if kind == "queue" else ""
    if not workspace:
        return {
            "remote": None, "branch": None, "base": None, "commits": [],
            "default_title": None, "default_body": None, "existing_pr_url": None,
        }

    def _git(args: list[str]) -> str:
        import subprocess
        try:
            out = subprocess.run(
                ["git", "-C", workspace, *args],
                capture_output=True, text=True, timeout=20,
            )
            return out.stdout.strip() if out.returncode == 0 else ""
        except Exception:  # pragma: no cover - defensive
            return ""

    branch = md.get("branch") or _git(["rev-parse", "--abbrev-ref", "HEAD"]) or None
    base = md.get("base_branch") or "main"
    commits = _git_commits(workspace, base)
    default_title = commits[0]["subject"] if commits else None
    default_body = None
    if commits:
        changes = "\n".join(f"- {c['subject']}" for c in commits)
        default_body = f"## Summary\n\n## Changes\n{changes}\n"
    return {
        "remote": md.get("remote") or "origin",
        "branch": branch,
        "base": base,
        "commits": commits,
        "default_title": default_title,
        "default_body": default_body,
        "existing_pr_url": None,
    }


def job_publish_preview(req: Request) -> JsonResponse:
    """Read-only preview of what publishing this job would open (contract §8).

    No network, no writes; honest nulls/empty when the job has no git workspace.
    The actual ``POST .../publish`` (open PR) is a separate, owner-gated route.
    """
    job_id = req.path_params.get("id", "")
    kind, obj = _resolve_job(job_id)
    if obj is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    return JsonResponse(200, _publish_preview_payload(kind, obj))


def _publish_repo_slug(workspace: str) -> tuple[Optional[str], Optional[str]]:
    """``(owner, repo)`` parsed from the job workspace's git remote, or ``(None, None)``."""
    try:
        from pathlib import Path

        from hermes_cli import github_publisher as _gp

        info = _gp.get_repo_info(Path(workspace))
        return info.owner, info.repo
    except Exception:  # pragma: no cover - not a git checkout / no remote
        return None, None


def _open_pull_request(  # pragma: no cover - network; validated with a real PAT
    client: Any, owner: str, repo: str, branch: str, base: str,
    title: str, body: str, draft: bool,
) -> JsonResponse:
    """Open (or report an existing) PR for ``branch``. Network — not unit-tested."""
    existing = client.open_pull_for_head(owner, repo, branch)
    if existing:
        return JsonResponse(409, {"error": "pr_already_exists", "pr_url": existing})
    result = client.create_pull_request(
        owner, repo, title=title, head=branch, base=base, body=body, draft=draft)
    if not result.get("success"):
        return JsonResponse(502, {
            "error": result.get("error", "github_error"),
            "message": result.get("message", "failed to open pull request"),
        })
    pr = result.get("payload") or {}
    return JsonResponse(200, {
        "pr_url": pr.get("html_url"),
        "pr_number": pr.get("number"),
        "branch": branch,
        "remote": "origin",
        "state": pr.get("state", "open"),
        "is_draft": bool(pr.get("draft", draft)),
    })


def job_publish(req: Request) -> JsonResponse:
    """Open a GitHub PR for a job's branch (contract §8) — owner-gated.

    Double-gated like ``job_approve``: refused on a non-loopback cockpit, and
    requires the exact owner phrase. Without the phrase it returns ``200`` with
    ``status: "approval_required"`` and the publish preview (no GitHub call).
    With the phrase it opens a **real** PR via the GitHub REST API using
    ``GITHUB_PERSONAL_ACCESS_TOKEN`` — ``403 github_not_configured`` when that
    token is absent, ``409 pr_already_exists`` (carrying ``pr_url``) when an open
    PR already targets the branch.

    The cockpit opens the PR for a branch already pushed to the remote (the
    worker/CI pushes; the cockpit publishes). It does **not** run ``git push``
    itself — the repo deliberately keeps the PAT out of ``git push`` (see
    ``hermes_cli/github_publisher``).
    """
    job_id = req.path_params.get("id", "")
    authorization = str(req.body.get("authorization", "")).strip()
    kind, obj = _resolve_job(job_id)
    if obj is None:
        return JsonResponse(404, {"error": f"unknown job: {job_id}"})
    if _ALLOW_REMOTE_EXECUTE:
        return JsonResponse(
            403,
            {"error": "publishing is disabled on a non-loopback cockpit; run the "
             "runtime locally (loopback) to open a PR"},
        )
    workspace = str(getattr(obj, "repo_root", "") or "") if kind == "queue" else ""
    if not workspace:
        return JsonResponse(409, {"error": "job has no workspace to publish"})

    preview = _publish_preview_payload(kind, obj)
    from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

    if authorization != AUTHORIZATION_PHRASE:
        return JsonResponse(200, {
            "status": "approval_required",
            "preview": preview,
            "authorization_required": True,
            "authorization_hint": f"send authorization exactly: {AUTHORIZATION_PHRASE!r}",
        })

    # --- past the owner gate: open a real PR (requires a configured PAT) ------
    try:
        from plugins.github_assistant.client import GithubClient
    except Exception as exc:  # pragma: no cover - import/runtime guard
        return JsonResponse(500, {"error": f"github client unavailable: {exc}"})
    client = GithubClient()
    if not client.has_token():
        return JsonResponse(403, {
            "error": "github_not_configured",
            "message": "set GITHUB_PERSONAL_ACCESS_TOKEN in ~/.hermes/.env to publish",
        })

    branch = preview.get("branch")
    if not branch:
        return JsonResponse(409, {"error": "job branch is not resolvable; nothing to publish"})
    owner, repo = _publish_repo_slug(workspace)
    if not owner or not repo:  # pragma: no cover - reached only past the token gate
        return JsonResponse(409, {"error": "could not resolve owner/repo from the job's git remote"})
    title = str(req.body.get("title") or preview.get("default_title") or branch)
    body = str(req.body.get("body") or preview.get("default_body") or "")
    base = str(req.body.get("base") or preview.get("base") or "main")
    draft = req.body.get("draft") is not False  # only an explicit JSON false → non-draft
    return _open_pull_request(client, owner, repo, branch, base, title, body, draft)


# ---------------------------------------------------------------------------
# Autonomy (Owner High-Autonomy Coding mode)
# ---------------------------------------------------------------------------
#
# The autonomy handler group (the FU-12 owner-gate cluster) lives in the
# sibling module ``handlers_autonomy`` and is re-exported here so every
# existing reference — notably ``server.py``'s route table calling
# ``h.autonomy_get`` / ``h.autonomy_set`` / ``h.autonomy_decisions`` — keeps
# resolving through ``handlers`` unchanged. Behaviour is identical; this is a
# physical relocation, not a route or signature change. (The import sits at
# the bottom of the module — see the re-export just before ``__all__`` — so
# ``Request`` / ``JsonResponse`` are already defined when it runs.)


# ---------------------------------------------------------------------------
# Approvals (persistent JARVIS proposal queue; owner phrase preserved)
# ---------------------------------------------------------------------------


def _proposals_path():
    import os as _os

    base = _os.environ.get("HERMES_HOME") or _os.path.expanduser("~/.hermes")
    from pathlib import Path as _Path

    return _Path(base) / "jarvis_prime" / "proposals.jsonl"


def _proposal_id(prop: dict[str, Any]) -> str:
    import hashlib

    raw = (
        f"{prop.get('kind', '')}|"
        f"{prop.get('target_path', '')}|"
        f"{prop.get('created_at', '')}"
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def _load_proposals() -> list[dict[str, Any]]:
    import json as _json

    path = _proposals_path()
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(_json.loads(line))
        except _json.JSONDecodeError:
            continue
    return out


def _save_proposals(items: list[dict[str, Any]]) -> None:
    import json as _json
    import os as _os

    path = _proposals_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    tmp.write_text(
        "".join(_json.dumps(i, default=str) + "\n" for i in items), encoding="utf-8"
    )
    _os.replace(tmp, path)


def approvals_list(_req: Request) -> JsonResponse:
    """The owner-approval queue as canonical ``ApprovalCard``s.

    Source today is the real JARVIS self-update proposal queue; future
    destructive-command approvals join the same card shape.
    """
    from . import contract

    cards = [
        contract.approval_card(p, approval_id=_proposal_id(p))
        for p in _load_proposals()
    ]
    return JsonResponse(200, {"approvals": cards})


def proposals_list(_req: Request) -> JsonResponse:
    """Self-update-native view of the proposal queue (proposal shape)."""
    from . import contract

    items = [
        contract.proposal_view(p, proposal_id=_proposal_id(p))
        for p in _load_proposals()
    ]
    return JsonResponse(200, {"proposals": items})


def skills_list(_req: Request) -> JsonResponse:
    """The gateway's real installed skills (read-only).

    Backed by the live skill scanner; an honest empty list when none are
    installed (or the scanner is unavailable) — never fabricated.
    """
    skills: list[dict[str, Any]] = []
    try:
        from agent.skill_commands import scan_skill_commands

        from . import contract

        for command, info in sorted(scan_skill_commands().items()):
            skills.append(contract.skill_entry(command, info))
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"skills": [], "error": str(exc)})
    return JsonResponse(200, {"skills": skills})


def navigation_list(req: Request) -> JsonResponse:
    """Recent HyperAgent navigation decisions (the pre-dispatch "where to look"),
    read from the orchestrator job ledger. Honest empty when no ``/orchestrate``
    job has navigated yet.

    Optional ``?job=<id>`` filters to a single job's decisions *before* the
    ``limit`` truncation — so the app's job-detail view never loses an older
    job's decision to the global recency cap.
    """
    limit = int(req.query.get("limit", "50"))
    job_filter = (req.query.get("job") or "").strip() or None
    items: list[dict[str, Any]] = []
    try:
        from hermes_cli import orchestrator as orch

        from . import contract

        ledger = orch.get_ledger() or {}
        for job_id, entries in ledger.items():
            if job_filter is not None and job_id != job_filter:
                continue
            for entry in entries or []:
                if (
                    isinstance(entry, dict)
                    and entry.get("kind") == "navigation_decision"
                ):
                    items.append(contract.navigation_view(entry, job_id=job_id))
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        items = items[:limit]
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"navigations": [], "error": str(exc)})
    return JsonResponse(200, {"navigations": items})


# ---------------------------------------------------------------------------
# GraphRAG — related files/sources/decisions, query modes (cognition plane)
# ---------------------------------------------------------------------------


def _graph_repo_root():
    import os
    from pathlib import Path

    return Path(os.environ.get("HERMES_REPO_ROOT") or os.getcwd())


def _load_graph():
    """Load the cached knowledge graph, building it on first use.

    The graph is an additive cache (``~/.hermes/jarvis_prime/graph/``) rebuilt
    from the repo + local stores; building is read-only over those sources.
    """

    from hermes_cli.jarvis_prime.graphrag import GraphStore, build_and_save

    store = GraphStore()
    graph = store.load()
    if not graph.nodes:
        graph, _ = build_and_save(_graph_repo_root(), store=store)
    return graph


def graph_related(req: Request) -> JsonResponse:
    """Related files / sources / decisions for an entity. Accepts ``node`` (a
    graph node id or key), or one of ``job_id`` / ``memory_id`` /
    ``evidence_id`` which are resolved to a node. Honest empty when the entity
    is not in the graph yet.
    """
    try:
        from hermes_cli.jarvis_prime.graphrag import find_entity_node, related_items

        from . import contract

        graph = _load_graph()
        q = req.query
        explicit = q.get("node", "")
        key = (
            q.get("job_id")
            or (f"memory:{q['memory_id']}" if q.get("memory_id") else "")
            or q.get("evidence_id")
            or explicit
        )
        node_id_ = find_entity_node(graph, node=explicit or None, key=key or None)
        if not node_id_:
            return JsonResponse(200, contract.graph_related_view([], node=key))
        items = related_items(graph, node_id_, limit=int(q.get("limit", "30")))
        return JsonResponse(
            200, contract.graph_related_view(items, node=node_id_, origin=key)
        )
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"node": "", "related": [], "error": str(exc)})


def graph_query(req: Request) -> JsonResponse:
    """Run a GraphRAG query (``mode`` = local | global | coding)."""
    try:
        from hermes_cli.jarvis_prime.graphrag import (
            coding_query,
            global_query,
            local_query,
        )

        from . import contract

        graph = _load_graph()
        mode = req.query.get("mode", "local")
        question = req.query.get("q", "")
        if mode == "global":
            answer = global_query(graph, question)
        elif mode == "coding":
            answer = coding_query(graph, question)
        else:
            answer = local_query(graph, question)
        return JsonResponse(200, contract.graph_answer_view(answer.to_dict()))
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"mode": "", "nodes": [], "edges": [], "error": str(exc)})


def graph_build(_req: Request) -> JsonResponse:
    """Rebuild + persist the knowledge-graph cache. Read-only over the repo and
    local stores (no repo edits, no network); not an owner-gated action.
    """
    try:
        from hermes_cli.jarvis_prime.graphrag import GraphStore, build_and_save

        graph, path = build_and_save(_graph_repo_root(), store=GraphStore())
        return JsonResponse(200, {"saved": str(path), **graph.stats()})
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})


def second_brain_status(_req: Request) -> JsonResponse:
    """Second Brain availability + non-secret settings (read-only).

    Reports whether retrieval is enabled (``MUSE_SECOND_BRAIN``) and the module
    is importable, plus the resolved backend and non-secret connection fields
    (never the password). Defensive — never raises.
    """
    try:
        from hermes_cli.jarvis_prime import second_brain_bridge as sbb

        available = sbb.is_available()
        out: dict[str, Any] = {"enabled": sbb.enabled(), "available": available}
        if available:
            try:
                from second_brain.knowledge import load_settings

                s = load_settings()
                out["settings"] = {
                    "backend": s.backend,
                    "postgres": {
                        "host": s.postgres.host,
                        "port": s.postgres.port,
                        "database": s.postgres.database,
                        "user": s.postgres.user,
                    },
                    "embedding": {
                        "provider": s.embedding.provider,
                        "model": s.embedding.model,
                        "dimension": s.embedding.dimension,
                    },
                }
            except Exception as exc:  # pragma: no cover - defensive
                out["settings_error"] = str(exc)
        return JsonResponse(200, out)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"enabled": False, "available": False, "error": str(exc)})


def second_brain_retrieve(req: Request) -> JsonResponse:
    """Retrieve fused Second Brain context for ``q`` (read-only).

    Requires ``MUSE_SECOND_BRAIN`` enabled + the module available; otherwise
    returns an honest payload (never an exception). Mirrors the bridge's
    augment-never-replace contract — this is a read-only retrieval surface, no
    writes (ingestion stays CLI-only and owner-gated).
    """
    from hermes_cli.jarvis_prime import second_brain_bridge as sbb

    query = req.query.get("q", "").strip()
    if not query:
        return JsonResponse(400, {"error": "missing q"})
    if not sbb.enabled():
        return JsonResponse(
            200,
            {
                "enabled": False,
                "blocks": 0,
                "text": "",
                "hint": "set MUSE_SECOND_BRAIN=1 on the gateway",
            },
        )
    if not sbb.is_available():
        return JsonResponse(200, {"enabled": True, "available": False, "blocks": 0, "text": ""})
    raw = req.query.get("top_k", "")
    try:
        top_k = int(raw) if raw else None
    except ValueError:
        top_k = None
    ctx = sbb.retrieve_optional(query, top_k=top_k)
    if ctx is None:
        return JsonResponse(
            200,
            {"enabled": True, "available": True, "backend_ready": False, "blocks": 0, "text": ""},
        )
    return JsonResponse(
        200,
        {
            "enabled": True,
            "available": True,
            "backend_ready": True,
            "blocks": ctx.block_count,
            "text": ctx.text,
            "source": ctx.source,
        },
    )


def forge_leaderboard(_req: Request) -> JsonResponse:
    """The Forge championship view (read-only): Glicko-2 standings, MAP-Elites
    coverage/QD score, and the candidate count.

    Surfaces the CLI-only ``jarvis_prime forge`` tournament system over the
    gateway. Read-only over the local registry/ledger; honest-empty (not an
    error) before anything has competed.
    """
    try:
        from hermes_cli.jarvis_prime.forge.leaderboard import standings
        from hermes_cli.jarvis_prime.forge.map_elites import ElitesGrid
        from hermes_cli.jarvis_prime.forge.registry import CandidateRegistry
        from hermes_cli.jarvis_prime.forge.tournament import RatingBook

        registry = CandidateRegistry()
        grid = ElitesGrid()
        return JsonResponse(
            200,
            {
                "standings": [s.to_dict() for s in standings(RatingBook(), registry)],
                "candidates": len(list(registry.all())),
                "coverage": round(grid.coverage(), 4),
                "qd_score": round(grid.qd_score(), 4),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(
            200, {"standings": [], "candidates": 0, "coverage": 0.0, "qd_score": 0.0, "error": str(exc)}
        )


def federation_status(_req: Request) -> JsonResponse:
    """Federation status (read-only, **public fields only**): this node's public
    identity and the known peer list.

    Security: ``NodeIdentity.to_dict()`` exposes only public material
    (node_id, display_name, algo, public_key_hex). Private key / HMAC secret are
    stored separately on disk and **never** leave the machine — they are not in
    this payload. Honest-empty before ``federation identity init``.
    """
    try:
        from hermes_cli.jarvis_prime.federation.attestation import FederationRegistry
        from hermes_cli.jarvis_prime.federation.identity import load_identity

        identity = load_identity()
        registry = FederationRegistry()
        peers = [p.to_dict() for p in registry.peers()]
        return JsonResponse(
            200,
            {
                "identity": identity.to_dict() if identity is not None else None,
                "peers": peers,
                "peer_count": len(peers),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(
            200, {"identity": None, "peers": [], "peer_count": 0, "error": str(exc)}
        )


def council_dispatch(req: Request) -> JsonResponse:
    """Route a request to the AOS Enterprise Council (read-only). ``?q=<request>``.

    Returns the engaged active council + matching domain specialists with their
    roles, required outputs, verification, and owner gates. Deterministic
    registry routing — no model calls, no writes.
    """
    query = req.query.get("q", "").strip()
    if not query:
        return JsonResponse(400, {"error": "missing q"})
    try:
        from hermes_cli.jarvis_prime.aos_council import dispatch
        from hermes_cli.jarvis_prime.effort_class import classify_effort_for_request

        # Deterministically stamp the request's smallest-sufficient effort class
        # (offline mode-classify → router; no model call) and thread it in. This
        # is a no-op unless the default-OFF MUSE_EFFORT_CAP flag is enabled: with
        # the flag off, dispatch ignores effort_class and the routed council is
        # byte-for-byte identical to before; when enabled it caps a real turn.
        effort_class = classify_effort_for_request(query)
        return JsonResponse(200, dispatch(query, effort_class=effort_class).to_dict())
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(
            200,
            {
                "request": query,
                "council": [],
                "specialists": [],
                "engaged_count": 0,
                "owner_gated": False,
                "error": str(exc),
            },
        )


# Ledger timeline (orchestrator event ledger) — the mobile "Activity" surface
# ---------------------------------------------------------------------------


def ledger_timeline(req: Request) -> JsonResponse:
    """Redacted, filterable timeline over the orchestrator event ledger.

    Reads every job's ``~/.hermes/jobs/<id>/ledger.jsonl`` via
    ``orchestrator_ledger.all_ledgers`` and projects each entry into a
    canonical, secret-scrubbed ``LedgerEvent``. Supports query filters:
    ``job``, ``risk``, ``worker``, ``category`` (or ``kind``), ``file``
    (substring), ``since``/``until`` (ISO-8601 prefix compare), ``limit``
    (default 100), ``order`` (``desc`` newest-first default / ``asc``).
    Honest empty list when nothing has run yet.
    """
    q = req.query
    limit = _int(q.get("limit"), 100)
    order = (q.get("order") or "desc").lower()
    want_job = q.get("job")
    want_risk = (q.get("risk") or "").upper() or None
    want_worker = q.get("worker")
    want_cat = (q.get("category") or q.get("kind") or "").upper() or None
    want_file = (q.get("file") or "").lower() or None
    since = q.get("since")
    until = q.get("until")

    events: list[dict[str, Any]] = []
    try:
        from hermes_cli import orchestrator_ledger as ol

        from . import contract

        ledgers = ol.all_ledgers()
        for job_id, entries in ledgers.items():
            if want_job and job_id != want_job:
                continue
            for index, entry in enumerate(entries or []):
                if not isinstance(entry, dict):
                    continue
                ev = contract.ledger_event(entry, job_id=job_id, index=index)
                if want_risk and ev["risk_tier"] != want_risk:
                    continue
                if want_cat and ev["category"] != want_cat and ev["kind"].upper() != want_cat:
                    continue
                if want_worker and (ev["worker"] or "") != want_worker and want_worker.lower() not in (ev["worker"] or "").lower():
                    continue
                if want_file and not any(want_file in f.lower() for f in ev["files"]):
                    continue
                ts = ev["timestamp"]
                if ts and since and _before_bound(ts, since):
                    continue
                if ts and until and _after_bound(ts, until):
                    continue
                events.append(ev)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"events": [], "error": str(exc)})

    events.sort(key=lambda e: (e.get("timestamp") or "", e.get("id") or ""), reverse=(order != "asc"))
    if limit > 0:
        events = events[:limit]
    return JsonResponse(200, {"events": events})


def ledger_event_detail(req: Request) -> JsonResponse:
    """Full redacted detail for one timeline event (``{job}/{index}``)."""
    job_id = req.path_params.get("job", "")
    index = _int(req.path_params.get("index"), -1)
    if not job_id or index < 0:
        return JsonResponse(400, {"error": "job and integer index are required"})
    try:
        from hermes_cli import orchestrator_ledger as ol

        from . import contract

        entries = ol.read(job_id)
        if index >= len(entries):
            return JsonResponse(404, {"error": f"no ledger event {job_id}:{index}"})
        return JsonResponse(200, contract.ledger_event_detail(entries[index], job_id=job_id, index=index))
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})


def ledger_rollback_request(req: Request) -> JsonResponse:
    """Raise an **owner-gated** rollback request for a timeline event.

    This never executes a rollback. It enqueues a proposal into the same
    owner-approval queue the Approvals screen reads (``proposals.jsonl``),
    so the rollback must still be approved with the exact owner phrase via
    ``POST /v1/cockpit/approvals/{id}`` before anything happens. Returns the
    canonical ``ApprovalCard`` for the new request.
    """
    job_id = req.path_params.get("job", "")
    index = _int(req.path_params.get("index"), -1)
    if not job_id or index < 0:
        return JsonResponse(400, {"error": "job and integer index are required"})
    reason = str(req.body.get("reason", "")).strip()

    # Confirm the event exists (and capture a short label) before queuing.
    try:
        from hermes_cli import orchestrator_ledger as ol

        from . import contract

        entries = ol.read(job_id)
        if index >= len(entries):
            return JsonResponse(404, {"error": f"no ledger event {job_id}:{index}"})
        ev = contract.ledger_event(entries[index], job_id=job_id, index=index)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})

    proposal = {
        "kind": "rollback",
        "target_path": ev["id"],
        "rationale": reason or f"Rollback requested for {ev['kind']} on job {job_id}",
        "risk_class": "RC3",
        "status": "proposed",
        "requires_owner_approval": True,
        "created_at": _now_iso(),
        "source": "cockpit-ledger",
    }
    items = _load_proposals()
    items.append(proposal)
    _save_proposals(items)

    from . import contract

    approval_id = _proposal_id(proposal)

    # Best-effort: enqueue this newly-created pending approval and emit a
    # bounded "approval pending" event so a phone tailing the SSE stream is
    # notified. The summary is the short rationale (no diff/secret). This must
    # never break proposal creation, so any failure is swallowed.
    try:
        import time as _time

        from hermes_cli.notifications import ApprovalNotification

        from . import notify

        notify.enqueue_and_notify(
            ApprovalNotification(
                approval_id=approval_id,
                job_id=job_id or "",
                summary=str(proposal.get("rationale", "") or ""),
                risk_tier=contract.approval_card_tier(proposal.get("risk_class")),
                created_at=_time.time(),
            )
        )
    except Exception:  # pragma: no cover - notify is best-effort
        pass

    return JsonResponse(
        201, contract.approval_card(proposal, approval_id=approval_id)
    )


def _int(value: Any, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _date_only(value: str) -> bool:
    """True for a bare ``YYYY-MM-DD`` (the filter panel's date fields)."""
    return len(value) == 10 and value[4] == "-" and value[7] == "-"


def _before_bound(ts: str, since: str) -> bool:
    """True when ``ts`` is before the lower bound. A date-only ``since`` is
    inclusive from the start of that calendar day."""
    return ts[:10] < since if _date_only(since) else ts < since


def _after_bound(ts: str, until: str) -> bool:
    """True when ``ts`` is past the upper bound. A date-only ``until`` is
    inclusive of the *whole* day, so ``until=2026-06-02`` keeps events like
    ``2026-06-02T12:05:00+00:00`` (a plain ``ts > until`` would drop them —
    the longer ISO string sorts greater than the bare date)."""
    return ts[:10] > until if _date_only(until) else ts > until


def approvals_decide(req: Request) -> JsonResponse:
    """Approve/reject a proposal. Approve requires the exact owner phrase."""
    proposal_id = req.path_params.get("id", "")
    decision = str(req.body.get("decision", "")).lower().strip()
    if decision not in ("approve", "reject"):
        return JsonResponse(400, {"error": "decision must be 'approve' or 'reject'"})

    from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

    if decision == "approve":
        phrase = str(req.body.get("authorization", "")).strip()
        if phrase != AUTHORIZATION_PHRASE:
            # Owner-gate contract: exact phrase required. Never bypass.
            return JsonResponse(
                403,
                {
                    "error": "owner authorization required",
                    "hint": f"reply exactly: {AUTHORIZATION_PHRASE!r}",
                },
            )

    items = _load_proposals()
    matched = None
    for p in items:
        if _proposal_id(p) == proposal_id:
            matched = p
            break
    if matched is None:
        return JsonResponse(404, {"error": f"unknown proposal: {proposal_id}"})

    # Sprint 9 race rules: a proposal is decided once. A duplicate decide
    # returns the existing decision (idempotent) instead of re-deciding, and
    # an expired/superseded proposal rejects the late decision. Expiry and
    # supersession only fire when a proposal carries those fields, so for
    # today's proposals (which don't) the only behaviour change is that a
    # repeat decide is now idempotent rather than silently re-mutating.
    import time

    from hermes_cli.approval_rules import (
        ApprovalRecord,
        ApprovalState,
        DecisionResult,
        resolve_decision,
    )

    _state = {
        "approved": ApprovalState.GRANTED,
        "rejected": ApprovalState.REJECTED,
    }.get(str(matched.get("status", "")).lower(), ApprovalState.PENDING)
    _exp = matched.get("expires_at")
    record = ApprovalRecord(
        approval_id=proposal_id,
        state=_state,
        expires_at=_exp if isinstance(_exp, (int, float)) else None,
        decided_at=0.0 if matched.get("resolved_at") else None,
        superseded_by=matched.get("superseded_by"),
    )
    outcome = resolve_decision(record, approve=(decision == "approve"), now=time.time())
    if outcome.result is DecisionResult.ALREADY_DECIDED:
        return JsonResponse(
            200,
            {"id": proposal_id, "status": matched.get("status"), "idempotent": True},
        )
    if outcome.result in (DecisionResult.EXPIRED, DecisionResult.SUPERSEDED):
        return JsonResponse(
            409,
            {"error": outcome.result.value, "detail": outcome.detail, "id": proposal_id},
        )

    matched["status"] = "approved" if decision == "approve" else "rejected"
    matched["resolved_at"] = _now_iso()
    matched["owner_decision_note"] = f"{decision} via cockpit"
    _save_proposals(items)

    # Best-effort: clear the now-decided proposal from the shared pending-approval
    # queue and emit a bounded "approval decided" event, so a phone tailing the
    # SSE stream stops showing "approval pending" forever. This runs only after a
    # decision actually succeeds (not the idempotent/expired/superseded returns
    # above), carries no secret, and must never break the decision.
    try:
        from . import notify

        notify.resolve_and_notify(proposal_id, decision=decision)
    except Exception:  # pragma: no cover - notify is best-effort
        pass

    return JsonResponse(200, {"id": proposal_id, "status": decision})


# ---------------------------------------------------------------------------
# Learning Queue (the JARVIS learning-dataset candidate queue)
# ---------------------------------------------------------------------------


def _learning_store():
    """Load the learning-dataset store (profile-aware via ``get_hermes_home``)."""

    from hermes_cli.jarvis_prime.learning_dataset import DatasetStore

    return DatasetStore.load()


def learning_list(req: Request) -> JsonResponse:
    """The learning-dataset candidate queue as provenance-first cards.

    Honest empty list when the store is missing or the pipeline is
    unavailable — never fabricated.
    """

    try:
        from . import contract

        store = _learning_store()
        trace_type = req.query.get("trace_type")
        status = req.query.get("status")
        cards = []
        for cand in store.entries():
            d = cand.to_dict()
            if trace_type and d.get("trace_type") != trace_type:
                continue
            if status and d.get("status") != status:
                continue
            cards.append(contract.learning_card(d, candidate_id=cand.id))
        return JsonResponse(200, {"learning": cards})
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"learning": [], "error": str(exc)})


def learning_decide(req: Request) -> JsonResponse:
    """Approve/reject a learning candidate. Approve requires the owner phrase."""

    candidate_id = req.path_params.get("id", "")
    decision = str(req.body.get("decision", "")).lower().strip()
    if decision not in ("approve", "reject"):
        return JsonResponse(400, {"error": "decision must be 'approve' or 'reject'"})

    from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

    if decision == "approve":
        phrase = str(req.body.get("authorization", "")).strip()
        if phrase != AUTHORIZATION_PHRASE:
            # Owner-gate contract: exact phrase required. Never bypass.
            return JsonResponse(
                403,
                {
                    "error": "owner authorization required",
                    "hint": f"reply exactly: {AUTHORIZATION_PHRASE!r}",
                },
            )

    store = _learning_store()
    if store.get(candidate_id) is None:
        return JsonResponse(404, {"error": f"unknown candidate: {candidate_id}"})
    note = str(req.body.get("notes", "") or f"{decision} via cockpit")
    if decision == "approve":
        store.approve(candidate_id, note=note)
    else:
        store.reject(candidate_id, note=note)
    return JsonResponse(200, {"id": candidate_id, "status": decision})


def learning_export(req: Request) -> JsonResponse:
    """Report exportable counts per format (read-only; never streams secrets)."""

    try:
        from hermes_cli.jarvis_prime.learning_dataset import CandidateStatus

        store = _learning_store()
        approved = store.entries(status=CandidateStatus.APPROVED)
        eligible = [c for c in approved if c.is_negative or c.quality.passed(c.trace_type)]
        return JsonResponse(
            200,
            {
                "formats": ["jsonl", "preference_pairs", "eval_cases", "skill_candidates"],
                "approved": len(approved),
                "exportable": len(eligible),
                "pending": len(store.pending()),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"formats": [], "error": str(exc)})
# Voice intake (mobile-native, hands-free)
# ---------------------------------------------------------------------------
#
# These two handlers expose the *canonical* voice-intake pipeline
# (``hermes_cli.voice_intake`` + ``voice_models``) to the cockpit so the
# Android app reuses one source of truth for read-back, intent
# classification, secret redaction, and the driving-mode safety veto —
# instead of reimplementing any of it client-side. Nothing here captures
# audio; the app sends an already-transcribed string.


def _voice_job_submitter(prompt: str) -> str:
    """Enqueue an approved voice intake onto the same queue ``jobs_dispatch``
    uses. Returns the new job id. No new orchestration primitive — this is
    the existing ``JobQueue`` path with a voice provenance tag."""
    import secrets as _secrets

    from hermes_cli.job_queue import JobQueue

    job_id = "job_" + _secrets.token_hex(8)
    JobQueue().add_job(
        job_id=job_id,
        prompt=prompt,
        repo_root="",
        workers=[],
        metadata={"title": "voice intake", "source": "cockpit-voice"},
    )
    return job_id


def voice_intake_create(req: Request) -> JsonResponse:
    """Open a voice intake from a transcript and return the read-back.

    Body: ``{transcript, mode?}``. ``mode`` is normalised server-side
    (unknown/typo'd modes collapse to ``push_to_talk`` — never silently
    driving). The draft is classified and the read-back built, but nothing
    is submitted: the app must call ``/decide`` with an explicit phrase.
    """
    text = str(req.body.get("transcript", "")).strip()
    if not text:
        return JsonResponse(400, {"error": "transcript is required"})

    from hermes_cli import voice_intake as vi
    from hermes_cli.voice_models import (
        VoiceDisabledError,
        VoiceIntakeConfig,
        VoiceTranscript,
        normalize_mode,
    )

    mode = normalize_mode(req.body.get("mode"))
    try:
        intake = vi.begin_intake(VoiceIntakeConfig(mode=mode))
    except VoiceDisabledError as exc:
        return JsonResponse(409, {"error": str(exc), "state": "disabled"})
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})

    provider = str(req.body.get("provider", "cockpit")) or "cockpit"
    intake = vi.ingest_transcript(intake, VoiceTranscript(text=text, provider=provider))
    readback = vi.build_readback(intake)
    return JsonResponse(
        201,
        {
            "id": intake.id,
            "mode": intake.mode,
            "readback": readback,
            "approval_state": intake.approval.state,
            "draft": {
                "intent": intake.draft.intent,
                "summary": intake.draft.summary,
                "publish_action": intake.draft.publish_action,
                "requires_implementation": intake.draft.requires_implementation,
            },
        },
    )


def voice_intake_decide(req: Request) -> JsonResponse:
    """Resolve a voice intake with an explicit spoken/typed phrase.

    Body: ``{phrase}`` (may be omitted/null to mean "the window closed").
    The phrase is interpreted by ``record_decision`` — only an explicit
    affirmative approves. A driving-mode publish that *was* approved still
    raises ``DrivingSafetyVeto`` → ``409``; the action queues for a
    non-driving confirmation. Voice can never silently execute a publish.
    """
    voice_id = req.path_params.get("id", "")

    from hermes_cli import voice_intake as vi
    from hermes_cli.voice_models import DrivingSafetyVeto, VoiceConfirmationRequired

    intake = vi.load_intake(voice_id)
    if intake is None:
        return JsonResponse(404, {"error": f"unknown voice intake: {voice_id}"})

    raw_phrase = req.body.get("phrase", None)
    phrase = None if raw_phrase is None else str(raw_phrase)
    intake = vi.record_decision(intake, phrase)

    job_id: Optional[str] = None
    try:
        job_id = vi.finalize(intake, submitter=_voice_job_submitter)
    except DrivingSafetyVeto as exc:
        return JsonResponse(
            409,
            {
                "id": intake.id,
                "state": intake.approval.state,
                "veto": "driving_safety",
                "hint": str(exc),
            },
        )
    except VoiceConfirmationRequired as exc:
        return JsonResponse(
            409,
            {
                "id": intake.id,
                "state": intake.approval.state,
                "veto": "confirmation_required",
                "hint": str(exc),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})

    return JsonResponse(
        200,
        {
            "id": intake.id,
            "state": intake.approval.state,
            "job_id": job_id,
            "notes": intake.approval.notes,
        },
    )


# ---------------------------------------------------------------------------
# Server-side voice audio duplex (transcribe in / synthesize out)
# ---------------------------------------------------------------------------
#
# The intake/decide handlers above are transcript-only — the app sends an
# already-transcribed string. These two routes close the *audio* loop so a
# thin client can hand the server raw audio and get redacted text back, and
# hand the server text and get spoken audio back, reusing the existing STT
# (``tools.transcription_tools``) and TTS (``tools.tts_tool``) providers — no
# new provider logic here. Audio is carried as base64 in JSON (the cockpit
# transport is JSON-only) and is **never retained**: the temp file (and, for
# TTS, the whole temp dir) is deleted in a ``finally``. The transcript is
# secret-redacted before it leaves the server, like every cockpit projection.

# Reject oversized uploads early (before decoding into memory). ~34 MiB of
# base64 ≈ the STT layer's own 25 MB raw-file cap; the tool re-checks too.
_MAX_VOICE_AUDIO_B64 = 34 * 1024 * 1024
_MAX_TTS_TEXT_CHARS = 8000

# Common audio MIME -> temp-file suffix. The suffix must be one the STT layer
# accepts (``transcription_tools.SUPPORTED_FORMATS``); unknown types fall back
# to ``.wav`` (PCM-friendly and always supported).
_AUDIO_MIME_SUFFIX = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/m4a": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/ogg": ".ogg",
    "audio/opus": ".ogg",
    "audio/webm": ".webm",
    "audio/flac": ".flac",
}
_SUFFIX_MIME = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".webm": "audio/webm",
    ".flac": "audio/flac",
}


def _audio_suffix_for_mime(mime: str) -> str:
    base = mime.split(";", 1)[0].strip().lower()
    return _AUDIO_MIME_SUFFIX.get(base, ".wav")


def _mime_for_path(path: str) -> str:
    import os

    return _SUFFIX_MIME.get(os.path.splitext(path)[1].lower(), "audio/mpeg")


def voice_transcribe(req: Request) -> JsonResponse:
    """Transcribe uploaded audio to redacted text (audio is NOT retained).

    Body: ``{audio_base64, mime?, model?}``. The base64 audio is decoded to a
    temp file, transcribed via the configured STT provider, and the temp file
    is deleted before returning. The transcript is secret-redacted. Honest
    degradation: when no STT provider is available the tool's own error is
    surfaced (``transcript: ""`` + ``error``) rather than crashing — exactly
    how the rest of the cockpit degrades.
    """
    import base64
    import binascii
    import os
    import tempfile

    audio_b64 = req.body.get("audio_base64")
    if not isinstance(audio_b64, str) or not audio_b64.strip():
        return JsonResponse(400, {"error": "audio_base64 is required"})
    if len(audio_b64) > _MAX_VOICE_AUDIO_B64:
        return JsonResponse(413, {"error": "audio too large"})
    try:
        audio_bytes = base64.b64decode(audio_b64, validate=True)
    except (binascii.Error, ValueError):
        return JsonResponse(400, {"error": "audio_base64 is not valid base64"})
    if not audio_bytes:
        return JsonResponse(400, {"error": "audio_base64 decoded to empty"})

    suffix = _audio_suffix_for_mime(str(req.body.get("mime", "")))
    raw_model = req.body.get("model")
    model = str(raw_model) if raw_model else None

    from tools.transcription_tools import transcribe_audio

    from gateway.cockpit.redaction import redact_text

    tmp_path: Optional[str] = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix="cockpit-voice-", suffix=suffix)
        with os.fdopen(fd, "wb") as fh:
            fh.write(audio_bytes)
        result = transcribe_audio(tmp_path, model=model)
    finally:
        # Never retain the uploaded audio, success or failure.
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    if not isinstance(result, dict) or not result.get("success"):
        detail = result.get("error") if isinstance(result, dict) else None
        return JsonResponse(
            200,
            {
                "transcript": "",
                "error": detail or "transcription unavailable",
                "audio_retained": False,
            },
        )
    return JsonResponse(
        200,
        {
            "transcript": redact_text(result.get("transcript", "")),
            "provider": result.get("provider"),
            "audio_retained": False,
        },
    )


def voice_responses(req: Request) -> JsonResponse:
    """Synthesize spoken audio for a response string (returned as base64).

    Body: ``{text}``. The text is sent to the configured TTS provider; the
    resulting audio is returned base64-encoded and the temp dir holding it is
    removed before returning (audio is NOT retained server-side). Honest
    degradation: when no TTS provider is available the tool's own error is
    surfaced instead of a crash.
    """
    import base64
    import json as _json
    import os
    import shutil
    import tempfile

    text = str(req.body.get("text", "")).strip()
    if not text:
        return JsonResponse(400, {"error": "text is required"})
    if len(text) > _MAX_TTS_TEXT_CHARS:
        return JsonResponse(413, {"error": "text too long"})

    from tools.tts_tool import text_to_speech_tool

    tmp_dir = tempfile.mkdtemp(prefix="cockpit-tts-")
    try:
        out_path = os.path.join(tmp_dir, "speech.mp3")
        raw = text_to_speech_tool(text, output_path=out_path)
        try:
            result = _json.loads(raw) if isinstance(raw, str) else {}
        except (ValueError, TypeError):
            result = {}
        if not result.get("success"):
            return JsonResponse(
                200,
                {
                    "audio_base64": "",
                    "error": result.get("error", "speech synthesis unavailable"),
                    "audio_retained": False,
                },
            )
        file_path = result.get("file_path") or out_path
        try:
            with open(file_path, "rb") as fh:
                audio_bytes = fh.read()
        except OSError as exc:
            return JsonResponse(500, {"error": f"synthesized audio unreadable: {exc}"})
        return JsonResponse(
            200,
            {
                "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
                "mime": _mime_for_path(file_path),
                "provider": result.get("provider"),
                "chars": len(text),
                "audio_retained": False,
            },
        )
    finally:
        # Wipe the whole temp dir so any provider-written siblings (e.g. an
        # Opus conversion next to the mp3) are removed too.
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Sessions (decision-ledger sessions)
# ---------------------------------------------------------------------------


def sessions_list(_req: Request) -> JsonResponse:
    sessions: list[dict[str, Any]] = []
    try:
        from hermes_cli import decision_ledger as dl

        d = dl.decisions_dir()
        if d.is_dir():
            for child in sorted(d.iterdir()):
                if child.is_dir():
                    ledgers = dl.list_ledgers(child.name)
                    sessions.append({
                        "id": child.name,
                        "decision_count": len(ledgers),
                        "last_updated": _safe(
                            lambda c=child: datetime.fromtimestamp(
                                c.stat().st_mtime, tz=timezone.utc
                            ).isoformat()
                        ),
                    })
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"sessions": [], "error": str(exc)})
    return JsonResponse(200, {"sessions": sessions})


# ---------------------------------------------------------------------------
# Execute gate (shared by job_run and coding/execute — no logic divergence)
# ---------------------------------------------------------------------------


@dataclass
class _ExecuteGate:
    """Outcome of the owner-phrase + loopback gate for an execute lane.

    ``error`` is a hard refusal (unknown worker, or a non-loopback cockpit
    trying to run an execute lane). When ``requires_approval`` is True the
    caller decides how to treat ``authorized``: ``job_run`` 403s, while
    ``coding_execute`` returns a *staged* approval-required response so the
    app can show "Ready to execute — approve to run".
    """

    requires_approval: bool
    authorized: bool
    error: Optional["JsonResponse"]
    authorization_hint: str = ""


def _evaluate_execute_gate(worker_id: str, authorization: str) -> _ExecuteGate:
    """Resolve a worker lane and evaluate the double gate.

    Reuses the real worker registry (``requires_approval`` per lane), the
    loopback guard (``_ALLOW_REMOTE_EXECUTE``), and the exact owner phrase
    (``owner_auth.AUTHORIZATION_PHRASE``). Never bypasses a gate.
    """
    from hermes_cli.workers import builtin_worker_classes, load_builtins

    load_builtins()
    classes = {c.id: c for c in builtin_worker_classes()}
    worker_cls = classes.get(worker_id)
    if worker_cls is None:
        return _ExecuteGate(
            requires_approval=False,
            authorized=False,
            error=JsonResponse(400, {"error": f"unknown worker: {worker_id}"}),
        )
    requires_approval = bool(getattr(worker_cls, "requires_approval", True))
    if requires_approval and _ALLOW_REMOTE_EXECUTE:
        return _ExecuteGate(
            requires_approval=True,
            authorized=False,
            error=JsonResponse(
                403,
                {
                    "error": "agentic execution is disabled on a non-loopback "
                    "cockpit; run the runtime locally (loopback) to use "
                    f"{worker_id!r}.",
                },
            ),
        )
    from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

    return _ExecuteGate(
        requires_approval=requires_approval,
        authorized=(authorization == AUTHORIZATION_PHRASE),
        error=None,
        authorization_hint=f"send authorization exactly: {AUTHORIZATION_PHRASE!r}",
    )


# ---------------------------------------------------------------------------
# Job pause / resume (human-requested scheduling control)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Emergency stop — a real backend halt (not Android-local state)
# ---------------------------------------------------------------------------


def emergency_stop(req: Request) -> JsonResponse:
    """Owner panic button: a decisive backend halt.

    A single tap (a) clears owner gates, disables the proactive tick, and
    releases worker branch leases (runtime halt); (b) **cancels** every
    non-terminal queued/running job so nothing keeps advancing; and (c)
    latches autonomy down to ``READ_ONLY`` (overriding ``HERMES_AUTONOMY``)
    so no auto-approved action runs until the owner re-enables it. Every
    effect is journaled. Cancellation is decisive on purpose — a panic stop
    revokes in-flight autonomous work rather than merely parking it.
    """
    reason = str(req.body.get("reason", "") or "owner_requested").strip()
    result: dict[str, Any] = {
        "engaged": True,
        "reason": reason,
        "cleared_actions": [],
        "branch_leases_cleared": 0,
        "tick_disabled": False,
        "cancelled_jobs": [],
        "cancelled_count": 0,
        "autonomy_level": "read_only",
        "errors": [],
    }
    # 1) Runtime halt: owner gates, proactive tick, worker branch leases.
    try:
        from hermes_cli.jarvis_prime.runtime import JarvisPrime

        stop_result = JarvisPrime().stop(reason=reason)
        result["cleared_actions"] = stop_result.get("cleared_actions", [])
        result["branch_leases_cleared"] = stop_result.get("branch_leases_cleared", 0)
        result["tick_disabled"] = bool(stop_result.get("tick_disabled", False))
    except Exception as exc:  # pragma: no cover - defensive
        result["errors"].append(f"runtime: {exc}")
    # 2) Cancel every non-terminal queue entry so work stops advancing.
    cancelled: list[str] = []
    try:
        from hermes_cli.job_queue import JobQueue, QueueState

        queue = JobQueue()
        for entry in queue.list_jobs():
            if entry.state in QueueState.TERMINAL:
                continue
            try:
                queue.cancel_job(entry.job_id, note=f"emergency stop: {reason}")
                cancelled.append(entry.job_id)
            except Exception as exc:  # pragma: no cover - defensive
                result["errors"].append(f"{entry.job_id}: {exc}")
    except Exception as exc:  # pragma: no cover - defensive
        result["errors"].append(f"queue: {exc}")
    result["cancelled_jobs"] = cancelled
    result["cancelled_count"] = len(cancelled)
    # 3) Latch autonomy to the safe floor (overrides HERMES_AUTONOMY).
    try:
        from hermes_cli import approval_policy as ap

        record = ap.engage_emergency_stop(set_by="cockpit-emergency-stop")
        result["autonomy_level"] = getattr(
            getattr(record, "level", None), "value", "read_only"
        )
    except Exception as exc:  # pragma: no cover - defensive
        result["errors"].append(f"autonomy: {exc}")
    result["halted_at"] = _now_iso()
    return JsonResponse(200, result)


# ---------------------------------------------------------------------------
# Coding lanes — audit (read-only) / plan (stage only) / execute (gated)
# ---------------------------------------------------------------------------


def coding_audit(req: Request) -> JsonResponse:
    """Classify + route a plain-English coding request (read-only).

    Returns the intent, risk class, owner-gate requirement, and worker/model
    lane hint via the natural-language coder. Builds **no** packet and runs
    **nothing** — this is the "what would this do" lane.
    """
    prompt = str(req.body.get("prompt", "")).strip()
    if not prompt:
        return JsonResponse(400, {"error": "prompt is required"})
    try:
        from hermes_cli.jarvis_prime import natural_language_coder as nlc
        from hermes_cli.secrets_policy import redact

        route = nlc.route_request(prompt)
        payload = route.to_dict()
        payload["mission"] = redact(prompt)
        payload["owner_gate_required"] = bool(route.owner_gates) or route.blocked
        payload["generated_at"] = _now_iso()
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(200, payload)


def coding_plan(req: Request) -> JsonResponse:
    """Build + validate a bounded coding work packet (stage only, never runs).

    Reuses ``natural_language_coder.build_work_packet`` /
    ``validate_work_packet`` / ``render_packet_markdown``. 422 when the
    packet fails validation (honest, not faked).
    """
    prompt = str(req.body.get("prompt", "")).strip()
    if not prompt:
        return JsonResponse(400, {"error": "prompt is required"})
    repo_root = str(req.body.get("repo_root") or req.body.get("workspace_path") or ".")
    try:
        from hermes_cli.jarvis_prime import natural_language_coder as nlc

        from . import contract

        packet = nlc.build_work_packet(prompt, repo_root=repo_root)
        validation = nlc.validate_work_packet(packet)
        markdown = nlc.render_packet_markdown(packet)
        payload = {
            "packet": contract.coding_packet(packet),
            "validation": validation.to_dict(),
            "markdown": markdown,
            "owner_gate_required": bool(packet.owner_gates) or packet.blocked,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    status = 200 if validation.ok else 422
    return JsonResponse(status, payload)


def coding_execute(req: Request) -> JsonResponse:
    """Dispatch a coding job **only** through the existing gated orchestrator.

    No second execution engine: build/validate the packet, submit an
    orchestrator job, then reuse the same double gate as ``job_run`` (owner
    phrase + loopback). When the gate is *not* satisfied this returns a
    ``200`` **staged** ``approval_required`` response (with the job id, risk
    class, workspace, worker/model, verification commands, and the phrase the
    owner must send) instead of running. When satisfied it approves the
    ``execute`` phase and dispatches, returning the job + worker ledger trail.
    """
    prompt = str(req.body.get("prompt", "")).strip()
    if not prompt:
        return JsonResponse(400, {"error": "prompt is required"})
    repo_root = str(req.body.get("repo_root") or req.body.get("workspace_path") or ".")
    authorization = str(req.body.get("authorization", "")).strip()
    try:
        from hermes_cli import orchestrator as orch
        from hermes_cli.jarvis_prime import natural_language_coder as nlc

        from . import contract

        packet = nlc.build_work_packet(prompt, repo_root=repo_root)
        validation = nlc.validate_work_packet(packet)
        if not validation.ok:
            return JsonResponse(
                422,
                {
                    "status": "invalid_packet",
                    "packet": contract.coding_packet(packet),
                    "validation": validation.to_dict(),
                },
            )
        if packet.blocked:
            return JsonResponse(
                403,
                {
                    "status": "blocked",
                    "error": "this request is blocked (disallowed intent)",
                    "packet": contract.coding_packet(packet),
                },
            )

        # Worker lane: explicit override, else derive an execute lane from the
        # packet's model-lane hint ("claude" -> "claude-execute"). Execute lanes
        # are owner-gated; the gate below stages when the phrase is absent.
        worker_id = str(req.body.get("worker_id", "")).strip()
        if not worker_id:
            lane = str(packet.model_lane_hint or "claude").lower()
            worker_id = f"{lane}-execute" if lane in ("claude", "codex", "aider", "goose") else "claude-execute"
        gate = _evaluate_execute_gate(worker_id, authorization)
        if gate.error is not None:
            return gate.error

        # Real, gated dispatch path. Reuse a previously-staged job when the
        # client passes its id (the cockpit's approval retry: first tap stages a
        # job, confirming the owner phrase resumes *that* job). Without reuse,
        # confirming would submit a second job and leak the staged one. Fall
        # back to a fresh job when no (or an unknown) id is supplied.
        staged_job_id = str(req.body.get("job_id", "")).strip()
        job = orch.get_job(staged_job_id) if staged_job_id else None
        if job is None:
            job = orch.submit_job(prompt)

        if gate.requires_approval and not gate.authorized:
            # Gate not satisfied → STAGE, do not run. The job is left awaiting
            # the owner's execute approval; the app shows "Ready to execute".
            return JsonResponse(
                200,
                {
                    "status": "approval_required",
                    "job": contract.orchestrator_job(job),
                    "packet": contract.coding_packet(packet),
                    "risk_class": packet.risk_class,
                    "workspace_path": packet.repo_root,
                    "worker_id": worker_id,
                    "model_lane_hint": packet.model_lane_hint,
                    "verification_plan": list(packet.verification_plan),
                    "authorization_required": True,
                    "authorization_hint": gate.authorization_hint,
                },
            )

        if gate.requires_approval:
            orch.approve_phase(job.id, "execute")
        # Pass the requested workspace through so the worker runs the CLI and
        # collects diffs in the selected repo, not the gateway's cwd.
        out = orch.dispatch_job(job.id, worker_id=worker_id, repo_root=packet.repo_root)
        if out is None:  # pragma: no cover - defensive
            return JsonResponse(500, {"error": "dispatch returned no job"})
        trail = [
            e
            for e in orch.get_ledger(out.id).get(out.id, [])
            if str(e.get("kind", "")).startswith("worker_")
        ]
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(
        200,
        {
            "status": "dispatched",
            "job": contract.orchestrator_job(out),
            "packet": contract.coding_packet(packet),
            "worker_id": worker_id,
            "worker_trail": trail[-6:],
            "ledger": {"job_id": out.id},
        },
    )


# ---------------------------------------------------------------------------
# Evidence — search (read-only). The non-mutating claim/verify audit and the
# richer list/detail/promote/demote surface live in the dedicated Evidence
# Engine handlers above (evidence_list / evidence_verify / ...).
# ---------------------------------------------------------------------------


def evidence_search(req: Request) -> JsonResponse:
    """Search the Research Vault for evidence artifacts (read-only).

    Honest empty list when the vault is absent/empty. Never mutates state.
    """
    query = req.query.get("q") or req.query.get("query") or ""
    limit = int(req.query.get("limit", "10"))
    try:
        from hermes_cli.jarvis_prime.research_vault import ResearchVault

        from . import contract

        vault = ResearchVault.load()
        if query.strip():
            artifacts = vault.search(query, limit=limit)
        else:
            artifacts = vault.entries()[:limit]
        items = [contract.evidence_artifact(a) for a in artifacts]
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"items": [], "error": str(exc)})
    return JsonResponse(200, {"items": items})


# ---------------------------------------------------------------------------
# Capabilities — server feature negotiation (not the curated in-app catalog)
# ---------------------------------------------------------------------------


def capabilities(_req: Request) -> JsonResponse:
    """Describe what *this backend* can do, for the app to negotiate against.

    Distinct from the Android curated ``Capability`` picker (an in-app
    catalog by design): this reports the live server's API version, which
    subsystems are importable, detected worker lanes, whether execute lanes
    are permitted (loopback guard), and the route catalog. Redacted: never
    emits the owner phrase value, tokens, or API keys.
    """
    subsystems: dict[str, bool] = {}
    for name, module in (
        ("memory", "hermes_cli.jarvis_prime.memory"),
        ("jobs", "hermes_cli.job_queue"),
        ("orchestrator", "hermes_cli.orchestrator"),
        ("coding", "hermes_cli.jarvis_prime.natural_language_coder"),
        ("evidence", "hermes_cli.jarvis_prime.research_vault"),
        ("ledger", "hermes_cli.decision_ledger"),
        ("models", "hermes_cli.jarvis_prime.model_bootstrap"),
    ):
        try:
            __import__(module)
            subsystems[name] = True
        except Exception:  # pragma: no cover - defensive
            subsystems[name] = False

    # ``available_workers`` advertises the orchestrator worker lane ids that the
    # coding/execute + jobs/{id}/run routes actually accept (``requires_approval``
    # flags which need the owner phrase), so a client can negotiate a lane and
    # dispatch it without hitting ``400 unknown worker``.
    workers: list[dict[str, Any]] = []
    try:
        from hermes_cli.workers import builtin_worker_classes, load_builtins

        load_builtins()
        for cls in builtin_worker_classes():
            workers.append({
                "id": cls.id,
                "requires_approval": bool(getattr(cls, "requires_approval", True)),
            })
    except Exception:  # pragma: no cover - defensive
        workers = []

    # ``detected_clis`` is the separate host-detection view (which external CLIs
    # are installed) — informational, not the set ``execute`` validates against.
    detected_clis: list[str] = []
    try:
        from hermes_cli.jarvis_prime import worker_registry as wr

        detected_clis = [s.lane.id for s in wr.detect_lanes() if s.available]
    except Exception:  # pragma: no cover - defensive
        detected_clis = []

    return JsonResponse(
        200,
        {
            "api_version": COCKPIT_API_VERSION,
            "gateway_version": _gateway_version(),
            "subsystems": subsystems,
            "available_workers": workers,
            "detected_clis": detected_clis,
            "execute_allowed": not _ALLOW_REMOTE_EXECUTE,
            "owner_gate_required": True,
            "generated_at": _now_iso(),
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe(fn):
    try:
        return fn()
    except Exception:  # pragma: no cover - defensive
        return None


def _gateway_version() -> str:
    try:
        import hermes_cli

        v = getattr(hermes_cli, "__version__", None)
        if v:
            return str(v)
    except Exception:
        pass
    try:
        import hermes_cli.jarvis_prime as jp

        return str(getattr(jp, "__version__", "unknown"))
    except Exception:
        return "unknown"


_PROC_START = _now_iso()


def _process_start_iso() -> str:
    return _PROC_START


def _queue_snapshot() -> dict[str, int]:
    snap = {"running": 0, "queued": 0, "waiting_approval": 0}
    try:
        from hermes_cli.job_queue import JobQueue

        queue = JobQueue()
        for entry in queue.list_jobs():
            status = str(getattr(entry, "status", "")).lower()
            if "run" in status:
                snap["running"] += 1
            elif "queue" in status or "pending" in status:
                snap["queued"] += 1
            elif "approval" in status or "wait" in status:
                snap["waiting_approval"] += 1
    except Exception:  # pragma: no cover - defensive
        pass
    return snap


def _ledger_summary(ledger: Any, path: Any) -> dict[str, Any]:
    return {
        "id": str(getattr(ledger, "id", "") or path),
        "title": str(getattr(ledger, "title", "") or ""),
        "type": "decision",
        "status": str(getattr(ledger, "status", "") or ""),
        "source": str(path),
        "timestamp": str(getattr(ledger, "created_at", "") or ""),
    }


# ---------------------------------------------------------------------------
# Research Mode (Evidence Engine)
# ---------------------------------------------------------------------------


def _research_engine():
    """Construct a ResearchEngine bound to the default local stores."""
    from hermes_cli.jarvis_prime.research_engine import ResearchEngine

    return ResearchEngine()


def research_run(req: Request) -> JsonResponse:
    """Run the research pipeline for a query (contract §research).

    Body: ``{"query": str, "manual_sources"?: [{title,url,excerpt}]}``.
    Returns the full report. Source gathering uses the configured web-search
    provider when one is available; otherwise it relies on ``manual_sources``
    and reports honestly via ``notes`` — it never fabricates an answer.
    """
    body = req.body
    query = str(body.get("query", "")).strip()
    if not query:
        return JsonResponse(400, {"error": "query is required"})
    manual = body.get("manual_sources") or []
    if not isinstance(manual, list):
        manual = []
    try:
        from . import contract

        report = _research_engine().run(query, manual_sources=manual)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(201, contract.research_report(report))


def research_list(_req: Request) -> JsonResponse:
    """List past research reports, newest first."""
    try:
        from . import contract

        reports = _research_engine().list_reports()
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    reports = sorted(reports, key=lambda r: r.created_at, reverse=True)
    return JsonResponse(
        200, {"reports": [contract.research_report(r) for r in reports]}
    )


def research_get(req: Request) -> JsonResponse:
    report_id = req.path_params.get("id", "")
    try:
        from . import contract

        report = _research_engine().get_report(report_id)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    if report is None:
        return JsonResponse(404, {"error": f"unknown report: {report_id}"})
    return JsonResponse(200, contract.research_report(report))


def research_promote(req: Request) -> JsonResponse:
    """Promote one evidence card into the Memory Tree — through the gate.

    Reuses the exact same ``MemoryStore.remember`` write path (and policy) as
    :func:`memory_create`, so a promoted finding shows in the Memory screen and
    a secret-like / low-confidence card is honestly rejected with 422.
    """
    report_id = req.path_params.get("id", "")
    card_id = str(req.body.get("card_id", "")).strip()
    if not card_id:
        return JsonResponse(400, {"error": "card_id is required"})
    try:
        from hermes_cli.jarvis_prime.memory import MemoryStore
        from hermes_cli.jarvis_prime.research_engine import ResearchEngine

        from . import contract

        engine = _research_engine()
        report = engine.get_report(report_id)
        if report is None:
            return JsonResponse(404, {"error": f"unknown report: {report_id}"})
        payload = ResearchEngine.promotion_payload(report, card_id)
        if payload is None:
            return JsonResponse(404, {"error": f"unknown card: {card_id}"})
        record = MemoryStore().remember(**payload)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    if record is None:
        # Same honest contract as memory_create — never faked.
        return JsonResponse(
            422, {"stored": False, "reason": "rejected (secret-like or low confidence)"}
        )
    return JsonResponse(201, {"stored": True, "item": contract.memory_item(record)})


def research_create_task(req: Request) -> JsonResponse:
    """Create a coding task from a research report — via the job queue gate.

    Reuses :func:`jobs_dispatch`'s enqueue path: a ``queued`` entry only,
    nothing executes here (owner/run gates unchanged).
    """
    report_id = req.path_params.get("id", "")
    body = req.body
    try:
        from hermes_cli.jarvis_prime.research_engine import ResearchEngine

        engine = _research_engine()
        report = engine.get_report(report_id)
        if report is None:
            return JsonResponse(404, {"error": f"unknown report: {report_id}"})
        title = str(body.get("title", "")).strip() or f"Research: {report.query}"[:120]
        prompt = ResearchEngine.task_prompt(report)
        dispatch = Request(
            method="POST",
            path="/v1/cockpit/jobs",
            body={
                "title": title,
                "prompt": prompt,
                "worker_id": str(body.get("worker_id", "")).strip(),
                "workspace_path": str(body.get("workspace_path", "")).strip(),
            },
        )
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return jobs_dispatch(dispatch)


# ---------------------------------------------------------------------------
# Re-exports
# ---------------------------------------------------------------------------
#
# The autonomy handler group was extracted to ``handlers_autonomy`` (a
# behaviour-preserving move). Re-import the public handlers here at module
# scope so callers that reach them via ``handlers.autonomy_*`` (e.g.
# ``server.py``'s route table) keep resolving unchanged. This import sits at
# the *bottom* of the module on purpose: ``Request`` / ``JsonResponse`` (which
# ``handlers_autonomy`` imports back from here) are already defined by now, so
# the two-way import resolves without a cycle.
from .handlers_autonomy import (  # noqa: E402  (intentional bottom-of-module re-export)
    autonomy_decisions,
    autonomy_get,
    autonomy_set,
)

# The Neural Observatory handler group (SYNAPSE Phase 3) lives in
# ``handlers_observatory`` — same bottom-of-module re-export contract as the
# autonomy group above, so ``server.py``'s route table reaches them via
# ``h.observatory_*`` like every other handler.
from .handlers_observatory import (  # noqa: E402  (intentional bottom-of-module re-export)
    observatory_layout,
    observatory_metrics,
    observatory_snapshot,
)

__all__ = [
    "COCKPIT_API_VERSION",
    "JsonResponse",
    "Request",
    "audit_events",
    "audit_list",
    "audit_proof",
    "capabilities",
    "coding_audit",
    "coding_execute",
    "coding_plan",
    "autonomy_decisions",
    "autonomy_get",
    "autonomy_set",
    "diagnostics",
    "emergency_stop",
    "evidence_demote",
    "evidence_detail",
    "evidence_list",
    "evidence_promote",
    "evidence_search",
    "evidence_verify",
    "health",
    "job_approve",
    "job_cancel",
    "job_diff",
    "job_file",
    "job_files_changed",
    "job_get",
    "job_ledger",
    "job_override",
    "job_pause",
    "job_publish",
    "job_publish_preview",
    "job_rerun",
    "job_resume",
    "job_revalidate",
    "job_tree",
    "job_validate",
    "job_validation",
    "jobs_dispatch",
    "jobs_list",
    "ledger_event_detail",
    "ledger_rollback_request",
    "ledger_timeline",
    "memory_create",
    "memory_delete",
    "memory_list",
    "models",
    "navigation_list",
    "observatory_layout",
    "observatory_metrics",
    "observatory_snapshot",
    "pair_confirm",
    "pair_start",
    "proposals_list",
    "research_create_task",
    "research_get",
    "research_list",
    "research_promote",
    "research_run",
    "runtime_status",
    "runtime_workers",
    "skills_list",
    "templates_list",
]
