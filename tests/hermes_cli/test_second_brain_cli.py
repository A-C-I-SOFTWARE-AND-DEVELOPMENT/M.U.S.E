"""CLI: ``jarvis_prime second-brain`` — status / retrieve / ingest.

Drives the real argparse entrypoint with a fake brain (no database) and asserts
the owner gate on writes, honest degradation when the backend is absent, and that
the status view never leaks the backend password.
"""

from __future__ import annotations

import json

from hermes_cli.jarvis_prime import second_brain_bridge as sbb
from hermes_cli.jarvis_prime.__main__ import main as cli_main
from hermes_cli.jarvis_prime.second_brain_bridge import RetrievedContext


def test_status_default_off(monkeypatch, capsys) -> None:
    monkeypatch.delenv("MUSE_SECOND_BRAIN", raising=False)
    code = cli_main(["second-brain", "status", "--json"])
    assert code == 0
    body = json.loads(capsys.readouterr().out)
    assert body["enabled"] is False
    assert body["available"] is True  # module is importable in-repo
    assert body["enable_env"] == "MUSE_SECOND_BRAIN"


def test_status_enabled_echoes_nonsecret_settings(monkeypatch, capsys) -> None:
    monkeypatch.setenv("MUSE_SECOND_BRAIN", "1")
    monkeypatch.setenv("SECOND_BRAIN_PG_PASSWORD", "super-secret")
    code = cli_main(["second-brain", "status", "--json"])
    assert code == 0
    dumped = capsys.readouterr().out
    body = json.loads(dumped)
    assert body["enabled"] is True
    assert "settings" in body
    assert "super-secret" not in dumped  # the password must never be echoed


def test_retrieve_json_with_fake_context(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sbb, "is_available", lambda: True)
    monkeypatch.setattr(
        sbb,
        "retrieve_optional",
        lambda query, **k: RetrievedContext(text="FUSED", block_count=4),
    )
    code = cli_main(["second-brain", "retrieve", "q", "--json"])
    assert code == 0
    body = json.loads(capsys.readouterr().out)
    assert body == {"text": "FUSED", "block_count": 4, "source": "second_brain"}


def test_retrieve_unavailable_returns_rc1(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sbb, "is_available", lambda: True)
    monkeypatch.setattr(sbb, "retrieve_optional", lambda *a, **k: None)
    code = cli_main(["second-brain", "retrieve", "q"])
    assert code == 1
    assert "backend unavailable" in capsys.readouterr().err


def test_ingest_dry_run(capsys, tmp_path) -> None:
    f = tmp_path / "note.md"
    f.write_text("hello")
    code = cli_main(["second-brain", "ingest", str(f)])
    assert code == 0
    assert "dry-run" in capsys.readouterr().out


def test_ingest_apply_requires_owner_phrase(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.delenv("JARVIS_OWNER_PHRASE", raising=False)
    f = tmp_path / "note.md"
    f.write_text("hello")
    code = cli_main(["second-brain", "ingest", str(f), "--apply"])
    assert code == 3
    assert "owner authorization required" in capsys.readouterr().err


def test_ingest_apply_with_phrase_writes_via_fake_brain(
    monkeypatch, capsys, tmp_path
) -> None:
    from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

    f = tmp_path / "note.md"
    f.write_text("ingest me")
    written: list[tuple] = []

    class _FakeBrain:
        def ingest_text(self, content, source_id, *, title=None, metadata=None):
            written.append((content, source_id, title))

        def close(self):
            pass

    import second_brain.knowledge as sbk

    monkeypatch.setattr(sbb, "is_available", lambda: True)
    monkeypatch.setattr(
        sbk, "SecondBrain", lambda settings, *, enable_graph=False: _FakeBrain()
    )

    code = cli_main(
        ["second-brain", "ingest", str(f), "--apply", "--phrase", AUTHORIZATION_PHRASE]
    )
    assert code == 0
    assert written and written[0][0] == "ingest me"
    assert written[0][2] == "note.md"
