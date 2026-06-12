"""Tests for hermes_cli.jarvis_prime.flywheel — events, auto-queue, digest."""

from __future__ import annotations

import json
import time

import pytest

from hermes_cli.jarvis_prime import flywheel as fw


def test_record_success() -> None:
    event = fw.record("agent.action", {"tool": "Bash"}, outcome="success")
    assert event is not None
    assert event["kind"] == "agent.action"
    assert event["payload"] == {"tool": "Bash"}
    assert fw.pending() == []
    assert fw._events_path().is_file()
    assert len(fw._events_path().read_text(encoding="utf-8").splitlines()) == 1


def test_failure_autoqueues() -> None:
    fw.record(
        "agent.action",
        {"summary": "tool blew up"},
        outcome="failure",
        lesson="check args first",
    )
    queued = fw.pending()
    assert len(queued) == 1
    assert queued[0]["source"] == "auto"
    assert queued[0]["summary"] == "tool blew up"


def test_queue_manual() -> None:
    entry = fw.queue_improvement("do X better")
    assert entry is not None
    assert entry["source"] == "manual"
    assert len(entry["id"]) == 12
    int(entry["id"], 16)  # hex
    assert [e["summary"] for e in fw.pending()] == ["do X better"]


def test_digest() -> None:
    fw.record("owner.prompt", {"summary": "hi"})
    fw.record("agent.action", {"tool": "Bash"}, outcome="success")
    fw.record("skill.used", {"skill": "verify"}, outcome="success")
    fw.record("model.routed", {"model": "claude"}, outcome="success")
    fw.record("agent.action", {"summary": "boom"}, outcome="failure", lesson="l1")

    d = fw.digest()
    assert d["total"] == 5
    assert d["by_kind"] == {
        "owner.prompt": 1,
        "agent.action": 2,
        "skill.used": 1,
        "model.routed": 1,
    }
    assert d["by_outcome"] == {"none": 1, "success": 3, "failure": 1}
    assert d["recent_failures"][-1]["lesson"] == "l1"
    assert d["pending_improvements"] == 1

    # An event outside the window is excluded.
    old = {
        "v": 1,
        "ts": time.time() - 7200,
        "kind": "agent.action",
        "payload": {},
        "outcome": None,
        "lesson": None,
    }
    with open(fw._events_path(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(old) + "\n")
    assert fw.digest(hours=1.0)["total"] == 5


def test_soft_fail_never_raises(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Occupy the would-be flywheel *directory* path with a file.
    blocker = tmp_path / "blocked-home"
    blocker.mkdir()
    (blocker / "flywheel").write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(blocker))

    assert fw.record("agent.action", {}) is None
    assert fw.queue_improvement("x") is None
    assert fw.pending() == []
    assert fw.digest()["total"] == 0


def test_cli(capsys: pytest.CaptureFixture) -> None:
    assert fw.main(["digest"]) == 0
    assert json.loads(capsys.readouterr().out)["total"] == 0
    assert fw.main(["pending"]) == 0
    assert json.loads(capsys.readouterr().out) == []

    fw.record("agent.action", {"summary": "boom"}, outcome="failure")
    assert fw.main(["digest", "--hours", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["pending_improvements"] == 1


def test_file_pending_to_plans(tmp_path) -> None:
    assert fw.file_pending_to_plans(str(tmp_path / "plans")) is None  # empty queue
    fw.queue_improvement("fix the frobnicator")
    path = fw.file_pending_to_plans(str(tmp_path / "plans"))
    assert path is not None and path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "fix the frobnicator" in text
    # Filing copies, never drains: the entry is still pending.
    assert len(fw.pending()) == 1


def test_tool_dispatch_failure_lands_in_flywheel() -> None:
    from model_tools import _flywheel_record_action

    _flywheel_record_action("demo_tool", 12, failed=False)
    _flywheel_record_action("demo_tool", None, failed=True, lesson="exploded")
    d = fw.digest()
    assert d["by_kind"].get("agent.action") == 2
    assert d["by_outcome"].get("failure") == 1
    assert fw.pending()  # the failure auto-queued


def test_owner_brief_includes_flywheel_digest() -> None:
    from hermes_cli.jarvis_prime.owner_brief import build_owner_brief

    fw.record("owner.prompt", {"summary": "hi"})
    fw.record("agent.action", {"summary": "boom"}, outcome="failure", lesson="l1")
    brief = build_owner_brief([], flywheel_digest=fw.digest())
    rendered = brief.render()
    assert "Flywheel digest" in rendered
    assert "failure in agent.action: l1" in rendered
    assert brief.to_dict()["flywheel_digest"]

    # No digest supplied -> section absent (module stays I/O-free).
    assert "Flywheel digest" not in build_owner_brief([]).render()
