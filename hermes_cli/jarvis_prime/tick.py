"""Proactive tick — muse's quiet daemon loop.

Runs every N minutes via cron (default 10m, disabled by default).
Only emits a notification when something material has changed
since the last tick. Idempotent: two back-to-back calls produce
exactly one notification.

The tick is the "anticipates blockers before you ask" part of the
Iron Man Jarvis vision — but rate-limited to the briefing window
and material-change events to avoid notification fatigue.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Optional

from hermes_cli.jarvis_prime.awareness import AwarenessSnapshot, perceive

LOGGER = logging.getLogger("hermes.jarvis_prime.tick")


@dataclass
class TickState:
    last_tick_at: Optional[str] = None
    last_failing_ci_prs: list[str] = field(default_factory=list)
    last_briefing_at: Optional[str] = None
    last_blocked_jobs: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "TickState":
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception:  # pragma: no cover - defensive
            return cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


@dataclass
class TickNotification:
    kind: str  # "ci_failure" | "daily_briefing" | "blocked_job" | ...
    title: str
    body: str
    severity: str = "info"  # "info" | "warning" | "alert"


def _is_in_briefing_window(now: datetime, window: str) -> bool:
    # Window like "08:00 America/Toronto" — we only compare HH:MM here;
    # the wall clock is assumed local. The full TZ comparison can be
    # added later when zoneinfo is available across all targets.
    try:
        hhmm, _tz = window.split(maxsplit=1)
        target = time.fromisoformat(hhmm)
    except Exception:
        return False
    return now.hour == target.hour and now.minute < target.minute + 10


def _notify(notification: TickNotification, channel: str) -> None:
    """Deliver a notification — best-effort, never raises.

    Channel handling is intentionally minimal here. Production routes
    deliver via gateway/*; the tick just writes a structured
    notification to the radar inbox.
    """

    if channel == "none":
        LOGGER.info("[notify:%s] %s — %s", notification.severity, notification.title, notification.body)
        return

    radar_inbox = Path(os.path.expanduser("~/.hermes/jarvis_prime/inbox"))
    radar_inbox.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = radar_inbox / f"{stamp}-{notification.kind}.json"
    target.write_text(
        json.dumps(
            {
                "kind": notification.kind,
                "title": notification.title,
                "body": notification.body,
                "severity": notification.severity,
                "channel": channel,
                "emitted_at": stamp,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def run_once(
    state_path: Optional[Path] = None,
    notify_via: str = "none",
    briefing_window: str = "08:00 America/Toronto",
    enabled: bool = False,
) -> list[TickNotification]:
    """Execute one tick. Returns the list of notifications emitted."""

    if not enabled:
        LOGGER.debug("jarvis tick disabled — no-op")
        return []

    state_path = state_path or Path(os.path.expanduser("~/.hermes/jarvis_prime/tick_state.json"))
    state = TickState.load(state_path)
    snap = perceive()
    notifications: list[TickNotification] = []
    now = datetime.now(timezone.utc)

    # CI failure surface
    failing = sorted(snap.github_state.failing_ci_prs)
    new_failing = [pr for pr in failing if pr not in state.last_failing_ci_prs]
    if new_failing:
        notifications.append(
            TickNotification(
                kind="ci_failure",
                title=f"CI failing on {len(new_failing)} PR(s)",
                body=f"PRs: {', '.join(str(p) for p in new_failing)}",
                severity="warning",
            )
        )

    # Blocked job surface
    blocked = sorted(j.job_id for j in snap.active_jobs if j.blocked)
    new_blocked = [j for j in blocked if j not in state.last_blocked_jobs]
    if new_blocked:
        notifications.append(
            TickNotification(
                kind="blocked_job",
                title=f"{len(new_blocked)} orchestrator job(s) newly blocked",
                body=f"Jobs: {', '.join(new_blocked)}",
                severity="warning",
            )
        )

    # Daily briefing — only once per window
    if _is_in_briefing_window(now, briefing_window):
        last_briefing = state.last_briefing_at
        today_key = now.strftime("%Y-%m-%d")
        if not last_briefing or not last_briefing.startswith(today_key):
            notifications.append(
                TickNotification(
                    kind="daily_briefing",
                    title=f"muse briefing — {today_key}",
                    body=snap.summary(),
                    severity="info",
                )
            )
            state.last_briefing_at = now.isoformat()

    # Deliver
    for note in notifications:
        _notify(note, channel=notify_via)

    # Persist state
    state.last_tick_at = now.isoformat()
    state.last_failing_ci_prs = failing
    state.last_blocked_jobs = blocked
    state.save(state_path)

    return notifications
