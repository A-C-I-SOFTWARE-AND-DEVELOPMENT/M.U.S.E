"""The flywheel — no action wasted, by construction.

Every notable runtime event (owner prompts, agent actions, skill use,
model routing) is appended to ``$HERMES_HOME/flywheel/events.jsonl``;
any event recorded with ``outcome="failure"`` auto-queues an entry in
``improvement_queue.jsonl`` so the system tells you where it failed.
``digest()`` summarizes recent activity; ``pending()`` lists queued
improvements waiting to be drained.

This is a working log, not a court of record — there is no hash chain
here. High-value items get promoted to the axiom_bridge chain by their
callers. Every public function is soft: it never raises into the host.

CLI:
    python -m hermes_cli.jarvis_prime.flywheel digest [--hours H]
    python -m hermes_cli.jarvis_prime.flywheel pending
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

KINDS = ("owner.prompt", "agent.action", "skill.used", "model.routed")

_DIR = "flywheel"
_EVENTS_FILE = "events.jsonl"
_QUEUE_FILE = "improvement_queue.jsonl"


def _hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home  # type: ignore

        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes"))


def _events_path() -> Path:
    return _hermes_home() / _DIR / _EVENTS_FILE


def _queue_path() -> Path:
    return _hermes_home() / _DIR / _QUEUE_FILE


def _append(path: Path, record: Mapping[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")
    return True


def _read(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    records: list[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue  # one corrupt line never hides the rest
    return records


def record(
    kind: str,
    payload: Mapping[str, Any],
    outcome: Optional[str] = None,
    lesson: Optional[str] = None,
) -> Optional[dict]:
    """Append one event; a "failure" outcome auto-queues an improvement.

    Returns the written record, or None on any error (soft-fail).
    """
    try:
        event = {
            "v": 1,
            "ts": time.time(),
            "kind": str(kind),
            "payload": dict(payload),
            "outcome": outcome,
            "lesson": lesson,
        }
        _append(_events_path(), event)
        if outcome == "failure":
            summary = (
                str(dict(payload).get("summary") or "").strip()
                or f"{kind} failed" + (f": {lesson}" if lesson else "")
            )
            queue_improvement(
                summary, kind=str(kind), payload=payload, source="auto"
            )
        return event
    except Exception:
        return None


def queue_improvement(
    summary: str,
    *,
    kind: str = "manual",
    payload: Optional[Mapping[str, Any]] = None,
    source: str = "manual",
) -> Optional[dict]:
    """Add a pending improvement to the queue; None on soft-fail."""
    try:
        ts = time.time()
        entry = {
            "v": 1,
            "id": hashlib.sha256(f"{ts}:{summary}".encode("utf-8")).hexdigest()[:12],
            "ts": ts,
            "source": source,
            "kind": str(kind),
            "summary": str(summary),
            "payload": dict(payload or {}),
            "status": "pending",
        }
        _append(_queue_path(), entry)
        return entry
    except Exception:
        return None


def pending() -> list[dict]:
    """Queue entries still marked pending; [] on soft-fail."""
    try:
        return [e for e in _read(_queue_path()) if e.get("status") == "pending"]
    except Exception:
        return []


def digest(hours: float = 24.0) -> dict:
    """Summarize events in the last *hours*: counts by kind/outcome,
    recent failures (with lessons), and the pending-improvement count."""
    empty = {
        "window_hours": float(hours),
        "total": 0,
        "by_kind": {},
        "by_outcome": {},
        "recent_failures": [],
        "pending_improvements": 0,
    }
    try:
        cutoff = time.time() - float(hours) * 3600.0
        events = [e for e in _read(_events_path()) if e.get("ts", 0) >= cutoff]
        by_kind: dict[str, int] = {}
        by_outcome: dict[str, int] = {}
        failures: list[dict] = []
        for e in events:
            by_kind[e.get("kind", "?")] = by_kind.get(e.get("kind", "?"), 0) + 1
            key = e.get("outcome") or "none"
            by_outcome[key] = by_outcome.get(key, 0) + 1
            if e.get("outcome") == "failure":
                failures.append(
                    {
                        "ts": e.get("ts"),
                        "kind": e.get("kind"),
                        "lesson": e.get("lesson"),
                        "summary": dict(e.get("payload") or {}).get("summary"),
                    }
                )
        return {
            "window_hours": float(hours),
            "total": len(events),
            "by_kind": by_kind,
            "by_outcome": by_outcome,
            "recent_failures": failures[-5:],
            "pending_improvements": len(pending()),
        }
    except Exception:
        return empty


def file_pending_to_plans(
    directory: Optional[str] = None, top: int = 10
) -> Optional[Path]:
    """Write the top pending improvements to a dated plan file.

    Queue entries are copied, not mutated — draining (marking done) is
    the build loop's job, not the filer's. Returns the written path, or
    None when there is nothing pending or on soft-fail.
    """
    try:
        entries = pending()[: max(1, int(top))]
        if not entries:
            return None
        target_dir = Path(directory) if directory else Path(".plans")
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d")
        path = target_dir / f"{stamp}-flywheel-improvements.md"
        lines = [
            f"# Flywheel improvements — filed {stamp}",
            "",
            "Auto-filed from `improvement_queue.jsonl`; drain via the build loop.",
            "",
        ]
        for e in entries:
            lines.append(f"- [ ] `{e.get('id')}` [{e.get('kind')}] {e.get('summary')}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
    except Exception:
        return None


def install_cron_jobs(repo_root: Optional[str] = None) -> Optional[dict]:
    """Register the nightly digest+audit and weekly file-pending cron jobs.

    Jobs are runtime data (``~/.hermes/cron/jobs.json``), so this is an
    explicit installer, not an import side effect. Returns the two job
    dicts, or None on soft-fail.
    """
    try:
        from cron.jobs import create_job

        workdir = repo_root or os.getcwd()
        nightly = create_job(
            prompt=None,
            schedule="0 6 * * *",
            name="Flywheel nightly digest + chain audit",
            script=_install_script(
                "flywheel-nightly.sh",
                "#!/usr/bin/env bash\n"
                "python -m hermes_cli.jarvis_prime.flywheel digest\n"
                "python -m hermes_cli.jarvis_prime.axiom_bridge audit\n",
            ),
            no_agent=True,
            deliver="local",
            workdir=workdir,
        )
        weekly = create_job(
            prompt=None,
            schedule="0 7 * * 1",
            name="Flywheel weekly: file pending improvements to .plans/",
            script=_install_script(
                "flywheel-weekly.sh",
                "#!/usr/bin/env bash\n"
                "python -m hermes_cli.jarvis_prime.flywheel file-pending --dir .plans\n",
            ),
            no_agent=True,
            deliver="local",
            workdir=workdir,
        )
        return {"nightly": nightly, "weekly": weekly}
    except Exception:
        return None


def _install_script(name: str, body: str) -> str:
    """Drop a helper script under ``$HERMES_HOME/scripts/`` (cron's search
    path) and return its name."""
    scripts_dir = _hermes_home() / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    path = scripts_dir / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return name


# ------------------------------------------------------------------------ CLI
def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m hermes_cli.jarvis_prime.flywheel",
        description="Inspect the flywheel event log and improvement queue.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    digest_p = sub.add_parser("digest", help="summary of recent events")
    digest_p.add_argument("--hours", type=float, default=24.0)
    sub.add_parser("pending", help="queued improvements awaiting drain")
    file_p = sub.add_parser(
        "file-pending", help="write top pending improvements to a plan file"
    )
    file_p.add_argument("--dir", default=".plans")
    file_p.add_argument("--top", type=int, default=10)
    cron_p = sub.add_parser(
        "install-cron", help="register the nightly digest and weekly filing jobs"
    )
    cron_p.add_argument("--repo-root", default=None)

    args = parser.parse_args(argv)
    if args.command == "digest":
        print(json.dumps(digest(args.hours), indent=2))
    elif args.command == "pending":
        print(json.dumps(pending(), indent=2))
    elif args.command == "file-pending":
        path = file_pending_to_plans(args.dir, args.top)
        print(json.dumps({"filed": str(path) if path else None}))
    elif args.command == "install-cron":
        jobs = install_cron_jobs(args.repo_root)
        if jobs is None:
            print(json.dumps({"installed": False}))
            return 1
        print(
            json.dumps(
                {
                    "installed": True,
                    "jobs": [
                        {"id": j.get("id"), "name": j.get("name")}
                        for j in jobs.values()
                    ],
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
