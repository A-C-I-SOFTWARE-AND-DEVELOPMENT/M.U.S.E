"""Local-only Hermes orchestrator API + WebSocket backend.

Exposes Hermes orchestration jobs through a small FastAPI app so the
Android APK, the TUI, and other local clients can control and observe
jobs without needing to embed Hermes' Python internals.

Design constraints (see ``docs/orchestration/local-api-backend.md``):

* Local-first. Binds to ``127.0.0.1`` by default. The caller has to opt
  in to a public bind, and the app *refuses* to start with no token
  configured in that mode.
* No multi-tenant complexity. There is one shared in-memory job store
  per process. Clients are trusted local processes on the same machine.
* Token auth is optional. Without a token the API is fully open on
  loopback. Set ``HERMES_ORCHESTRATOR_API_TOKEN`` (or pass ``token=`` to
  :func:`create_app`) to require ``Authorization: Bearer <token>`` on
  every request and ``?token=<token>`` on WebSocket connects.
* No heavy framework beyond FastAPI which is already an optional
  ``[web]`` extra of hermes-agent.

The store is intentionally minimal — job state lives in memory, keyed
by job id. Persistent orchestration state is the responsibility of the
worker that handed the job to this API; this module just exposes
control + observability surfaces.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

try:
    from fastapi import (
        Depends,
        FastAPI,
        HTTPException,
        Request,
        WebSocket,
        WebSocketDisconnect,
        status,
    )
    from fastapi.responses import JSONResponse
    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the extra
    FastAPI = None  # type: ignore[assignment]
    HTTPException = Exception  # type: ignore[assignment]
    WebSocket = object  # type: ignore[assignment]
    WebSocketDisconnect = Exception  # type: ignore[assignment]
    FASTAPI_AVAILABLE = False

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

# Event names emitted on /jobs/{job_id}/events. Kept as constants so the
# Android / TUI clients can import them and stay in sync without copying
# string literals.
EVENT_JOB_CREATED = "job.created"
EVENT_EVIDENCE_UPDATED = "evidence.updated"
EVENT_WORKER_STARTED = "worker.started"
EVENT_WORKER_BLOCKED = "worker.blocked"
EVENT_WORKER_COMPLETED = "worker.completed"
EVENT_SCORING_COMPLETED = "scoring.completed"
EVENT_VALIDATION_COMPLETED = "validation.completed"
EVENT_PUBLISH_READY = "publish.ready"
EVENT_JOB_FAILED = "job.failed"

ALL_EVENTS: tuple = (
    EVENT_JOB_CREATED,
    EVENT_EVIDENCE_UPDATED,
    EVENT_WORKER_STARTED,
    EVENT_WORKER_BLOCKED,
    EVENT_WORKER_COMPLETED,
    EVENT_SCORING_COMPLETED,
    EVENT_VALIDATION_COMPLETED,
    EVENT_PUBLISH_READY,
    EVENT_JOB_FAILED,
)

# Terminal statuses — POST /jobs/{id}/cancel/resume reject these.
_TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


@dataclass
class Job:
    """In-memory representation of an orchestration job."""

    id: str
    name: str
    spec: Dict[str, Any]
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    evidence: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    validation: Optional[Dict[str, Any]] = None
    publish_plan: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "spec": self.spec,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "evidence": self.evidence,
            "artifacts": self.artifacts,
            "validation": self.validation,
            "publish_plan": self.publish_plan,
            "error": self.error,
        }


class JobStore:
    """Thread-safe in-memory job store with per-job event broadcasting.

    The store is shared by every request handler. WebSocket subscribers
    are tracked per job id and woken via :meth:`emit_event`.
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._subscribers: Dict[str, Set["asyncio.Queue[Dict[str, Any]]"]] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Job CRUD
    # ------------------------------------------------------------------
    async def create(self, name: str, spec: Dict[str, Any]) -> Job:
        async with self._lock:
            job = Job(id=str(uuid.uuid4()), name=name, spec=dict(spec or {}))
            self._jobs[job.id] = job
        await self.emit_event(
            job.id, EVENT_JOB_CREATED, {"name": job.name, "spec": job.spec}
        )
        return job

    async def get(self, job_id: str) -> Job:
        async with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    async def list(self) -> List[Job]:
        async with self._lock:
            return list(self._jobs.values())

    async def update(self, job_id: str, **changes: Any) -> Job:
        """Apply attribute changes to an existing job."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            for key, value in changes.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            job.updated_at = time.time()
        return job

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    async def emit_event(
        self,
        job_id: str,
        event: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Append an event to the job log and fan it out to subscribers."""
        if event not in ALL_EVENTS:
            raise ValueError(f"unknown event: {event}")
        envelope = {
            "event": event,
            "job_id": job_id,
            "ts": time.time(),
            "data": dict(data or {}),
        }
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.events.append(envelope)
                job.updated_at = envelope["ts"]
            subs = list(self._subscribers.get(job_id, ()))
        for queue in subs:
            try:
                queue.put_nowait(envelope)
            except asyncio.QueueFull:
                # Slow subscriber — drop the event rather than block the
                # whole broadcaster. The subscriber will see the missed
                # event reflected in the job state on its next poll.
                logger.warning(
                    "orchestrator_api: dropping event for slow subscriber on job %s",
                    job_id,
                )
        return envelope

    async def subscribe(self, job_id: str) -> "asyncio.Queue[Dict[str, Any]]":
        queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subscribers.setdefault(job_id, set()).add(queue)
        return queue

    async def unsubscribe(
        self, job_id: str, queue: "asyncio.Queue[Dict[str, Any]]"
    ) -> None:
        async with self._lock:
            subs = self._subscribers.get(job_id)
            if subs is not None:
                subs.discard(queue)
                if not subs:
                    self._subscribers.pop(job_id, None)

    async def replay(self, job_id: str) -> List[Dict[str, Any]]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            return list(job.events)


