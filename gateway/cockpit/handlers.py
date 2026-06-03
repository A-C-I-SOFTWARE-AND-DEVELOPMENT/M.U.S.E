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
from typing import Any, Optional


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
            "time": _now_iso(),
        },
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
# Audit (decision ledger) + tasks (job queue)
# ---------------------------------------------------------------------------


def audit_events(req: Request) -> JsonResponse:
    limit = int(req.query.get("limit", "100"))
    events: list[dict[str, Any]] = []
    try:
        from hermes_cli import decision_ledger as dl

        for path in dl.list_ledgers()[:limit]:
            try:
                ledger = dl.read_ledger(path)
                events.append(_ledger_summary(ledger, path))
            except Exception:
                continue
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"events": [], "error": str(exc)})
    return JsonResponse(200, {"events": events})


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
            200, {"jobs": [], "next_cursor": None, "prev_cursor": None, "error": str(exc)}
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
    jobs.sort(key=lambda j: (j.get("created_at") or ""), reverse=True)
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
        from hermes_cli.workers import builtin_worker_classes, load_builtins

        from . import contract

        load_builtins()
        job = orch.get_job(job_id)
        if job is None:
            return JsonResponse(404, {"error": f"unknown job: {job_id}"})

        classes = {c.id: c for c in builtin_worker_classes()}
        worker_cls = classes.get(worker_id)
        if worker_cls is None:
            return JsonResponse(400, {"error": f"unknown worker: {worker_id}"})
        requires_approval = bool(getattr(worker_cls, "requires_approval", True))

        if requires_approval:
            if _ALLOW_REMOTE_EXECUTE:
                return JsonResponse(
                    403,
                    {
                        "error": "agentic execution is disabled on a non-loopback "
                        "cockpit; run the runtime locally (loopback) to use "
                        f"{worker_id!r}.",
                    },
                )
            from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

            if authorization != AUTHORIZATION_PHRASE:
                return JsonResponse(
                    403,
                    {
                        "error": "owner approval required to run an execute lane",
                        "hint": f"send authorization exactly: {AUTHORIZATION_PHRASE!r}",
                    },
                )
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
    return JsonResponse(200, {"job": contract.orchestrator_job(out), "worker_trail": trail[-6:]})


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
    """Cancel a job (contract §4). 409 if already terminal."""
    job_id = req.path_params.get("id", "")
    reason = req.body.get("reason")
    try:
        from hermes_cli.job_queue import JobQueue, JobQueueNotFoundError, QueueState

        from . import contract

        queue = JobQueue()
        try:
            entry = queue.get_job(job_id)
        except JobQueueNotFoundError:
            return JsonResponse(404, {"error": f"unknown job: {job_id}"})
        if entry.state in QueueState.TERMINAL:
            return JsonResponse(409, {"error": f"job already {entry.state}"})
        entry = queue.cancel_job(job_id, note=str(reason) if reason else None)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(200, contract.cockpit_job(entry))


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
    """
    limit = int(req.query.get("limit", "50"))
    items: list[dict[str, Any]] = []
    try:
        from hermes_cli import orchestrator as orch

        from . import contract

        ledger = orch.get_ledger() or {}
        for job_id, entries in ledger.items():
            for entry in entries or []:
                if isinstance(entry, dict) and entry.get("kind") == "navigation_decision":
                    items.append(contract.navigation_view(entry, job_id=job_id))
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        items = items[:limit]
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(200, {"navigations": [], "error": str(exc)})
    return JsonResponse(200, {"navigations": items})


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
    matched = False
    for p in items:
        if _proposal_id(p) == proposal_id:
            p["status"] = "approved" if decision == "approve" else "rejected"
            p["resolved_at"] = _now_iso()
            p["owner_decision_note"] = f"{decision} via cockpit"
            matched = True
            break
    if not matched:
        return JsonResponse(404, {"error": f"unknown proposal: {proposal_id}"})
    _save_proposals(items)
    return JsonResponse(200, {"id": proposal_id, "status": items and decision})


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


__all__ = [
    "COCKPIT_API_VERSION",
    "JsonResponse",
    "Request",
    "audit_events",
    "audit_list",
    "audit_proof",
    "diagnostics",
    "health",
    "job_cancel",
    "job_get",
    "jobs_dispatch",
    "jobs_list",
    "memory_create",
    "memory_delete",
    "memory_list",
    "models",
    "navigation_list",
    "proposals_list",
    "runtime_status",
    "runtime_workers",
    "skills_list",
]
