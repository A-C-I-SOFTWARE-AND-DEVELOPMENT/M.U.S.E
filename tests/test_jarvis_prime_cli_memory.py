"""CLI subcommands for memory correction/deletion (B3 from final release review)."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from hermes_cli.jarvis_prime.__main__ import main as cli_main


def _run(argv: list[str]) -> tuple[int, Any]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli_main(argv)
    out = buf.getvalue().strip()
    return code, (json.loads(out) if out else {})


@pytest.fixture(autouse=True)
def _isolated_memory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Force MemoryStore to journal under tmp so tests don't touch ~/.hermes."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # The default_factory in MemoryStore reads os.path.expanduser("~"); HOME
    # override is sufficient on POSIX. On Windows pytest's monkeypatch sets
    # USERPROFILE too.
    monkeypatch.setenv("USERPROFILE", str(tmp_path))


def test_remember_then_recollect() -> None:
    code, body = _run(["remember", "--key", "mission", "--value", "ship v1"])
    assert code == 0
    assert body["stored"] is True

    code, hits = _run(["recollect", "mission"])
    assert code == 0
    assert any(h["key"] == "mission" and h["value"] == "ship v1" for h in hits)


def test_forget_removes_record() -> None:
    _run(["remember", "--key", "scratch", "--value", "delete-me"])
    code, body = _run(["forget", "--key", "scratch"])
    assert code == 0
    assert body["removed"] >= 1


def test_remember_rejects_secret_like_value() -> None:
    code, body = _run(
        [
            "remember",
            "--key",
            "leak",
            "--value",
            "api_key=sk-abcdefghijklmnopqrstuvwx",
        ]
    )
    assert code == 1
    assert body["stored"] is False


def test_stop_subcommand_emits_clear_report() -> None:
    code, body = _run(["stop", "--reason", "test"])
    assert code == 0
    assert body["tick_disabled"] is True
    assert body["reason"] == "test"
    assert body["cleared"] == 0
