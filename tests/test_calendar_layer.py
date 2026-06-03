"""CAL-1 local-first calendar adapter tests: ICS parse, agenda, provenance."""

from datetime import datetime, timedelta, timezone

from agent.calendar import (
    event_to_memory_event,
    on_day,
    parse_ics,
    parse_ics_file,
    render_agenda,
    upcoming,
)

SAMPLE = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:evt-1
SUMMARY:Standup
DTSTART:20260610T090000Z
DTEND:20260610T091500Z
LOCATION:Zoom
END:VEVENT
BEGIN:VEVENT
UID:evt-2
SUMMARY:All-hands
DTSTART;VALUE=DATE:20260612
RRULE:FREQ=WEEKLY
END:VEVENT
BEGIN:VEVENT
UID:evt-broken
SUMMARY:No start here
END:VEVENT
END:VCALENDAR
"""


# -- parser -----------------------------------------------------------------


def test_parse_extracts_vevents_and_skips_broken():
    events = parse_ics(SAMPLE)
    # evt-broken has no DTSTART → skipped.
    assert len(events) == 2
    by_uid = {e.uid: e for e in events}
    assert by_uid["evt-1"].summary == "Standup"
    assert by_uid["evt-1"].location == "Zoom"
    assert by_uid["evt-1"].all_day is False
    assert by_uid["evt-2"].all_day is True
    assert by_uid["evt-2"].rrule == "FREQ=WEEKLY"


def test_parse_handles_utc_marker():
    e = parse_ics(SAMPLE)[0]
    assert isinstance(e.start, datetime)  # date-time event, not all-day
    assert e.start.tzinfo == timezone.utc
    assert e.start.hour == 9


def test_line_unfolding():
    text = (
        "BEGIN:VEVENT\nUID:u\nSUMMARY:Long title that is\n  folded across lines\n"
        "DTSTART:20260101T120000Z\nEND:VEVENT\n"
    )
    e = parse_ics(text)[0]
    assert e.summary == "Long title that is folded across lines"


def test_escaped_text_unescaped():
    text = (
        "BEGIN:VEVENT\nUID:u\nSUMMARY:A\\, B\\; C\nDESCRIPTION:line1\\nline2\n"
        "DTSTART:20260101T120000Z\nEND:VEVENT\n"
    )
    e = parse_ics(text)[0]
    assert e.summary == "A, B; C"
    assert e.description == "line1\nline2"


def test_parse_garbage_is_failsoft():
    assert parse_ics("") == []
    assert parse_ics("not a calendar at all") == []


def test_parse_missing_file_returns_empty(tmp_path):
    assert parse_ics_file(tmp_path / "nope.ics") == []


def test_parse_file_roundtrip(tmp_path):
    p = tmp_path / "cal.ics"
    p.write_text(SAMPLE, encoding="utf-8")
    assert len(parse_ics_file(p)) == 2


# -- agenda -----------------------------------------------------------------


def test_upcoming_filters_window_and_sorts():
    events = parse_ics(SAMPLE)
    now = datetime(2026, 6, 9, tzinfo=timezone.utc)
    up = upcoming(events, now=now, within=timedelta(days=7))
    assert [e.uid for e in up] == ["evt-1", "evt-2"]  # 6/10 then 6/12


def test_upcoming_excludes_past_and_far_future():
    events = parse_ics(SAMPLE)
    # now after evt-1, window too short to include evt-2
    now = datetime(2026, 6, 11, tzinfo=timezone.utc)
    up = upcoming(events, now=now, within=timedelta(hours=12))
    assert up == []


def test_upcoming_naive_now_treated_as_utc():
    events = parse_ics(SAMPLE)
    up = upcoming(events, now=datetime(2026, 6, 9), within=timedelta(days=7))
    assert len(up) == 2


def test_on_day():
    events = parse_ics(SAMPLE)
    day = datetime(2026, 6, 10, tzinfo=timezone.utc)
    assert [e.uid for e in on_day(events, day=day)] == ["evt-1"]


def test_render_agenda():
    events = parse_ics(SAMPLE)
    out = render_agenda(events)
    assert "Standup" in out and "@ Zoom" in out
    assert "[recurring]" in out  # evt-2 has RRULE
    assert render_agenda([]) == "Upcoming: nothing scheduled."


# -- provenance bridge ------------------------------------------------------


def test_event_to_memory_event_is_trusted_not_owner():
    e = parse_ics(SAMPLE)[0]
    mem = event_to_memory_event(e)
    # Conservative: a local ICS entry is trusted, never owner — so it can't
    # auto-promote to durable memory.
    assert mem.trust_level == "trusted"
    assert mem.user_approval_state == "unreviewed"
    assert "Standup" in mem.content
    assert dict(mem.metadata)["uid"] == "evt-1"


def test_calendar_event_never_auto_promotes():
    from agent.memory_layers import should_auto_promote

    mem = event_to_memory_event(parse_ics(SAMPLE)[0])
    assert should_auto_promote(mem) is False


# -- CLI handler ------------------------------------------------------------


def test_cli_calendar_lists_events(tmp_path, capsys):
    import argparse

    from hermes_cli.jarvis_prime.__main__ import _cmd_calendar

    ics = tmp_path / "cal.ics"
    ics.write_text(
        "BEGIN:VEVENT\nUID:u\nSUMMARY:Future thing\nDTSTART:20990101T100000Z\nEND:VEVENT\n",
        encoding="utf-8",
    )
    ns = argparse.Namespace(file=str(ics), days=10**6, json=False)
    rc = _cmd_calendar(ns)
    assert rc == 0
    assert "Future thing" in capsys.readouterr().out


def test_cli_calendar_missing_file_is_graceful(tmp_path, capsys):
    import argparse

    from hermes_cli.jarvis_prime.__main__ import _cmd_calendar

    ns = argparse.Namespace(file=str(tmp_path / "nope.ics"), days=7, json=False)
    assert _cmd_calendar(ns) == 0
    assert "no ICS file" in capsys.readouterr().out
