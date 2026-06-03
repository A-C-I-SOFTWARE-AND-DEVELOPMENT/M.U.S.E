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


def job_pause(req: Request) -> JsonResponse:
    """Pause a job (human-requested). 404 unknown, 409 if already terminal.

    Thin wrapper over ``JobQueue.pause_job`` — the queue stays the single
    scheduling authority; nothing here advances or runs work.
    """
    job_id = req.path_params.get("id", "")
    note = req.body.get("note") or req.body.get("reason")
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
        entry = queue.pause_job(job_id, note=str(note) if note else None)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(200, contract.cockpit_job(entry))


def job_resume(req: Request) -> JsonResponse:
    """Resume a paused/blocked/disconnected/failed job (back to ``queued``).

    Thin wrapper over ``JobQueue.resume_job``. 404 unknown; 409 when the
    state isn't resumable (e.g. already running or terminal).
    """
    job_id = req.path_params.get("id", "")
    note = req.body.get("note") or req.body.get("reason")
    try:
        from hermes_cli.job_queue import JobQueue, JobQueueNotFoundError, QueueState

        from . import contract

        queue = JobQueue()
        try:
            entry = queue.get_job(job_id)
        except JobQueueNotFoundError:
            return JsonResponse(404, {"error": f"unknown job: {job_id}"})
        if entry.state not in QueueState.RESUMABLE:
            return JsonResponse(409, {"error": f"job not resumable from {entry.state}"})
        entry = queue.resume_job(job_id, note=str(note) if note else None)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(200, contract.cockpit_job(entry))


# ---------------------------------------------------------------------------
# Emergency stop — a real backend halt (not Android-local state)
# ---------------------------------------------------------------------------


def emergency_stop(req: Request) -> JsonResponse:
    """Halt backend work: clear owner gates, disable the tick, release worker
    branch leases, and pause every non-terminal queued/running job.

    This genuinely stops backend *advancement* (and revokes the branch
    leases workers hold) — it is not a local Android toggle. It does not
    SIGKILL a worker subprocess already mid-command; pausing is reversible
    via ``/jobs/{id}/resume``. Every effect is journaled to memory/ledger.
    """
    reason = str(req.body.get("reason", "") or "owner_requested").strip()
    result: dict[str, Any] = {
        "reason": reason,
        "cleared_actions": [],
        "branch_leases_cleared": 0,
        "tick_disabled": False,
        "jobs_paused": 0,
        "jobs_paused_ids": [],
    }
    # 1) Runtime halt: owner gates, proactive tick, worker branch leases.
    try:
        from hermes_cli.jarvis_prime.runtime import JarvisPrime

        stop_result = JarvisPrime().stop(reason=reason)
        result["cleared_actions"] = stop_result.get("cleared_actions", [])
        result["branch_leases_cleared"] = stop_result.get("branch_leases_cleared", 0)
        result["tick_disabled"] = bool(stop_result.get("tick_disabled", False))
    except Exception as exc:  # pragma: no cover - defensive
        result["runtime_error"] = str(exc)
    # 2) Pause every non-terminal queue entry so work stops advancing.
    try:
        from hermes_cli.job_queue import JobQueue, QueueState

        queue = JobQueue()
        paused: list[str] = []
        for entry in queue.list_jobs():
            if entry.state in QueueState.TERMINAL or entry.state == QueueState.PAUSED:
                continue
            try:
                queue.pause_job(entry.job_id, note=f"emergency stop: {reason}")
                paused.append(entry.job_id)
            except Exception:  # pragma: no cover - defensive
                continue
        result["jobs_paused"] = len(paused)
        result["jobs_paused_ids"] = paused
    except Exception as exc:  # pragma: no cover - defensive
        result["queue_error"] = str(exc)
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

        # Real, gated dispatch path: submit an orchestrator job first.
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
        out = orch.dispatch_job(job.id, worker_id=worker_id)
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
# Evidence — search (read-only) / verify (non-mutating claim audit)
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


def evidence_verify(req: Request) -> JsonResponse:
    """Audit a claim against the Research Vault + epistemics (**non-mutating**).

    Cross-checks the vault for supporting/contradicting artifacts and runs
    the citation/epistemic audit, returning a verdict with confidence,
    supporting/contradicting sources, missing evidence, and a freshness
    status. Never writes the vault and is safe to call repeatedly.
    """
    claim = str(req.body.get("claim", "")).strip()
    if not claim:
        return JsonResponse(400, {"error": "claim is required"})
    source_ids = [str(s) for s in (req.body.get("source_ids") or [])]
    try:
        from hermes_cli.jarvis_prime import epistemics
        from hermes_cli.jarvis_prime.research_vault import ResearchVault
        from hermes_cli.secrets_policy import redact

        from . import contract

        vault = ResearchVault.load()
        matches = vault.search(claim, limit=10)
        if source_ids:
            pinned = [vault.artifacts[i] for i in source_ids if i in vault.artifacts]
            # Pinned sources take precedence, then de-duped search matches.
            seen = {a.id for a in pinned}
            matches = pinned + [a for a in matches if a.id not in seen]

        citations = [a.source_uri for a in matches if a.source_uri]
        report = epistemics.audit_response(claim, provided_citations=citations)
        payload = contract.evidence_verdict(claim, matches, report)
        payload["claim"] = redact(claim)
    except Exception as exc:  # pragma: no cover - defensive
        return JsonResponse(500, {"error": str(exc)})
    return JsonResponse(200, payload)


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

    workers: list[str] = []
    try:
        from hermes_cli.jarvis_prime import worker_registry as wr

        workers = [s.lane.id for s in wr.detect_lanes() if s.available]
    except Exception:  # pragma: no cover - defensive
        workers = []

    return JsonResponse(
        200,
        {
            "api_version": COCKPIT_API_VERSION,
            "gateway_version": _gateway_version(),
            "subsystems": subsystems,
            "available_workers": workers,
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
    "diagnostics",
    "emergency_stop",
    "evidence_search",
    "evidence_verify",
    "health",
    "job_cancel",
    "job_get",
    "job_pause",
    "job_resume",
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
