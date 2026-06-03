"""Bridge a calendar event into the MEM-1 provenance layer (CAL-1).

A calendar entry read from a local file is *trusted local data the owner
maintains*, but it is not the owner explicitly approving a memory write — so it
maps to ``trusted`` (not ``owner``) and ``unreviewed``. That means it is never
auto-promoted to durable memory; it flows through the same owner-gated curator
bridge as everything else. Keeping the mapping conservative here is the whole
point: a poisoned ICS file (e.g. a malicious meeting invite) cannot write
itself into long-term memory.
"""

from __future__ import annotations

from .ics import CalendarEvent


def event_to_memory_event(event: CalendarEvent, *, source: str = "calendar:local"):
    """Convert a :class:`CalendarEvent` into a MEM-1 ``MemoryEvent``.

    Lazy-imports the memory layer so the calendar package stays importable on
    its own. Trust is ``trusted`` and approval is ``unreviewed`` — promotion
    stays owner-gated.
    """
    from agent.memory_layers import MemoryEvent

    when = event.start_dt().isoformat()
    content = f"calendar event: {event.summary} at {when}"
    if event.location:
        content += f" ({event.location})"
    return MemoryEvent(
        content=content,
        source=source,
        trust_level="trusted",
        user_approval_state="unreviewed",
        metadata=(("uid", event.uid), ("when", when)),
    )
