"""Tolerant ICS (iCalendar / RFC 5545) VEVENT parser (CAL-1).

A deliberately small, dependency-free reader for the subset of iCalendar that
matters for an agenda: ``VEVENT`` blocks with ``SUMMARY``, ``DTSTART``,
``DTEND``, ``LOCATION``, ``DESCRIPTION``, ``UID``, and a verbatim ``RRULE``.

Design choices:
* **Fail-soft per event.** A property we can't parse (e.g. a date in a shape we
  don't recognise) drops that field, and a ``VEVENT`` with no usable start is
  skipped — a single bad event never sinks the whole file.
* **Line unfolding** per RFC 5545 §3.1: a line beginning with a space or tab is
  a continuation of the previous line.
* **Naive datetimes.** ``Z`` (UTC) is honoured; ``TZID`` and floating times are
  treated as naive local — good enough for a local agenda, and explicitly not a
  timezone library. Callers compare against a ``now`` of matching awareness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class CalendarEvent:
    """One calendar entry. ``start``/``end`` are ``datetime`` (date-times) or
    ``date`` (all-day). ``all_day`` distinguishes the two for rendering."""

    summary: str
    start: object  # datetime | date
    end: Optional[object] = None  # datetime | date | None
    location: str = ""
    description: str = ""
    uid: str = ""
    rrule: str = ""
    all_day: bool = False

    def start_dt(self) -> datetime:
        """Coerce ``start`` to a datetime for comparison (midnight for dates)."""
        return _as_datetime(self.start)


def _unfold(text: str) -> list[str]:
    """RFC 5545 line unfolding: a leading space/tab continues the prior line."""
    out: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and out:
            out[-1] += raw[1:]
        else:
            out.append(raw)
    return out


def _split_prop(line: str) -> tuple[str, dict[str, str], str]:
    """Split ``NAME;PARAM=VAL:value`` into (name, params, value)."""
    if ":" not in line:
        return "", {}, ""
    head, value = line.split(":", 1)
    parts = head.split(";")
    name = parts[0].strip().upper()
    params: dict[str, str] = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.strip().upper()] = v.strip()
    return name, params, value


def _unescape(value: str) -> str:
    """Reverse RFC 5545 text escaping (\\n, \\, comma, semicolon)."""
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def _parse_dt(value: str, params: dict[str, str]) -> tuple[Optional[object], bool]:
    """Parse a DTSTART/DTEND value. Returns ``(value_or_None, all_day)``."""
    value = value.strip()
    is_date = params.get("VALUE", "").upper() == "DATE" or (
        len(value) == 8 and value.isdigit()
    )
    try:
        if is_date:
            return date(int(value[0:4]), int(value[4:6]), int(value[6:8])), True
        if value.endswith("Z"):
            dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ")
            return dt.replace(tzinfo=timezone.utc), False
        return datetime.strptime(value, "%Y%m%dT%H%M%S"), False
    except (ValueError, IndexError):
        return None, False


def parse_ics(text: str) -> list[CalendarEvent]:
    """Parse ICS text into a list of :class:`CalendarEvent` (fail-soft)."""
    events: list[CalendarEvent] = []
    cur: Optional[dict] = None
    for line in _unfold(text or ""):
        stripped = line.strip()
        if stripped == "BEGIN:VEVENT":
            cur = {}
            continue
        if stripped == "END:VEVENT":
            if cur is not None:
                ev = _finalize(cur)
                if ev is not None:
                    events.append(ev)
            cur = None
            continue
        if cur is None:
            continue
        name, params, value = _split_prop(line)
        if not name:
            continue
        if name == "SUMMARY":
            cur["summary"] = _unescape(value)
        elif name == "LOCATION":
            cur["location"] = _unescape(value)
        elif name == "DESCRIPTION":
            cur["description"] = _unescape(value)
        elif name == "UID":
            cur["uid"] = value.strip()
        elif name == "RRULE":
            cur["rrule"] = value.strip()
        elif name == "DTSTART":
            dt, all_day = _parse_dt(value, params)
            if dt is not None:
                cur["start"] = dt
                cur["all_day"] = all_day
        elif name == "DTEND":
            dt, _ = _parse_dt(value, params)
            if dt is not None:
                cur["end"] = dt
    return events


def _finalize(raw: dict) -> Optional[CalendarEvent]:
    start = raw.get("start")
    if start is None:
        return None  # an event with no usable start is not an agenda item
    return CalendarEvent(
        summary=raw.get("summary", "(no title)"),
        start=start,
        end=raw.get("end"),
        location=raw.get("location", ""),
        description=raw.get("description", ""),
        uid=raw.get("uid", ""),
        rrule=raw.get("rrule", ""),
        all_day=bool(raw.get("all_day", False)),
    )


def parse_ics_file(path: Path | str) -> list[CalendarEvent]:
    """Parse an ICS file from disk. Missing/unreadable file → empty list."""
    try:
        return parse_ics(Path(path).read_text(encoding="utf-8"))
    except OSError:
        return []


def _as_datetime(value: object) -> datetime:
    """Coerce a ``date`` or ``datetime`` to a ``datetime`` (midnight for dates)."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    raise TypeError(f"not a date/datetime: {value!r}")
