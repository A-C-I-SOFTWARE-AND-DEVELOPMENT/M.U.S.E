"""End-to-end tests for the cockpit Memory Tree endpoints (MEM-2).

Hermetic: a real stdlib cockpit server on a random loopback port with a tmp
HERMES_HOME, driven over urllib. Exercises the proposed inbox, owner
decisions (approve/reject/supersede), contradictions, and freshness against
the real provenance-first MemoryTreeStore.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit.server import serve
from hermes_cli.jarvis_prime.memory_tree import (
    ApprovalState,
    MemoryLayer,
    MemoryTreeStore,
)

TOKEN = "test-cockpit-token-123"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    return tmp_path


@pytest.fixture()
def server(home: Path):
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


def _tree_path(home: Path) -> Path:
    return home / "jarvis_prime" / "memory_tree.jsonl"


def _seed_store(home: Path) -> MemoryTreeStore:
    """A store pointed at the SAME default path the cockpit handlers load."""
    return MemoryTreeStore(path=_tree_path(home))


def _url(server, path: str) -> str:
    host, port = server.server_address
    return f"http://{host}:{port}{path}"


def _get(server, path: str, token: str | None = TOKEN):
    req = urllib.request.Request(_url(server, path), method="GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read())


def _post(server, path: str, body: dict, token: str | None = TOKEN):
    data = json.dumps(body).encode()
    req = urllib.request.Request(_url(server, path), data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, json.loads(resp.read())


def _proposed(store: MemoryTreeStore, text: str, *, title: str, ns="jarvis/decisions"):
    return store.write(
        text,
        namespace=ns,
        title=title,
        subject=title,
        layer=MemoryLayer.SESSION,
        confidence=0.6,
        approval_state=ApprovalState.PROPOSED,
    )


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------


def test_tree_endpoints_require_auth(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "/v1/cockpit/memory/tree/proposed", token=None)
    assert exc.value.code == 401


# ---------------------------------------------------------------------------
# proposed inbox + search
# ---------------------------------------------------------------------------


def test_proposed_inbox_lists_captured_candidates(server, home) -> None:
    store = _seed_store(home)
    _proposed(store, "We decided to deploy on Monday.", title="deploy-day")

    status, payload = _get(server, "/v1/cockpit/memory/tree/proposed")
    assert status == 200
    titles = {n["title"] for n in payload["nodes"]}
    assert "deploy-day" in titles
    assert all(n["approval_state"] == "proposed" for n in payload["nodes"])


def test_tree_search_cites_sources(server, home) -> None:
    store = _seed_store(home)
    store.write(
        "Hermes is the canonical backend.",
        namespace="jarvis/architecture",
        title="backend",
        layer=MemoryLayer.DURABLE,
        confidence=0.95,
        source_uri="docs/spec.md",
        owner_approved=True,
    )
    status, payload = _get(server, "/v1/cockpit/memory/tree?q=backend")
    assert status == 200
    assert payload["nodes"]
    assert "docs/spec.md" in payload["nodes"][0]["sources"]


# ---------------------------------------------------------------------------
# owner decisions
# ---------------------------------------------------------------------------


def test_approve_promotes_to_durable(server, home) -> None:
    store = _seed_store(home)
    node = _proposed(store, "We standardize on Material 3.", title="ui").node

    status, payload = _post(
        server, f"/v1/cockpit/memory/tree/{node.id}/decision", {"decision": "approve"}
    )
    assert status == 200
    assert payload["node"]["layer"] == "durable"
    assert payload["node"]["approval_state"] == "owner_approved"
    # Persisted on disk for the live loop to recall.
    reloaded = MemoryTreeStore.load(path=_tree_path(home))
    assert reloaded is not None
    reloaded_node = reloaded.get(node.id)
    assert reloaded_node is not None
    assert reloaded_node.layer is MemoryLayer.DURABLE


def test_approve_conflict_returns_contradiction_not_overwrite(server, home) -> None:
    store = _seed_store(home)
    existing = store.write(
        "We deploy on Friday.",
        namespace="jarvis/decisions",
        title="deploy-day",
        subject="deploy-day",
        layer=MemoryLayer.DURABLE,
        confidence=0.9,
        owner_approved=True,
    ).node
    candidate = _proposed(store, "We deploy on Monday.", title="deploy-day").node

    status, payload = _post(
        server,
        f"/v1/cockpit/memory/tree/{candidate.id}/decision",
        {"decision": "approve"},
    )
    assert status == 200
    assert "contradiction" in payload
    # Both facts survive — no silent overwrite.
    reloaded = MemoryTreeStore.load(path=_tree_path(home))
    assert existing is not None
    assert reloaded.get(existing.id) is not None
    assert reloaded.get(candidate.id) is not None
    assert reloaded is not None
    reloaded_existing = reloaded.get(existing.id)
    assert reloaded_existing is not None
    assert reloaded_existing.contested


def test_reject_excludes_from_recall(server, home) -> None:
    store = _seed_store(home)
    node = _proposed(store, "A weak guess.", title="guess").node

    status, payload = _post(
        server, f"/v1/cockpit/memory/tree/{node.id}/decision", {"decision": "reject"}
    )
    assert status == 200
    assert payload["node"]["approval_state"] == "rejected"
    reloaded = MemoryTreeStore.load(path=_tree_path(home))
    assert reloaded is not None
    reloaded_node = reloaded.get(node.id)
    assert reloaded_node is not None
    assert reloaded_node.active is False


def test_supersede_marks_loser(server, home) -> None:
    store = _seed_store(home)
    old = store.write(
        "Use REST.", namespace="jarvis/decisions", title="api-old",
        subject="api", layer=MemoryLayer.DURABLE, confidence=0.9, owner_approved=True,
    ).node
    new = _proposed(store, "Use REST + SSE.", title="api-new", ns="jarvis/decisions").node

    assert old is not None
    status, payload = _post(
        server,
        f"/v1/cockpit/memory/tree/{new.id}/decision",
        {"decision": "supersede", "supersedes_id": old.id, "note": "SSE added"},
    )
    assert status == 200
    assert payload["superseded"]["superseded_by"] == new.id
    reloaded = MemoryTreeStore.load(path=_tree_path(home))
    assert reloaded is not None
    reloaded_old = reloaded.get(old.id)
    assert reloaded_old is not None
    assert reloaded_old.active is False  # superseded, not deleted


def test_decision_unknown_node_404(server, home) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(
            server, "/v1/cockpit/memory/tree/deadbeef/decision", {"decision": "approve"}
        )
    assert exc.value.code == 404


def test_decision_rejects_secret_capture(server, home) -> None:
    # A node can never have been written with secret content — the write
    # policy rejects it — so the inbox stays clean.
    store = _seed_store(home)
    result = store.write(
        "api_key=sk-ABCDEFGHIJKLMNOPQRSTUV0123456789",
        namespace="jarvis/general",
        title="leak",
        layer=MemoryLayer.SESSION,
        approval_state=ApprovalState.PROPOSED,
    )
    assert not result.ok
    status, payload = _get(server, "/v1/cockpit/memory/tree/proposed")
    assert payload["nodes"] == []


# ---------------------------------------------------------------------------
# contradictions + freshness
# ---------------------------------------------------------------------------


def test_contradictions_list_and_resolve(server, home) -> None:
    store = _seed_store(home)
    a = store.write(
        "We deploy on Friday.", namespace="jarvis/decisions", title="d",
        subject="d", layer=MemoryLayer.DURABLE, confidence=0.9, owner_approved=True,
    ).node
    b = store.write(
        "We deploy on Monday.", namespace="jarvis/decisions", title="d",
        subject="d", layer=MemoryLayer.DURABLE, confidence=0.9, owner_approved=True,
    )
    assert b.contradiction is not None

    status, payload = _get(server, "/v1/cockpit/memory/contradictions")
    assert status == 200
    assert len(payload["contradictions"]) == 1
    report_id = payload["contradictions"][0]["id"]

    assert b.node is not None
    status, resolved = _post(
        server,
        f"/v1/cockpit/memory/contradictions/{report_id}/resolve",
        {"winner_id": b.node.id, "note": "Monday confirmed"},
    )
    assert status == 200
    assert resolved["resolved"]["status"] == "resolved"
    reloaded = MemoryTreeStore.load(path=_tree_path(home))
    assert reloaded is not None
    assert a is not None
    reloaded_a = reloaded.get(a.id)
    assert reloaded_a is not None
    assert reloaded_a.superseded_by == b.node.id


def test_freshness_lists_overdue(server, home) -> None:
    from datetime import datetime, timedelta, timezone

    store = _seed_store(home)
    overdue = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    store.write(
        "Stale fact.", namespace="jarvis/general", title="stale",
        layer=MemoryLayer.SESSION, freshness_due=overdue,
    )
    status, payload = _get(server, "/v1/cockpit/memory/freshness")
    assert status == 200
    assert {n["title"] for n in payload["nodes"]} == {"stale"}
