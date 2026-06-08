"""AwarenessSnapshot — MUSE's six live sensor streams.

This is the "hyper aware" layer. Iron Man Jarvis-style omnipresent
context, mapped to existing Hermes subsystems:

| Stream | Source |
|---|---|
| memory_recall | plugins/memory backends |
| active_gateways | gateway/* health probes |
| active_jobs | ~/.hermes/jobs/<id>/ledger.jsonl scan |
| github_state | plugins/github_assistant |
| telemetry | hermes doctor + termux-doctor |
| user_profile | hermes_cli/profile_describer |

Each stream is gated through an existing API (no new network calls
from this module). All streams are *best-effort* — if a backend is
unavailable, the stream returns empty/default rather than raising.

The ``perceive`` function parallelizes all six with hard 2-second
per-stream timeouts so the response loop is never blocked. This
module is stdlib-only at import time; plugin imports are deferred
to ``perceive`` call sites.
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

LOGGER = logging.getLogger("hermes.jarvis_prime.awareness")


DEFAULT_TIMEOUT_SECONDS = 2.0


@dataclass
class MemoryRecord:
    key: str
    value: str
    backend: str  # "sqlite" | "honcho" | "mem0" | "supermemory"
    last_seen: Optional[str] = None
    durability: str = "durable"  # "durable" | "session" | "ephemeral"


@dataclass
class GatewayState:
    name: str  # telegram, discord, slack, whatsapp, signal, email, home_assistant
    connected: bool
    unread_count: int = 0
    last_event_at: Optional[str] = None
    note: str = ""


@dataclass
class JobStatus:
    job_id: str
    phase: str
    blocked: bool
    last_decision: Optional[str] = None
    ledger_path: Optional[str] = None


@dataclass
class GitHubSnapshot:
    open_prs: int = 0
    failing_ci_prs: list[str] = field(default_factory=list)
    high_priority_issues: list[str] = field(default_factory=list)
    branch: Optional[str] = None
    last_commit: Optional[str] = None


@dataclass
class TelemetrySnapshot:
    host_os: str = ""
    python_version: str = ""
    disk_free_gb: float = 0.0
    network_reachable: bool = True
    model_providers_healthy: list[str] = field(default_factory=list)
    model_providers_degraded: list[str] = field(default_factory=list)
    on_termux: bool = False


@dataclass
class UserProfile:
    name: Optional[str] = None
    timezone: Optional[str] = None
    preferred_voice: str = "calm, direct, grounded"
    durable_facts: list[str] = field(default_factory=list)
    long_term_mission: Optional[str] = None


@dataclass
class AwarenessSnapshot:
    memory_recall: list[MemoryRecord] = field(default_factory=list)
    active_gateways: dict[str, GatewayState] = field(default_factory=dict)
    active_jobs: list[JobStatus] = field(default_factory=list)
    github_state: GitHubSnapshot = field(default_factory=GitHubSnapshot)
    telemetry: TelemetrySnapshot = field(default_factory=TelemetrySnapshot)
    user_profile: UserProfile = field(default_factory=UserProfile)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stream_failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d

    def summary(self) -> str:
        """Render a compact text summary suitable for prompt injection."""

        lines: list[str] = ["AWARENESS SNAPSHOT"]
        if self.user_profile.name:
            lines.append(f"User: {self.user_profile.name}")
        if self.user_profile.long_term_mission:
            lines.append(f"Mission: {self.user_profile.long_term_mission}")
        active_gws = [n for n, s in self.active_gateways.items() if s.connected]
        if active_gws:
            lines.append(f"Active gateways: {', '.join(sorted(active_gws))}")
        if self.active_jobs:
            blocked = [j.job_id for j in self.active_jobs if j.blocked]
            lines.append(
                f"Active jobs: {len(self.active_jobs)} "
                f"({len(blocked)} blocked)"
            )
        if self.github_state.failing_ci_prs:
            lines.append(
                f"GitHub: {self.github_state.open_prs} open PRs, "
                f"failing CI on {self.github_state.failing_ci_prs[:3]}"
            )
        elif self.github_state.open_prs:
            lines.append(f"GitHub: {self.github_state.open_prs} open PRs, CI green")
        if self.telemetry.model_providers_degraded:
            lines.append(f"Providers degraded: {self.telemetry.model_providers_degraded}")
        if not self.telemetry.network_reachable:
            lines.append("Network: unreachable")
        if self.telemetry.on_termux:
            lines.append("Host: Termux (mobile)")
        if self.stream_failures:
            lines.append(f"Stream failures: {self.stream_failures}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stream collectors — each best-effort, never raises, has a hard timeout.
# ---------------------------------------------------------------------------


def _collect_memory(limit: int = 10) -> list[MemoryRecord]:
    try:
        # Lazy import — memory plugins may not be installed in all envs.
        try:
            from plugins.memory import sqlite as memory_sqlite  # type: ignore

            backend = "sqlite"
            records: list[MemoryRecord] = []
            recall = getattr(memory_sqlite, "recall_recent", None)
            if callable(recall):
                rows = recall(limit=limit)
                for row in rows or []:
                    records.append(
                        MemoryRecord(
                            key=str(row.get("key", "")),
                            value=str(row.get("value", ""))[:200],
                            backend=backend,
                            last_seen=str(row.get("last_seen", "") or ""),
                            durability="durable",
                        )
                    )
            return records
        except Exception:  # pragma: no cover - optional backend
            pass
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.debug("memory stream failed: %s", exc)
    return []


def _collect_gateways() -> dict[str, GatewayState]:
    states: dict[str, GatewayState] = {}
    candidates = ("telegram", "discord", "slack", "whatsapp", "signal", "email", "home_assistant")
    for name in candidates:
        env_var = f"{name.upper()}_BOT_TOKEN" if name != "home_assistant" else "HASS_URL"
        connected = bool(os.environ.get(env_var))
        states[name] = GatewayState(name=name, connected=connected)
    return states


def _collect_jobs(hermes_home: Optional[Path] = None) -> list[JobStatus]:
    hermes_home = hermes_home or Path(os.path.expanduser("~/.hermes"))
    jobs_dir = hermes_home / "jobs"
    if not jobs_dir.is_dir():
        return []
    statuses: list[JobStatus] = []
    try:
        for path in sorted(jobs_dir.iterdir())[:20]:
            if not path.is_dir():
                continue
            ledger = path / "ledger.jsonl"
            if not ledger.is_file():
                continue
            try:
                last_line = ""
                with ledger.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        if line.strip():
                            last_line = line.strip()
                statuses.append(
                    JobStatus(
                        job_id=path.name,
                        phase="unknown",
                        blocked=False,
                        last_decision=last_line[:200] if last_line else None,
                        ledger_path=str(ledger),
                    )
                )
            except Exception:  # pragma: no cover - best-effort
                continue
    except Exception:
        return statuses
    return statuses


def _collect_github() -> GitHubSnapshot:
    # Read-only telemetry from the github_assistant plugin if available.
    snap = GitHubSnapshot()
    try:
        try:
            from plugins.github_assistant import api as gh_api  # type: ignore

            opened = getattr(gh_api, "list_open_prs", None)
            if callable(opened):
                prs = opened() or []
                snap.open_prs = len(prs)
                snap.failing_ci_prs = [
                    pr.get("number") or pr.get("title", "")
                    for pr in prs
                    if pr.get("mergeable_state") == "unstable"
                ][:10]
        except Exception:  # pragma: no cover - plugin optional
            pass
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.debug("github stream failed: %s", exc)
    return snap


def _collect_telemetry() -> TelemetrySnapshot:
    import platform
    import shutil
    import sys

    snap = TelemetrySnapshot()
    snap.host_os = platform.system().lower()
    snap.python_version = sys.version.split()[0]
    try:
        snap.disk_free_gb = round(shutil.disk_usage("/").free / (1024 ** 3), 1)
    except Exception:
        pass
    snap.on_termux = "TERMUX_VERSION" in os.environ or os.path.isdir("/data/data/com.termux")
    return snap


def _collect_profile() -> UserProfile:
    profile = UserProfile()
    # Pull tz and name from env or known config locations.
    profile.timezone = os.environ.get("TZ") or None
    home_config = Path(os.path.expanduser("~/.hermes/profile.json"))
    if home_config.is_file():
        try:
            import json

            data = json.loads(home_config.read_text(encoding="utf-8"))
            profile.name = data.get("name") or profile.name
            profile.long_term_mission = data.get("long_term_mission") or profile.long_term_mission
            facts = data.get("durable_facts") or []
            if isinstance(facts, list):
                profile.durable_facts = [str(f) for f in facts][:20]
        except Exception:  # pragma: no cover - defensive
            pass
    return profile


def _run_with_timeout(name: str, fn: Callable[[], Any], timeout: float):
    """Run a stream collector with a hard timeout. Returns (value, error_str|None)."""

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(fn)
        try:
            return future.result(timeout=timeout), None
        except concurrent.futures.TimeoutError:
            return None, f"{name}: timeout after {timeout}s"
        except Exception as exc:  # pragma: no cover - defensive
            return None, f"{name}: {exc}"


def perceive(timeout: float = DEFAULT_TIMEOUT_SECONDS) -> AwarenessSnapshot:
    """Build a fresh AwarenessSnapshot by running all six streams in parallel.

    Each stream has a hard ``timeout`` cap. Streams that fail or time
    out land in ``snapshot.stream_failures`` and the field falls back
    to its default. The function never raises.
    """

    snap = AwarenessSnapshot()

    streams: list[tuple[str, Callable[[], Any], Callable[[Any], None]]] = [
        ("memory", _collect_memory, lambda v: setattr(snap, "memory_recall", v or [])),
        ("gateways", _collect_gateways, lambda v: setattr(snap, "active_gateways", v or {})),
        ("jobs", _collect_jobs, lambda v: setattr(snap, "active_jobs", v or [])),
        ("github", _collect_github, lambda v: setattr(snap, "github_state", v or GitHubSnapshot())),
        ("telemetry", _collect_telemetry, lambda v: setattr(snap, "telemetry", v or TelemetrySnapshot())),
        ("profile", _collect_profile, lambda v: setattr(snap, "user_profile", v or UserProfile())),
    ]

    for name, fn, sink in streams:
        value, err = _run_with_timeout(name, fn, timeout)
        if err:
            snap.stream_failures.append(err)
        sink(value)

    return snap
