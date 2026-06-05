"""Tests for the Swarm Blackboard (stigmergic coordination)."""

from __future__ import annotations

from hermes_cli.swarm.blackboard import SwarmBlackboard


def test_post_and_read_in_process():
    board = SwarmBlackboard("job-1")
    board.post("g1", "found the interface", kind="interface")
    board.post("g2", "blocked on g1", kind="blocker")
    entries = board.read()
    assert [e.grain_id for e in entries] == ["g1", "g2"]
    assert entries[0].kind == "interface"


def test_query_substring_fallback():
    board = SwarmBlackboard("job-1")
    board.post("g1", "the API schema is frozen")
    board.post("g2", "web layout done")
    hits = board.query("schema")
    assert len(hits) == 1
    assert "schema" in hits[0]["note"]


def test_memory_backed_post_and_query():
    class FakeMemory:
        def __init__(self):
            self.written = []

        def write(self, text, **kw):
            self.written.append((text, kw))

        def search(self, query, namespaces=None, limit=20):
            class Node:
                title = "t"
                text = "the API schema is frozen"
                summary = ""

            return [type("Hit", (), {"node": Node()})()]

    mem = FakeMemory()
    board = SwarmBlackboard("job-1", memory_store=mem)
    board.post("g1", "the API schema is frozen")
    # Written to the namespaced memory store.
    assert mem.written
    assert mem.written[0][1]["namespace"] == "swarm/job-1"
    # Query goes through memory search.
    hits = board.query("schema")
    assert hits and "schema" in hits[0]["text"]


def test_memory_failure_is_swallowed():
    class BoomMemory:
        def write(self, *a, **k):
            raise RuntimeError("down")

        def search(self, *a, **k):
            raise RuntimeError("down")

    board = SwarmBlackboard("job-1", memory_store=BoomMemory())
    board.post("g1", "still recorded locally")  # must not raise
    # Falls back to local substring scan.
    assert board.query("recorded")