def _is_loopback_host(host: str) -> bool:
    return host in _LOOPBACK_HOSTS


def _client_is_local(request_or_ws: Any) -> bool:
    """Both ``Request`` and ``WebSocket`` expose ``.client.host`` the same way."""
    client = getattr(request_or_ws, "client", None)
    host = getattr(client, "host", "") if client else ""
    if not host:
        # No socket peer (e.g. ASGI test transport with no client tuple).
        # Treat as local — tests rely on this and uvicorn fills it in.
        return True
    return _is_loopback_host(host)


def create_app(
    *,
    store: Optional[JobStore] = None,
    token: Optional[str] = None,
    allow_public_bind: bool = False,
) -> "FastAPI":
    """Build the orchestrator FastAPI application.

    Args:
        store: Optional pre-existing :class:`JobStore`. Lets tests inject
            a populated store, and lets the gateway share one store with
            its job dispatcher.
        token: When set, every HTTP request must carry
            ``Authorization: Bearer <token>`` (constant-time compared)
            and every WebSocket must include ``?token=<token>``.
        allow_public_bind: Set to ``True`` only when the caller is
            *deliberately* exposing the API beyond loopback. When
            ``False`` (default) the middleware refuses non-loopback
            clients even if uvicorn happened to bind ``0.0.0.0``.

    Raises:
        RuntimeError: if FastAPI isn't installed.
    """
    if not FASTAPI_AVAILABLE:
        raise RuntimeError(
            "fastapi is required for hermes_cli.orchestrator_api. Install "
            "with: pip install 'hermes-agent[web]' or `pip install fastapi`."
        )

    store = store or JobStore()
    app = FastAPI(title="Hermes Orchestrator API", version="1.0.0")
    app.state.store = store
    app.state.token = token
    app.state.allow_public_bind = allow_public_bind

    # ------------------------------------------------------------------
    # Middleware: loopback + token enforcement
    # ------------------------------------------------------------------
    @app.middleware("http")
    async def _local_only_guard(request: "Request", call_next: Callable[..., Any]):
        if not allow_public_bind and not _client_is_local(request):
            return JSONResponse(
                {"error": "orchestrator API is restricted to loopback"},
                status_code=403,
            )
        if token:
            auth = request.headers.get("authorization", "")
            prefix = "Bearer "
            if not auth.startswith(prefix) or not hmac.compare_digest(
                auth[len(prefix):].encode(), token.encode()
            ):
                # Skip token check on the unauthenticated health probe so
                # supervisors (systemd, Docker healthcheck) work without
                # baking the token into their config.
                if request.url.path != "/health":
                    return JSONResponse(
                        {"error": "missing or invalid bearer token"},
                        status_code=401,
                    )
        return await call_next(request)

    def _ws_authorised(ws: "WebSocket") -> bool:
        if not allow_public_bind and not _client_is_local(ws):
            return False
        if not token:
            return True
        supplied = ws.query_params.get("token", "")
        return hmac.compare_digest(supplied.encode(), token.encode())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _get_job_or_404(job_id: str) -> Job:
        try:
            return await store.get(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"job {job_id} not found")

    def _reject_terminal(job: Job, action: str) -> None:
        if job.status in _TERMINAL_STATES:
            raise HTTPException(
                status_code=409,
                detail=f"cannot {action} job in terminal state '{job.status}'",
            )

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "service": "hermes-orchestrator-api",
            "version": "1.0.0",
            "auth_required": bool(token),
            "public_bind": bool(allow_public_bind),
        }

    @app.get("/jobs")
    async def list_jobs() -> Dict[str, Any]:
        jobs = await store.list()
        return {"jobs": [j.to_dict() for j in jobs]}

    @app.post("/jobs", status_code=201)
    async def create_job(payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="payload must be a JSON object")
        raw_name = payload.get("name", payload.get("title", "untitled"))
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise HTTPException(
                status_code=400, detail="'name' must be a non-empty string"
            )
        name = raw_name
        spec = payload.get("spec", {})
        if spec is None:
            spec = {}
        if not isinstance(spec, dict):
            raise HTTPException(status_code=400, detail="'spec' must be an object")
        job = await store.create(name=name.strip(), spec=spec)
        return job.to_dict()

    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str) -> Dict[str, Any]:
        job = await _get_job_or_404(job_id)
        return job.to_dict()

    @app.get("/jobs/{job_id}/status")
    async def get_job_status(job_id: str) -> Dict[str, Any]:
        job = await _get_job_or_404(job_id)
        return {
            "id": job.id,
            "status": job.status,
            "updated_at": job.updated_at,
            "error": job.error,
        }

    @app.get("/jobs/{job_id}/artifacts")
    async def get_job_artifacts(job_id: str) -> Dict[str, Any]:
        job = await _get_job_or_404(job_id)
        return {"id": job.id, "artifacts": list(job.artifacts)}

    @app.post("/jobs/{job_id}/resume")
    async def resume_job(job_id: str) -> Dict[str, Any]:
        job = await _get_job_or_404(job_id)
        _reject_terminal(job, "resume")
        job = await store.update(job_id, status="running", error=None)
        await store.emit_event(job_id, EVENT_WORKER_STARTED, {"reason": "resume"})
        return job.to_dict()

    @app.post("/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str) -> Dict[str, Any]:
        job = await _get_job_or_404(job_id)
        if job.status in _TERMINAL_STATES:
            return job.to_dict()
        job = await store.update(job_id, status="cancelled")
        await store.emit_event(job_id, EVENT_JOB_FAILED, {"reason": "cancelled"})
        return job.to_dict()

    @app.post("/jobs/{job_id}/validate")
    async def validate_job(job_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        job = await _get_job_or_404(job_id)
        _reject_terminal(job, "validate")
        result = dict(payload or {})
        result.setdefault("requested_at", time.time())
        job = await store.update(job_id, validation=result, status="validating")
        await store.emit_event(
            job_id, EVENT_VALIDATION_COMPLETED, {"result": result}
        )
        return job.to_dict()

    @app.post("/jobs/{job_id}/publish-plan")
    async def publish_plan(job_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        job = await _get_job_or_404(job_id)
        _reject_terminal(job, "publish")
        plan = dict(payload or {})
        plan.setdefault("prepared_at", time.time())
        job = await store.update(job_id, publish_plan=plan, status="publish_ready")
        await store.emit_event(job_id, EVENT_PUBLISH_READY, {"plan": plan})
        return job.to_dict()

    # ------------------------------------------------------------------
    # WebSocket — /jobs/{job_id}/events
    # ------------------------------------------------------------------
    @app.websocket("/jobs/{job_id}/events")
    async def job_events(ws: "WebSocket", job_id: str) -> None:
        if not _ws_authorised(ws):
            await ws.close(code=4401)
            return
        try:
            await store.get(job_id)
        except KeyError:
            await ws.close(code=4404)
            return

        await ws.accept()

        # Replay any buffered history first so a late subscriber sees the
        # ``job.created`` event that was emitted before it connected.
        history = await store.replay(job_id)
        for envelope in history:
            await ws.send_json(envelope)

        queue = await store.subscribe(job_id)
        try:
            recv_task = asyncio.create_task(_drain_ws(ws))
            try:
                while True:
                    envelope = await queue.get()
                    await ws.send_json(envelope)
            finally:
                recv_task.cancel()
        except WebSocketDisconnect:
            pass
        except Exception as exc:  # pragma: no cover - belt-and-braces
            logger.warning("orchestrator_api: WS error on job %s: %s", job_id, exc)
        finally:
            await store.unsubscribe(job_id, queue)

    return app


async def _drain_ws(ws: "WebSocket") -> None:
    """Pull (and discard) any client-sent frames so disconnects surface promptly."""
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        return
    except Exception:
        return


def run(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    token: Optional[str] = None,
    allow_public_bind: bool = False,
) -> None:
    """Run the orchestrator API under uvicorn.

    The CLI wrapper resolves ``token`` from ``HERMES_ORCHESTRATOR_API_TOKEN``
    when not provided. A public bind without a token is refused so the
    operator can't accidentally publish an unauthenticated control plane.
    """
    try:
        import uvicorn  # local import — avoids hard dep at import time
    except ImportError as exc:  # pragma: no cover - dep error path
        raise RuntimeError(
            "uvicorn is required to run the orchestrator API. Install "
            "with: pip install 'hermes-agent[web]'."
        ) from exc

    if token is None:
        token = os.environ.get("HERMES_ORCHESTRATOR_API_TOKEN") or None

    is_public = host not in {"127.0.0.1", "localhost", "::1"}
    if is_public and not allow_public_bind:
        raise RuntimeError(
            f"refusing to bind orchestrator API to {host!r}: pass "
            "allow_public_bind=True (or --insecure on the CLI) to opt in."
        )
    if is_public and not token:
        raise RuntimeError(
            "refusing to bind orchestrator API to a non-loopback address "
            "without HERMES_ORCHESTRATOR_API_TOKEN set."
        )

    # When bound to loopback we keep allow_public_bind=False so the
    # middleware defensively rejects any client that somehow reaches us
    # off-loopback. Only flip it on for a deliberate public bind.
    app = create_app(token=token, allow_public_bind=is_public and allow_public_bind)
    uvicorn.run(app, host=host, port=port, log_level="info")


__all__ = [
    "ALL_EVENTS",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "EVENT_EVIDENCE_UPDATED",
    "EVENT_JOB_CREATED",
    "EVENT_JOB_FAILED",
    "EVENT_PUBLISH_READY",
    "EVENT_SCORING_COMPLETED",
    "EVENT_VALIDATION_COMPLETED",
    "EVENT_WORKER_BLOCKED",
    "EVENT_WORKER_COMPLETED",
    "EVENT_WORKER_STARTED",
    "Job",
    "JobStore",
    "create_app",
    "run",
]
