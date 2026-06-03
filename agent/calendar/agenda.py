"""Agenda queries over parsed calendar events (CAL-1).

Pure functions — no I/O, no clock of their own (the caller passes ``now`` so
tests are deterministic). Naive datetimes are treated as UTC for comparison so
a mixed file (some events ``Z``-suffixed, some floating) still orders sanely.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from .ics import CalendarEvent


def _aware_utc(dt: datetime) -> datetime:
    """Return ``dt`` as an aware UTC datetime (assume UTC when naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def upcoming(
    events: Iterable[CalendarEvent],
    *,
    now: datetime,
    within: timedelta = timedelta(days=7),
) -> list[CalendarEvent]:
    """Events starting in the window ``[now, now + within]``, soonest first.

    An event already in progress (started before ``now``) is excluded — this is
    a forward-looking agenda. Use ``on_day`` for "what's happening today".
    """
    now_u = _aware_utc(now)
    horizon = now_u + within
    kept = [
        e
        for e in events
        if now_u <= _aware_utc(e.start_dt()) <= horizon
    ]
    return sorted(kept, key=lambda e: _aware_utc(e.start_dt()))


def on_day(
    events: Iterable[CalendarEvent], *, day: datetime
) -> list[CalendarEvent]:
    """Events whose start falls on the calendar day of ``day`` (UTC), sorted."""
    day_u = _aware_utc(day)
    target = day_u.date()
    kept = [e for e in events if _aware_utc(e.start_dt()).date() == target]
    return sorted(kept, key=lambda e: _aware_utc(e.start_dt()))


def _fmt(e: CalendarEvent) -> str:
    when = e.start
    if e.all_day:
        stamp = when.strftime("%Y-%m-%d (all day)")
    else:
        stamp = e.start_dt().strftime("%Y-%m-%d %H:%M")
    line = f"  {stamp}  {e.summary}"
    if e.location:
        line += f"  @ {e.location}"
    if e.rrule:
        line += "  [recurring]"
    return line


def render_agenda(events: list[CalendarEvent], *, title: str = "Upcoming") -> str:
    """Human-readable agenda block."""
    if not events:
        return f"{title}: nothing scheduled."
    return "\n".join([f"{title}:", *(_fmt(e) for e in events)])
