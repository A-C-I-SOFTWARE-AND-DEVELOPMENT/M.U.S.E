"""Local-first calendar adapter (CAL-1).

A new surface, built local-first and deliberately *without* any external
network or OAuth: it reads an ICS (iCalendar / RFC 5545) file from disk — the
format every calendar app on earth can export — and exposes a small, typed
agenda API. Nothing here phones home; nothing here needs a credential.

Layers (mirrors the memory-layers split so each piece is independently
testable):

* ``ics`` — a tolerant VEVENT parser (line-unfolding, DATE + DATE-TIME, raw
  RRULE capture). Fail-soft: a malformed event is skipped, never raised.
* ``agenda`` — pure time-window queries over parsed events (``upcoming``,
  ``on_day``) plus a human-readable renderer.
* ``provenance`` — bridge a calendar event into a MEM-1 ``MemoryEvent`` at a
  conservative trust level, so the agent can record "what's on the calendar"
  through the same provenance/owner-gated path as everything else.

Deliberately NOT here (owner-gated follow-ups, by design):

* Live two-way sync with Google Calendar / CalDAV. That is a new external
  surface that requires OAuth — an owner gate — and outbound network. It is a
  follow-up, not faked here.
* Recurrence expansion. RRULE is captured verbatim but not expanded; expansion
  is a bounded follow-up that builds on this parser.
"""

from __future__ import annotations

from .agenda import on_day, render_agenda, upcoming
from .ics import CalendarEvent, parse_ics, parse_ics_file
from .provenance import event_to_memory_event

__all__ = [
    "CalendarEvent",
    "parse_ics",
    "parse_ics_file",
    "upcoming",
    "on_day",
    "render_agenda",
    "event_to_memory_event",
]
