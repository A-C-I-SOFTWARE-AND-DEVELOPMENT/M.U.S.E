"""Local orchestrator controller for the Hermes CLI.

Provides Python-level entry points for the Phase 16 native slash commands:

  * ``/orchestrate <prompt>``
  * ``/orchestrator status [job-id]``
  * ``/orchestrator list``
  * ``/orchestrator open <job-id>``
  * ``/orchestrator resume <job-id>``
  * ``/orchestrator publish <job-id>``
  * ``/model-router explain <prompt>``
  * ``/decision-ledger show [job-id]``
  * ``/ai-radar update``
  * ``/best-coding-tool-mission status``

The controller is intentionally minimal: it owns local job bookkeeping and
returns formatted strings so the CLI dispatcher and the gateway can render
them without duplicating logic.  It deliberately stops short of executing
agents — every "go" path is gated and surfaces an instructional message
until config + approval are wired.  This mirrors the local-orchestrator
contract documented in ``docs/hermes-local-orchestrator.md``: Hermes
prepares hand-off material; the user is the one who launches anything that
actually moves money, code, or messages.
"""

from __future__ import annotations

import json
import os
import shlex
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional


# ---------------------------------------------------------------------------
# Storage layout
# ---------------------------------------------------------------------------

_ORCHESTRATOR_DIR_NAME = "orchestrator"
_JOBS_FILE = "jobs.json"
_LEDGER_FILE = "decision_ledger.json"
_RADAR_FILE = "ai_radar.json"
_MISSION_FILE = "best_coding_tool_mission.json"


def _hermes_home() -> Path:
    """Return the active Hermes home directory.

    Imported lazily so tests that point ``HERMES_HOME`` at a tmpdir before
    importing this module still pick up the override.
    """
    try:
        from hermes_constants import get_hermes_home
        return get_hermes_home()
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes"))


def _orch_dir() -> Path:
    d = _hermes_home() / _ORCHESTRATOR_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Job dataclass + JSON persistence
# ---------------------------------------------------------------------------

JOB_STATUSES = ("queued", "running", "paused", "succeeded", "failed", "published")


@dataclass
class Job:
    """A single orchestrator job.

    The orchestrator stores a small flat record per job.  Tool calls,
    model decisions, and validator output live in the decision ledger
    (keyed by ``job.id``).
    """

    id: str
    prompt: str
    status: str = "queued"
    created_at: int = 0
    updated_at: int = 0
    notes: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    published_at: Optional[int] = None
    resumed_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        # Tolerate unknown keys so future schema additions don't crash
        # older readers (this file may be hand-edited).
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in data.items() if k in known}
        kwargs.setdefault("id", data.get("id") or _new_job_id())
        kwargs.setdefault("prompt", data.get("prompt") or "")
        return cls(**kwargs)


def _new_job_id() -> str:
    return f"orc-{uuid.uuid4().hex[:8]}"


_LAST_NOW = 0  # monotonic increment guard for _now() ties


def _now() -> int:
    """Return a strictly-increasing Unix time stamp (microseconds).

    Microsecond resolution + a monotonic-increment guard guarantees that
    two submissions inside the same loop tick still get distinct
    ``created_at`` values — which is what ``list_jobs`` relies on to
    order results newest-first.  Without the guard, fast scripts and
    tests can submit several jobs inside the same wall-clock tick and
    the listing order becomes implementation-defined.
    """
    global _LAST_NOW
    candidate = time.time_ns() // 1_000  # microseconds
    if candidate <= _LAST_NOW:
        candidate = _LAST_NOW + 1
    _LAST_NOW = candidate
    return candidate


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _load_jobs() -> list[Job]:
    raw = _read_json(_orch_dir() / _JOBS_FILE, default=[])
    if not isinstance(raw, list):
        return []
    jobs: list[Job] = []
    for entry in raw:
        if isinstance(entry, dict):
            try:
                jobs.append(Job.from_dict(entry))
            except Exception:
                continue
    return jobs


def _save_jobs(jobs: Iterable[Job]) -> None:
    _write_json(_orch_dir() / _JOBS_FILE, [j.to_dict() for j in jobs])


def _find_job(jobs: list[Job], job_id: str) -> Optional[Job]:
    job_id = (job_id or "").strip()
    if not job_id:
        return None
    for j in jobs:
        if j.id == job_id:
            return j
    # Allow prefix match so users can type the first few chars of a UUID.
    matches = [j for j in jobs if j.id.startswith(job_id)]
    if len(matches) == 1:
        return matches[0]
    return None


