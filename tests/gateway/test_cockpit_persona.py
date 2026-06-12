"""Tests for the adopted-character persona ("make my avatar Goku")."""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway.cockpit import handlers as h
from gateway.cockpit import persona_store as ps


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


def test_generate_persists_and_directive(home, monkeypatch) -> None:
    # No model reachable here → honest fallback persona, still persisted + usable.
    data = ps.generate_persona("Goku from Dragon Ball", name="Goku")
    assert data["name"] == "Goku"
    assert "Goku" in data["description"]
    assert ps.load_persona()["name"] == "Goku"  # ty: ignore[not-subscriptable]
    directive = ps.persona_directive()
    assert directive.startswith("Adopted persona — speak and behave as Goku")
    assert "Goku" in directive


def test_generate_uses_model_when_available(home, monkeypatch) -> None:
    # Inject a fake auxiliary_client so the lazy import resolves to it (the real
    # module pulls heavy deps not present in this slim test env).
    import sys
    import types

    fake = types.ModuleType("agent.auxiliary_client")

    class _Msg:
        content = "You are Goku: cheerful, brave, loves to train and eat."

    class _Resp:
        choices = [type("C", (), {"message": _Msg()})()]

    fake.call_llm = lambda **kw: _Resp()  # ty: ignore[unresolved-attribute]
    monkeypatch.setitem(sys.modules, "agent.auxiliary_client", fake)

    data = ps.generate_persona("Goku", name="Goku")
    assert data["generated"] is True
    assert "cheerful" in data["persona_prompt"]


def test_empty_description_rejected(home) -> None:
    with pytest.raises(ValueError):
        ps.generate_persona("")


def test_directive_empty_when_unset(home) -> None:
    assert ps.persona_directive() == ""


def test_handler_set_get_clear(home) -> None:
    set_resp = h.avatar_persona_set(
        h.Request(method="POST", path="x", body={"description": "a sarcastic cat", "name": "Mochi"})
    )
    assert set_resp.status == 201
    assert set_resp.payload["name"] == "Mochi"

    get_resp = h.avatar_persona_get(h.Request(method="GET", path="x"))
    assert get_resp.status == 200
    assert get_resp.payload["name"] == "Mochi"

    clear_resp = h.avatar_persona_set(h.Request(method="POST", path="x", body={"description": ""}))
    assert clear_resp.status == 200
    assert clear_resp.payload["cleared"] is True
    assert ps.load_persona() is None
