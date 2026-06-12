"""Tests for the Learning-Queue dashboard plugin backend router.

Drives the plugin's FastAPI APIRouter with a TestClient against a temp
DatasetStore, mirroring how the kanban plugin_api is exercised. Skips cleanly
when the optional dashboard deps (fastapi/httpx) aren't installed.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from muse_cli.jarvis_prime.learning_dataset import (
    DatasetStore,
    Provenance,
    QualityGates,
    SourceTrust,
    TraceType,
)
from muse_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE

_PLUGIN_API = (
    Path(__file__).resolve().parents[3]  # repo root (tests/plugins/dashboard/<file>)
    / "plugins"
    / "learning-queue"
    / "dashboard"
    / "plugin_api.py"
)


def _load_router():
    spec = importlib.util.spec_from_file_location("_lq_plugin_api", _PLUGIN_API)
    mod = importlib.util.module_from_spec(spec)  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture
    # Register before exec so Pydantic can resolve the request models'
    # forward-ref annotations (the dashboard loader does the same).
    sys.modules[spec.name] = mod  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
    spec.loader.exec_module(mod)  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
    return mod.router


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Point the profile-aware store at a temp HERMES_HOME so the plugin's
    # DatasetStore.load() reads/writes there.
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    app = FastAPI()
    app.include_router(_load_router())
    return TestClient(app)


def _seed_pending(tmp_path):
    store = DatasetStore()  # uses HERMES_HOME default path
    cand = store.add_candidate(
        TraceType.CODING_TASK,
        {"conversations": [{"from": "human", "value": "fix it"}]},
        Provenance(source_kind="trajectory", source_uri="job://7", trust=SourceTrust.OWNER),
        QualityGates(tests_passed=True, reviewer_passed=True, rollback_available=True),
    )
    return cand.id


def test_queue_and_stats(client, tmp_path):
    cid = _seed_pending(tmp_path)
    r = client.get("/queue", params={"status": "pending"})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1
    assert data["learning"][0]["id"] == cid

    s = client.get("/stats").json()
    assert s["total"] == 1
    assert s["by_status"].get("pending") == 1


def test_approve_requires_owner_phrase(client, tmp_path):
    cid = _seed_pending(tmp_path)
    # Missing/incorrect phrase → 403, candidate stays pending.
    bad = client.post(f"/candidate/{cid}/decide", json={"decision": "approve"})
    assert bad.status_code == 403
    assert client.get("/queue", params={"status": "pending"}).json()["count"] == 1

    # Correct phrase → approved.
    ok = client.post(
        f"/candidate/{cid}/decide",
        json={"decision": "approve", "authorization": AUTHORIZATION_PHRASE},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "approve"
    assert client.get("/queue", params={"status": "approved"}).json()["count"] == 1


def test_reject_needs_no_phrase(client, tmp_path):
    cid = _seed_pending(tmp_path)
    r = client.post(f"/candidate/{cid}/decide", json={"decision": "reject"})
    assert r.status_code == 200
    assert client.get("/queue", params={"status": "rejected"}).json()["count"] == 1


def test_decide_unknown_candidate_404(client, tmp_path):
    _seed_pending(tmp_path)
    r = client.post("/candidate/deadbeef/decide", json={"decision": "reject"})
    assert r.status_code == 404


def test_export_jsonl(client, tmp_path):
    cid = _seed_pending(tmp_path)
    client.post(
        f"/candidate/{cid}/decide",
        json={"decision": "approve", "authorization": AUTHORIZATION_PHRASE},
    )
    out = tmp_path / "export.jsonl"
    r = client.post("/export", json={"format": "jsonl", "out": str(out)})
    assert r.status_code == 200
    assert r.json()["exported"] == 1
    assert out.exists()
    line = json.loads(out.read_text().strip().splitlines()[0])
    assert line["trace_type"] == "coding_task_trace"


def test_manifest_is_valid_and_dist_present():
    base = _PLUGIN_API.parent
    manifest = json.loads((base / "manifest.json").read_text())
    assert manifest["name"] == "learning-queue"
    assert manifest["entry"] == "dist/index.js"
    assert manifest["api"] == "plugin_api.py"
    assert (base / "dist" / "index.js").exists()