# ---------------------------------------------------------------------------
# Decision ledger
# ---------------------------------------------------------------------------

def _load_ledger() -> dict[str, list[dict[str, Any]]]:
    raw = _read_json(_orch_dir() / _LEDGER_FILE, default={})
    if not isinstance(raw, dict):
        return {}
    return {
        str(k): list(v) if isinstance(v, list) else []
        for k, v in raw.items()
    }


def _save_ledger(ledger: dict[str, list[dict[str, Any]]]) -> None:
    _write_json(_orch_dir() / _LEDGER_FILE, ledger)


def _append_ledger(job_id: str, entry: dict[str, Any]) -> None:
    ledger = _load_ledger()
    ledger.setdefault(job_id, []).append({"ts": _now(), **entry})
    _save_ledger(ledger)


# ---------------------------------------------------------------------------
# Public controller API — used by both CLI and gateway dispatchers
# ---------------------------------------------------------------------------

def submit_job(prompt: str) -> Job:
    """Record a new orchestration job.

    Does **not** spawn any workers — workers require explicit configuration
    + approval (see ``docs/orchestration/orchestrator-command-reference.md``).
    """
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("/orchestrate requires a prompt")
    job = Job(id=_new_job_id(), prompt=prompt, status="queued",
              created_at=_now(), updated_at=_now())
    jobs = _load_jobs()
    jobs.append(job)
    _save_jobs(jobs)
    _append_ledger(job.id, {"kind": "submit", "prompt": prompt})
    return job


def list_jobs(limit: int = 25) -> list[Job]:
    jobs = _load_jobs()
    jobs.sort(key=lambda j: j.created_at, reverse=True)
    return jobs[: max(1, int(limit))]


def get_job(job_id: str) -> Optional[Job]:
    return _find_job(_load_jobs(), job_id)


def resume_job(job_id: str) -> Optional[Job]:
    jobs = _load_jobs()
    job = _find_job(jobs, job_id)
    if not job:
        return None
    job.status = "queued" if job.status in {"paused", "failed"} else job.status
    job.resumed_count += 1
    job.updated_at = _now()
    _save_jobs(jobs)
    _append_ledger(job.id, {"kind": "resume", "status": job.status})
    return job


def publish_job(job_id: str) -> Optional[Job]:
    jobs = _load_jobs()
    job = _find_job(jobs, job_id)
    if not job:
        return None
    job.status = "published"
    job.published_at = _now()
    job.updated_at = _now()
    _save_jobs(jobs)
    _append_ledger(job.id, {"kind": "publish"})
    return job


def get_ledger(job_id: Optional[str] = None) -> dict[str, list[dict[str, Any]]]:
    ledger = _load_ledger()
    if not job_id:
        return ledger
    job = get_job(job_id)
    if not job:
        return {}
    return {job.id: ledger.get(job.id, [])}


# ---------------------------------------------------------------------------
# Model router — explain-only stub
# ---------------------------------------------------------------------------

_ROUTING_RULES: tuple[tuple[str, str, str], ...] = (
    # (keyword, route, rationale)
    ("review", "reviewer-profile", "code review prompts go to the reviewer profile"),
    ("debug", "debug-profile", "debugging prompts go to the debug profile"),
    ("refactor", "builder-profile", "refactor prompts go to the builder profile"),
    ("design", "architect-profile", "architecture prompts go to the architect profile"),
    ("plan", "planner-profile", "planning prompts go to the planner profile"),
    ("test", "tester-profile", "testing prompts go to the tester profile"),
    ("doc", "writer-profile", "documentation prompts go to the writer profile"),
)


def model_router_explain(prompt: str) -> dict[str, Any]:
    """Return the routing decision Hermes would make for *prompt*.

    This is an explain-only surface — the CLI does **not** actually flip
    the live model.  Use ``/model`` for that.
    """
    text = (prompt or "").lower()
    matched: list[tuple[str, str]] = []
    for kw, route, rationale in _ROUTING_RULES:
        if kw in text:
            matched.append((route, rationale))
    if not matched:
        return {
            "route": "default-profile",
            "rationale": "no routing keywords matched; falling back to the active profile",
            "matched_keywords": [],
        }
    return {
        "route": matched[0][0],
        "rationale": matched[0][1],
        "matched_keywords": [route for route, _ in matched],
    }


# ---------------------------------------------------------------------------
# AI radar
# ---------------------------------------------------------------------------

