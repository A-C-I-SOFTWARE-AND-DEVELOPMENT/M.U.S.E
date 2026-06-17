"""Second Brain augments ``build_context_handoff`` only when opted in.

Default-off ⇒ the packet is unchanged and the bridge is never consulted. Enabled
with a fake available brain ⇒ a screened ``## second brain`` section appears;
enabled-but-unavailable ⇒ an honest note, never an exception.
"""

from __future__ import annotations

import pytest

from hermes_cli.jarvis_prime import second_brain_bridge as sbb
from hermes_cli.jarvis_prime.context_handoff import build_context_handoff
from hermes_cli.jarvis_prime.second_brain_bridge import RetrievedContext


def test_handoff_omits_second_brain_when_disabled(monkeypatch) -> None:
    monkeypatch.delenv("MUSE_SECOND_BRAIN", raising=False)
    monkeypatch.setattr(
        sbb,
        "retrieve_optional",
        lambda *a, **k: pytest.fail("retrieve_optional called while disabled"),
    )
    h = build_context_handoff("add a route", repo_root=".")
    assert h.second_brain == []
    assert "## second brain" not in h.render()
    assert "second_brain" in h.to_dict()  # field always present in the dict view


def test_handoff_includes_second_brain_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("MUSE_SECOND_BRAIN", "1")
    monkeypatch.setattr(sbb, "is_available", lambda: True)
    monkeypatch.setattr(
        sbb,
        "retrieve_optional",
        lambda request, **k: RetrievedContext(
            text="routing lives in task_router.py\nlanes are owner-gated",
            block_count=2,
        ),
    )
    h = build_context_handoff("add a route", repo_root=".")
    assert any("routing lives in" in s for s in h.second_brain)
    assert "## second brain" in h.render()


def test_handoff_notes_when_enabled_but_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("MUSE_SECOND_BRAIN", "1")
    monkeypatch.setattr(sbb, "is_available", lambda: False)
    h = build_context_handoff("add a route", repo_root=".")
    assert h.second_brain == []
    assert any(
        "second brain enabled but module not importable" in n for n in h.notes
    )
