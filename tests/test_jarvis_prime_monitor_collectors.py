from __future__ import annotations

import json

from muse_cli.jarvis_prime.memory_tree import MemoryLayer, MemoryTreeStore
from muse_cli.jarvis_prime.model_scorecard import ModelScorecard, ScorecardBook
from muse_cli.jarvis_prime.monitor_collectors import (
    collect_context,
    collect_memory_contradictions,
    collect_model_failures,
    collect_pending_proposals,
    collect_repo_state,
)


def _fake_git(branch: str, porcelain: str):
    def run(args):
        if args[:2] == ["rev-parse", "--abbrev-ref"]:
            return branch + "\n"
        if args[0] == "status":
            return porcelain
        raise AssertionError(f"unexpected git args {args}")

    return run


def test_repo_state_dirty_with_changed_files() -> None:
    runner = _fake_git("feature", " M a.py\n?? b.py\n")
    state = collect_repo_state(runner=runner)
    assert state is not None
    assert state["branch"] == "feature"
    assert state["dirty"] is True
    assert "a.py" in state["changed_files"]
    assert "b.py" in state["changed_files"]


def test_repo_state_clean() -> None:
    state = collect_repo_state(runner=_fake_git("main", ""))
    assert state is not None
    assert state["dirty"] is False
    assert state["changed_files"] == []


def test_repo_state_unobservable_is_none() -> None:
    def boom(args):
        raise RuntimeError("no git")

    assert collect_repo_state(runner=boom) is None


def test_memory_contradictions_from_store(tmp_path) -> None:
    store = MemoryTreeStore(path=tmp_path / "m.jsonl")
    for text in ("We deploy on Friday.", "We deploy on Monday."):
        store.write(
            text,
            namespace="jarvis/decisions",
            title="deploy-day",
            subject="deploy-day",
            layer=MemoryLayer.DURABLE,
            confidence=0.9,
            owner_approved=True,
        )
    found = collect_memory_contradictions(store=store)
    assert found == ["deploy-day"]


def test_model_failures_from_book(tmp_path) -> None:
    book = ScorecardBook(path=tmp_path / "s.jsonl")
    book.record(
        ModelScorecard("good", "x", "coding", tests_passed=5, tests_failed=0),
        persist=False,
    )
    book.record(
        ModelScorecard("bad", "x", "coding", tests_passed=1, tests_failed=4),
        persist=False,
    )
    fails = collect_model_failures(book=book)
    assert fails is not None
    assert any("bad" in f for f in fails)
    assert not any("good" in f for f in fails)


def test_pending_proposals_none_when_missing(tmp_path) -> None:
    assert collect_pending_proposals(tmp_path / "nope.jsonl") is None


def test_pending_proposals_counts_open(tmp_path) -> None:
    path = tmp_path / "proposals.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps({"status": "needs_owner_approval", "kind": "skill_update"})
            + "\n"
        )
        fh.write(json.dumps({"status": "applied", "kind": "agent_update"}) + "\n")
    pending = collect_pending_proposals(path)
    assert pending is not None
    assert len(pending) == 1


def test_collect_context_includes_only_observable(tmp_path) -> None:
    store = MemoryTreeStore(path=tmp_path / "m.jsonl")
    store.write(
        "note", namespace="jarvis/general", title="n", layer=MemoryLayer.SESSION
    )
    context = collect_context(
        memory_store_path=tmp_path / "m.jsonl",
        scorecard_path=tmp_path / "missing-s.jsonl",
        git_runner=_fake_git("main", ""),
        test_results={"passed": 3, "failed": []},
    )
    assert "repo" in context
    assert "open_contradictions" in context
    assert "tests" in context
    # open_prs / docs / android intentionally absent → blind spots downstream
    assert "open_prs" not in context
    assert "docs" not in context