def ai_radar_update() -> dict[str, Any]:
    """Record a manual AI-radar refresh and return the new snapshot.

    The real radar pipeline pulls model/provider news from external feeds.
    The CLI surface here just stamps the local file so users can verify
    the orchestrator can write to its own home and the rest of the
    pipeline is reachable.
    """
    path = _orch_dir() / _RADAR_FILE
    payload = {
        "updated_at": _now(),
        "source": "manual /ai-radar update",
        "note": (
            "Local placeholder.  Wire a real feed by setting "
            "orchestrator.ai_radar.feed_url in config.yaml."
        ),
    }
    _write_json(path, payload)
    return payload


def ai_radar_status() -> dict[str, Any]:
    return _read_json(_orch_dir() / _RADAR_FILE, default={"updated_at": 0})


# ---------------------------------------------------------------------------
# "Best coding tool" mission
# ---------------------------------------------------------------------------

def best_coding_tool_mission_status() -> dict[str, Any]:
    """Return the mission status snapshot.

    Mission state is read-only via this command — the orchestrator
    updates it as part of its evaluation runs.  Users can edit the file
    manually under ``$HERMES_HOME/orchestrator/best_coding_tool_mission.json``.
    """
    default = {
        "mission": "Make Hermes the best coding tool for the user's day-to-day work.",
        "metrics": {
            "jobs_submitted": 0,
            "jobs_published": 0,
            "jobs_resumed": 0,
        },
        "next_actions": [
            "Submit a real prompt with /orchestrate <prompt>.",
            "Review the decision ledger with /decision-ledger show.",
        ],
    }
    snapshot = _read_json(_orch_dir() / _MISSION_FILE, default=default)
    # Refresh metrics from live job data so the snapshot is honest even
    # if no-one has hand-edited the JSON file.
    jobs = _load_jobs()
    if isinstance(snapshot, dict):
        snapshot.setdefault("metrics", {})
        snapshot["metrics"].update({
            "jobs_submitted": len(jobs),
            "jobs_published": sum(1 for j in jobs if j.status == "published"),
            "jobs_resumed": sum(j.resumed_count for j in jobs),
        })
    return snapshot if isinstance(snapshot, dict) else default


# ---------------------------------------------------------------------------
# Formatting helpers (used by run_slash + cli.py + gateway/run.py)
# ---------------------------------------------------------------------------

def _fmt_ts(ts: Optional[int]) -> str:
    if not ts:
        return "—"
    # ``_now()`` returns microseconds; convert before handing it to
    # ``time.localtime`` which expects seconds.
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts) / 1_000_000.0))


def _fmt_job_line(job: Job) -> str:
    head = job.prompt.splitlines()[0] if job.prompt else ""
    if len(head) > 72:
        head = head[:69] + "..."
    return f"  {job.id}  {job.status:10s}  {_fmt_ts(job.updated_at)}  {head}"


def _fmt_job_detail(job: Job) -> str:
    lines = [
        f"job:        {job.id}",
        f"status:     {job.status}",
        f"created:    {_fmt_ts(job.created_at)}",
        f"updated:    {_fmt_ts(job.updated_at)}",
        f"resumes:    {job.resumed_count}",
        f"published:  {_fmt_ts(job.published_at) if job.published_at else 'no'}",
        "prompt:",
    ]
    lines.extend(f"  {ln}" for ln in (job.prompt or "").splitlines() or [""])
    if job.notes:
        lines.append("notes:")
        lines.extend(f"  • {n}" for n in job.notes)
    if job.artifacts:
        lines.append("artifacts:")
        lines.extend(f"  • {a}" for a in job.artifacts)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Help blocks (mirrors the kanban run_slash pattern)
# ---------------------------------------------------------------------------

_ORCHESTRATE_HELP = (
    "Usage: /orchestrate <prompt>\n"
    "\n"
    "Records a new orchestration job and assigns it an id.\n"
    "The orchestrator does NOT auto-execute workers — see\n"
    "/orchestrator status <id> to inspect, /orchestrator publish <id>\n"
    "to mark the result as published.\n"
)


_ORCHESTRATOR_HELP = (
    "Usage: /orchestrator <subcommand> [args]\n"
    "\n"
    "Subcommands:\n"
    "  status [job-id]   Show status of one job (or every job).\n"
    "  list              List recent jobs.\n"
    "  open <job-id>     Print a job's full record.\n"
    "  resume <job-id>   Re-queue a paused or failed job.\n"
    "  publish <job-id>  Mark a job as published.\n"
)


_MODEL_ROUTER_HELP = (
    "Usage: /model-router explain <prompt>\n"
    "\n"
    "Explains which model/profile Hermes would route a prompt to.\n"
    "This is an explain-only surface — use /model to actually switch.\n"
)


_DECISION_LEDGER_HELP = (
    "Usage: /decision-ledger show [job-id]\n"
    "\n"
    "Show the decision ledger (submit/resume/publish events, plus any\n"
    "entries written by the orchestrator) for one job or every job.\n"
)


_AI_RADAR_HELP = (
    "Usage: /ai-radar update\n"
    "\n"
    "Refresh the local AI-radar snapshot.\n"
)


_MISSION_HELP = (
    "Usage: /best-coding-tool-mission status\n"
    "\n"
    "Show the orchestrator's running mission summary and live metrics.\n"
)


# ---------------------------------------------------------------------------
# Slash dispatchers
# ---------------------------------------------------------------------------

def run_orchestrate(rest: str) -> str:
    """Handle ``/orchestrate <prompt>``."""
    prompt = (rest or "").strip()
    if not prompt or prompt in {"-h", "--help", "?"}:
        return _ORCHESTRATE_HELP
    try:
        job = submit_job(prompt)
    except ValueError as exc:
        return f"⚠ {exc}\n{_ORCHESTRATE_HELP}"
    return (
        f"✓ Orchestration job queued: {job.id}\n"
        f"  status:  {job.status}\n"
        f"  prompt:  {job.prompt[:120]}{'...' if len(job.prompt) > 120 else ''}\n"
        f"\n"
        f"No worker has started.  Use /orchestrator status {job.id} to inspect."
    )


def _run_orchestrator_status(args: list[str]) -> str:
    if args:
        job = get_job(args[0])
        if not job:
            return f"⚠ /orchestrator: unknown job id {args[0]!r}"
        return _fmt_job_detail(job)
    jobs = list_jobs()
    if not jobs:
        return "  (no jobs yet — use /orchestrate <prompt>)"
    lines = [f"  Orchestrator status — {len(jobs)} job(s)"]
    lines.extend(_fmt_job_line(j) for j in jobs)
    return "\n".join(lines)


def _run_orchestrator_list(_args: list[str]) -> str:
    jobs = list_jobs()
    if not jobs:
        return "  (no jobs yet — use /orchestrate <prompt>)"
    lines = [f"  Recent orchestrator jobs ({len(jobs)}):"]
    lines.extend(_fmt_job_line(j) for j in jobs)
    return "\n".join(lines)


def _run_orchestrator_open(args: list[str]) -> str:
    if not args:
        return "⚠ /orchestrator open requires a job id"
    job = get_job(args[0])
    if not job:
        return f"⚠ /orchestrator: unknown job id {args[0]!r}"
    return _fmt_job_detail(job)


def _run_orchestrator_resume(args: list[str]) -> str:
    if not args:
        return "⚠ /orchestrator resume requires a job id"
    job = resume_job(args[0])
    if not job:
        return f"⚠ /orchestrator: unknown job id {args[0]!r}"
    return (
        f"✓ Job {job.id} re-queued (status={job.status}, "
        f"resumes={job.resumed_count})."
    )


def _run_orchestrator_publish(args: list[str]) -> str:
    if not args:
        return "⚠ /orchestrator publish requires a job id"
    job = publish_job(args[0])
    if not job:
        return f"⚠ /orchestrator: unknown job id {args[0]!r}"
    return (
        f"✓ Job {job.id} marked published at {_fmt_ts(job.published_at)}."
    )


_ORCHESTRATOR_SUBCOMMANDS: dict[str, Any] = {
    "status":  _run_orchestrator_status,
    "list":    _run_orchestrator_list,
    "open":    _run_orchestrator_open,
    "resume":  _run_orchestrator_resume,
    "publish": _run_orchestrator_publish,
}


def run_orchestrator(rest: str) -> str:
    """Handle ``/orchestrator <subcommand> [args]``."""
    rest = (rest or "").strip()
    if not rest or rest in {"-h", "--help", "?", "help"}:
        return _ORCHESTRATOR_HELP
    try:
        tokens = shlex.split(rest)
    except ValueError as exc:
        return f"⚠ /orchestrator: {exc}\n{_ORCHESTRATOR_HELP}"
    sub, *args = tokens
    handler = _ORCHESTRATOR_SUBCOMMANDS.get(sub)
    if not handler:
        return f"⚠ /orchestrator: unknown subcommand {sub!r}\n{_ORCHESTRATOR_HELP}"
    return handler(args)


def run_model_router(rest: str) -> str:
    rest = (rest or "").strip()
    if not rest or rest in {"-h", "--help", "?", "help"}:
        return _MODEL_ROUTER_HELP
    try:
        tokens = shlex.split(rest)
    except ValueError as exc:
        return f"⚠ /model-router: {exc}\n{_MODEL_ROUTER_HELP}"
    sub, *args = tokens
    if sub != "explain":
        return f"⚠ /model-router: unknown subcommand {sub!r}\n{_MODEL_ROUTER_HELP}"
    prompt = " ".join(args).strip()
    if not prompt:
        return _MODEL_ROUTER_HELP
    decision = model_router_explain(prompt)
    matched = decision.get("matched_keywords") or []
    return (
        f"  route:     {decision.get('route')}\n"
        f"  rationale: {decision.get('rationale')}\n"
        f"  matched:   {', '.join(matched) if matched else '—'}"
    )


def run_decision_ledger(rest: str) -> str:
    rest = (rest or "").strip()
    if rest in {"-h", "--help", "?", "help"}:
        return _DECISION_LEDGER_HELP
    if not rest:
        return _DECISION_LEDGER_HELP
    try:
        tokens = shlex.split(rest)
    except ValueError as exc:
        return f"⚠ /decision-ledger: {exc}\n{_DECISION_LEDGER_HELP}"
    sub, *args = tokens
    if sub != "show":
        return f"⚠ /decision-ledger: unknown subcommand {sub!r}\n{_DECISION_LEDGER_HELP}"
    job_id = args[0] if args else None
    ledger = get_ledger(job_id)
    if not ledger:
        return "  (no ledger entries)"
    lines: list[str] = []
    for jid, entries in sorted(ledger.items()):
        lines.append(f"  {jid}  ({len(entries)} entries)")
        for entry in entries:
            kind = entry.get("kind", "?")
            ts = _fmt_ts(entry.get("ts"))
            extras = {k: v for k, v in entry.items() if k not in {"kind", "ts"}}
            extra_str = ""
            if extras:
                # Keep extras compact and on one line for chat surfaces.
                extra_str = "  " + json.dumps(extras, sort_keys=True)
            lines.append(f"    {ts}  {kind}{extra_str}")
    return "\n".join(lines)


def run_ai_radar(rest: str) -> str:
    rest = (rest or "").strip()
    if not rest or rest in {"-h", "--help", "?", "help"}:
        return _AI_RADAR_HELP
    try:
        tokens = shlex.split(rest)
    except ValueError as exc:
        return f"⚠ /ai-radar: {exc}\n{_AI_RADAR_HELP}"
    sub = tokens[0]
    if sub != "update":
        return f"⚠ /ai-radar: unknown subcommand {sub!r}\n{_AI_RADAR_HELP}"
    snapshot = ai_radar_update()
    return (
        "✓ ai-radar snapshot written\n"
        f"  updated_at: {_fmt_ts(snapshot.get('updated_at'))}\n"
        f"  source:     {snapshot.get('source')}\n"
        f"  note:       {snapshot.get('note')}"
    )


def run_best_coding_tool_mission(rest: str) -> str:
    rest = (rest or "").strip()
    if not rest or rest in {"-h", "--help", "?", "help"}:
        return _MISSION_HELP
    try:
        tokens = shlex.split(rest)
    except ValueError as exc:
        return f"⚠ /best-coding-tool-mission: {exc}\n{_MISSION_HELP}"
    sub = tokens[0]
    if sub != "status":
        return (
            f"⚠ /best-coding-tool-mission: unknown subcommand {sub!r}\n"
            f"{_MISSION_HELP}"
        )
    snapshot = best_coding_tool_mission_status()
    metrics = snapshot.get("metrics") or {}
    lines = [
        f"  mission:  {snapshot.get('mission')}",
        "  metrics:",
        f"    jobs_submitted: {metrics.get('jobs_submitted', 0)}",
        f"    jobs_published: {metrics.get('jobs_published', 0)}",
        f"    jobs_resumed:   {metrics.get('jobs_resumed', 0)}",
    ]
    actions = snapshot.get("next_actions") or []
    if actions:
        lines.append("  next actions:")
        lines.extend(f"    • {a}" for a in actions)
    return "\n".join(lines)


__all__ = [
    "Job",
    "JOB_STATUSES",
    "submit_job",
    "list_jobs",
    "get_job",
    "resume_job",
    "publish_job",
    "get_ledger",
    "model_router_explain",
    "ai_radar_update",
    "ai_radar_status",
    "best_coding_tool_mission_status",
    "run_orchestrate",
    "run_orchestrator",
    "run_model_router",
    "run_decision_ledger",
    "run_ai_radar",
    "run_best_coding_tool_mission",
]
