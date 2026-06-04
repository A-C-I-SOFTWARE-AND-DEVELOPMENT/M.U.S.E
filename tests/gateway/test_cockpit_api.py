"""End-to-end tests for the Hermes cockpit API (gateway/cockpit).

Hermetic: each test starts the real stdlib server on a random loopback
port with a tmp HERMES_HOME and a known token, then drives it with
``urllib``. No network, no third-party deps. The chat test exercises the
REAL JARVIS agent responder (not an echo).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit import auth as cockpit_auth
from gateway.cockpit.server import serve


TOKEN = "test-cockpit-token-123"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Isolate every state root the cockpit touches so the suite is hermetic
    # regardless of cwd: HERMES_HOME (memory, proposals, auth) and
    # HERMES_ORCHESTRATOR_HOME (the JobQueue keys off its own env, else cwd).
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    return tmp_path


@pytest.fixture()
def server(home: Path):
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


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
        return resp.status, resp.read()


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------


def test_health_needs_no_auth(server) -> None:
    status, payload = _get(server, "/v1/health", token=None)
    assert status == 200
    assert payload["ok"] is True
    assert payload["service"] == "hermes-cockpit"
    assert payload["api_version"]


def test_protected_route_rejects_missing_token(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "/v1/cockpit/runtime/status", token=None)
    assert exc.value.code == 401


def test_protected_route_rejects_wrong_token(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "/v1/cockpit/runtime/status", token="wrong")
    assert exc.value.code == 401


def test_protected_route_accepts_token(server) -> None:
    status, payload = _get(server, "/v1/cockpit/runtime/status")
    assert status == 200
    assert "gateway" in payload and "host" in payload and "queue" in payload


# ---------------------------------------------------------------------------
# real subsystem-backed routes
# ---------------------------------------------------------------------------


def test_runtime_status_has_live_queue_snapshot(server) -> None:
    _, payload = _get(server, "/v1/cockpit/runtime/status")
    queue = payload["queue"]
    assert set(queue) >= {"running", "queued", "waiting_approval"}
    assert all(isinstance(v, int) for v in queue.values())


def test_workers_detection_is_keyless(server) -> None:
    _, payload = _get(server, "/v1/cockpit/runtime/workers")
    assert "workers" in payload
    # detection-only: no token/key fields leak
    blob = json.dumps(payload)
    assert "api_key" not in blob and "token" not in blob.lower()


def test_diagnostics_runs_launch_doctor(server) -> None:
    _, payload = _get(server, "/v1/cockpit/diagnostics")
    assert "checks" in payload
    names = {c["name"] for c in payload["checks"]}
    assert "owner_gate" in names and "emergency_stop" in names


def test_models_is_read_only_policy(server) -> None:
    _, payload = _get(server, "/v1/cockpit/models")
    assert "routes" in payload
    assert payload["routes"]["local_oss"]["rank"] == 1


def test_jobs_and_events_have_real_or_empty(server) -> None:
    _, jobs = _get(server, "/v1/cockpit/jobs")
    assert "jobs" in jobs and isinstance(jobs["jobs"], list)
    _, events = _get(server, "/v1/cockpit/events")
    assert "events" in events and isinstance(events["events"], list)


# ---------------------------------------------------------------------------
# memory CRUD — real store, secret-rejection preserved
# ---------------------------------------------------------------------------


def test_memory_create_and_list(server) -> None:
    # Legacy flat key/value still accepted (backward compatible)...
    status, raw = _post(
        server, "/v1/cockpit/memory", {"key": "fav_editor", "value": "neovim"}
    )
    assert status == 201
    created = json.loads(raw)
    assert created["stored"] is True
    # ...and the response is the canonical enriched MemoryItem, not flat.
    item = created["item"]
    assert item["title"] == "fav_editor"
    assert item["content"] == "neovim"
    assert item["id"] == "fav_editor"
    assert item["category"] == "UNCATEGORIZED"  # honest, not guessed
    assert item["confidence"] in {"LOW", "MEDIUM", "HIGH", "CONFIRMED"}
    assert item["durability"] in {
        "EPHEMERAL",
        "SESSION",
        "SHORT_TERM",
        "LONG_TERM",
        "PERMANENT",
    }
    assert item["provenance"]["source"]
    assert item["redacted"] is False

    _, listing = _get(server, "/v1/cockpit/memory")
    assert any(i["title"] == "fav_editor" for i in listing["items"])


def test_memory_create_canonical_fields(server) -> None:
    status, raw = _post(
        server,
        "/v1/cockpit/memory",
        {
            "title": "deploy_window",
            "content": "Owner prefers deploys after 6pm ET",
            "category": "OWNER_PREFERENCE",
            "durability": "PERMANENT",
            "confidence": "HIGH",
            "tags": ["ops", "scheduling"],
        },
    )
    assert status == 201
    item = json.loads(raw)["item"]
    assert item["category"] == "OWNER_PREFERENCE"  # persisted, round-trips
    assert item["durability"] == "PERMANENT"
    assert item["confidence"] == "HIGH"
    assert "ops" in item["tags"]


def test_memory_rejects_secret(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(
            server,
            "/v1/cockpit/memory",
            {"key": "leak", "value": "api_key=sk-secret-value-1234567890"},
        )
    assert exc.value.code == 422  # rejected, not stored, not faked


# ---------------------------------------------------------------------------
# jobs — real JobQueue, canonical CockpitJob shape
# ---------------------------------------------------------------------------


def test_jobs_dispatch_list_get_cancel_roundtrip(server) -> None:
    _, listing = _get(server, "/v1/cockpit/jobs")
    assert listing["jobs"] == []
    assert "next_cursor" in listing and "prev_cursor" in listing

    status, raw = _post(
        server,
        "/v1/cockpit/jobs",
        {
            "title": "Add OAuth callback",
            "worker_id": "codex_cli",
            "prompt": "## Goal\nAdd handler",
            "workspace_path": "/tmp/proj",
            "branch_hint": "feature/oauth",
        },
    )
    assert status == 201
    job = json.loads(raw)
    assert job["title"] == "Add OAuth callback"
    assert job["worker_id"] == "codex_cli"
    assert job["status"] == "QUEUED"
    assert job["workspace_path"] == "/tmp/proj"
    assert job["branch"] == "feature/oauth"
    assert job["created_at"]
    assert job["validation_summary"] is None  # honest null until the pipeline runs
    jid = job["id"]

    _, listing = _get(server, "/v1/cockpit/jobs")
    assert any(j["id"] == jid for j in listing["jobs"])

    _, fetched = _get(server, f"/v1/cockpit/jobs/{jid}")
    assert fetched["id"] == jid and fetched["status"] == "QUEUED"

    status, raw = _post(
        server, f"/v1/cockpit/jobs/{jid}/cancel", {"reason": "wrong workspace"}
    )
    assert status == 200
    assert json.loads(raw)["status"] == "CANCELLED"

    # cancelling a terminal job → 409
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, f"/v1/cockpit/jobs/{jid}/cancel", {})
    assert exc.value.code == 409


def test_jobs_dispatch_requires_title_and_prompt(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/jobs", {"title": "no prompt here"})
    assert exc.value.code == 400


def test_job_get_unknown_is_404(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "/v1/cockpit/jobs/job_does_not_exist")
    assert exc.value.code == 404


# ---------------------------------------------------------------------------
# audit — real decision ledger, canonical AuditRecord / ProofRecord
# ---------------------------------------------------------------------------


def test_audit_list_and_proof_from_real_ledger(server) -> None:
    from hermes_cli.decision_ledger import DecisionLedger, write_ledger

    ledger = DecisionLedger(
        decision="Add OAuth callback",
        plain_english_summary="Finish the OAuth return path",
        context="User asked to finish OAuth login",
        evidence_reviewed="Reviewed src/auth and the provider docs",
        options_considered="Codex vs manual",
        selected_model_worker="codex_cli",
        why_this_choice="Bounded edit, Codex is fastest",
        rejected_alternatives="Manual would be slower",
        cost_latency_quality_tradeoff="cheap/fast/high",
        validation_plan="Run the auth tests",
        approval_required="no - trivial",
        final_decision="proceed - implemented",
        confidence="high - understood",
        open_risks="N/A - additive",
        rollback_plan="Revert the commit",
    )
    write_ledger(ledger, session_id="smoke", validate=False)

    _, listing = _get(server, "/v1/cockpit/audit")
    assert listing["records"], "expected the written ledger to surface"
    rec = listing["records"][0]
    assert rec["route"]["destination"] == "CODEX"
    assert rec["result"] == "SUCCESS"
    assert rec["confidence"] == 0.95
    proof_id = rec["proof_id"]

    _, proof = _get(server, f"/v1/cockpit/audit/{proof_id}/proof")
    assert proof["audit_id"] == proof_id
    assert proof["rollback"] is not None  # "Revert the commit"
    assert any(e["kind"] == "DOC_LINK" for e in proof["evidence"])


def test_audit_proof_unknown_is_404(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "/v1/cockpit/audit/does-not-exist/proof")
    assert exc.value.code == 404


# ---------------------------------------------------------------------------
# real-agent chat stream (NDJSON, not an echo)
# ---------------------------------------------------------------------------


def test_chat_streams_real_agent_turn(server) -> None:
    status, raw = _post(
        server, "/v1/jarvis/chat", {"prompt": "audit this repo", "history": []}
    )
    assert status == 200
    lines = [json.loads(ln) for ln in raw.decode().splitlines() if ln.strip()]
    types = [c["type"] for c in lines]
    assert types[0] == "thinking"
    assert "body" in types and types[-1] == "done"
    # Real classification, not an echo of the prompt.
    body_text = next(c["text"] for c in lines if c["type"] == "body")
    assert "JARVIS Prime" in body_text
    assert "You said:" not in body_text


def test_chat_requires_auth(server) -> None:
    data = json.dumps({"prompt": "hi"}).encode()
    req = urllib.request.Request(_url(server, "/v1/jarvis/chat"), data=data, method="POST")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=10)
    assert exc.value.code == 401


# ---------------------------------------------------------------------------
# loopback gate + token persistence
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# approvals — persistent proposal queue, owner phrase preserved
# ---------------------------------------------------------------------------


def _seed_proposal(home: Path) -> str:
    import hashlib
    import json as _json

    path = home / "jarvis_prime" / "proposals.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    prop = {
        "kind": "skill_update",
        "target_path": "skills/foo/SKILL.md",
        "rationale": "improve",
        "risk_class": "RC2",
        "requires_owner_approval": True,
        "status": "proposed",
        "created_at": "2026-05-30T00:00:00+00:00",
    }
    path.write_text(_json.dumps(prop) + "\n", encoding="utf-8")
    raw = f"{prop['kind']}|{prop['target_path']}|{prop['created_at']}"
    return hashlib.sha1(raw.encode()).hexdigest()[:10]


def test_approvals_list_canonical_cards(server, home: Path) -> None:
    pid = _seed_proposal(home)
    _, payload = _get(server, "/v1/cockpit/approvals")
    card = next(a for a in payload["approvals"] if a["id"] == pid)
    # Canonical ApprovalCard shape (not the raw proposal shape).
    assert card["tier"] == "RISKY"  # RC2
    assert card["status"] == "PENDING"  # proposed
    assert card["requester"] == "jarvis"
    assert card["summary"] == "improve"
    assert card["title"].startswith("Self-update")
    assert card["proposed_action"]
    assert card["expires_at"] is None


def test_proposals_native_view(server, home: Path) -> None:
    pid = _seed_proposal(home)
    _, payload = _get(server, "/v1/cockpit/proposals")
    item = next(p for p in payload["proposals"] if p["id"] == pid)
    # Self-update-native shape: keeps risk_class/risk_level/target.
    assert item["risk_class"] == "RC2"
    assert item["risk_level"] == "medium"
    assert item["target"] == "skills/foo/SKILL.md"
    assert item["requires_owner_approval"] is True


def test_approve_requires_exact_owner_phrase(server, home: Path) -> None:
    pid = _seed_proposal(home)
    # Wrong phrase → 403, never bypasses the owner gate.
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(
            server,
            f"/v1/cockpit/approvals/{pid}",
            {"decision": "approve", "authorization": "yes go ahead"},
        )
    assert exc.value.code == 403
    # Exact phrase → approved.
    status, raw = _post(
        server,
        f"/v1/cockpit/approvals/{pid}",
        {"decision": "approve", "authorization": "Yes, with authorization."},
    )
    assert status == 200
    assert json.loads(raw)["status"] == "approve"


def test_reject_needs_no_phrase(server, home: Path) -> None:
    pid = _seed_proposal(home)
    status, raw = _post(
        server, f"/v1/cockpit/approvals/{pid}", {"decision": "reject"}
    )
    assert status == 200


def test_sessions_list_real_or_empty(server) -> None:
    _, payload = _get(server, "/v1/cockpit/sessions")
    assert "sessions" in payload and isinstance(payload["sessions"], list)


# ---------------------------------------------------------------------------
# research vault — recent evidence for the mobile home screen (read-only)
# ---------------------------------------------------------------------------


def test_research_requires_auth(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "/v1/cockpit/research", token=None)
    assert exc.value.code == 401


def test_refuses_non_loopback_bind(home: Path) -> None:
    with pytest.raises(ValueError):
        serve(host="0.0.0.0", port=0, token=TOKEN)


def test_token_persisted_owner_only(home: Path) -> None:
    token = cockpit_auth.load_or_create_token()
    assert token and cockpit_auth.read_token() == token
    import os
    import stat

    if os.name == "posix":
        mode = stat.S_IMODE(os.stat(cockpit_auth.token_path()).st_mode)
        assert mode == 0o600


# ---------------------------------------------------------------------------
# skills — real installed-skill list (read-only)
# ---------------------------------------------------------------------------


def test_skills_list_returns_canonical_list(server) -> None:
    _, payload = _get(server, "/v1/cockpit/skills")
    assert "skills" in payload and isinstance(payload["skills"], list)
    for s in payload["skills"]:
        assert set(s.keys()) == {"id", "command", "name", "description"}


def test_skills_list_requires_auth(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "/v1/cockpit/skills", token=None)
    assert exc.value.code == 401


# ---------------------------------------------------------------------------
# navigation — surfaced from the orchestrator job ledger
# ---------------------------------------------------------------------------


def test_navigation_surface_from_orchestrator_ledger(server, home: Path) -> None:
    from hermes_cli import orchestrator as orch

    repo = home / "repo"
    (repo / "svc").mkdir(parents=True)
    (repo / "svc" / "uploader.py").write_text(
        "def upload_file(p):\n    return open(p).read()\n"
    )
    job = orch.submit_job("upload_file fails on large files")
    orch.navigate_job(job.id, repo_root=str(repo))

    _, payload = _get(server, "/v1/cockpit/navigation")
    navs = payload["navigations"]
    assert navs, "the navigation decision should surface in the cockpit"
    nav = navs[0]
    assert nav["job_id"] == job.id
    assert nav["objective"].startswith("upload_file")
    assert any(f["path"].endswith("uploader.py") for f in nav["candidate_files"])


def test_navigation_empty_when_no_orchestrate_job(server) -> None:
    _, payload = _get(server, "/v1/cockpit/navigation")
    assert payload["navigations"] == []  # honest empty, not fabricated


# ---------------------------------------------------------------------------
# capabilities — server feature negotiation (not the curated in-app catalog)
# ---------------------------------------------------------------------------


def test_capabilities_reports_subsystems_and_gate(server) -> None:
    status, payload = _get(server, "/v1/cockpit/capabilities")
    assert status == 200
    assert payload["api_version"]
    assert payload["owner_gate_required"] is True
    # Loopback server (default) permits execute lanes.
    assert payload["execute_allowed"] is True
    subs = payload["subsystems"]
    # Core subsystems import in this repo.
    for name in ("memory", "jobs", "orchestrator", "coding", "evidence", "ledger"):
        assert name in subs
    # available_workers advertises the *lane ids the execute route accepts*
    # (not the host-CLI detection view) so negotiation is actionable.
    worker_ids = {w["id"] for w in payload["available_workers"]}
    assert "claude-execute" in worker_ids
    assert any(w["requires_approval"] for w in payload["available_workers"])
    assert "detected_clis" in payload


def test_capabilities_requires_auth(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "/v1/cockpit/capabilities", token=None)
    assert exc.value.code == 401


# ---------------------------------------------------------------------------
# jobs pause / resume — real JobQueue scheduling control
# ---------------------------------------------------------------------------


def test_job_pause_and_resume_roundtrip(server) -> None:
    _, raw = _post(
        server,
        "/v1/cockpit/jobs",
        {"title": "Pause me", "prompt": "## Goal\nwork"},
    )
    jid = json.loads(raw)["id"]

    status, raw = _post(server, f"/v1/cockpit/jobs/{jid}/pause", {"reason": "hold"})
    assert status == 200
    assert json.loads(raw)["status"] == "PAUSED"

    status, raw = _post(server, f"/v1/cockpit/jobs/{jid}/resume", {})
    assert status == 200
    assert json.loads(raw)["status"] == "QUEUED"


def test_job_pause_unknown_is_404(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/jobs/nope/pause", {})
    assert exc.value.code == 404


def test_job_resume_non_resumable_is_409(server) -> None:
    _, raw = _post(
        server, "/v1/cockpit/jobs", {"title": "Fresh", "prompt": "## Goal\nx"}
    )
    jid = json.loads(raw)["id"]  # QUEUED, not a resumable state
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, f"/v1/cockpit/jobs/{jid}/resume", {})
    assert exc.value.code == 409


# ---------------------------------------------------------------------------
# emergency stop — a real backend halt (pauses queued work, clears leases)
# ---------------------------------------------------------------------------


def test_emergency_stop_cancels_non_terminal_jobs(server) -> None:
    _, raw = _post(
        server, "/v1/cockpit/jobs", {"title": "Runaway", "prompt": "## Goal\ngo"}
    )
    jid = json.loads(raw)["id"]

    status, raw = _post(server, "/v1/cockpit/emergency-stop", {"reason": "owner panic"})
    assert status == 200
    result = json.loads(raw)
    assert result["reason"] == "owner panic"
    assert result["engaged"] is True
    assert result["tick_disabled"] is True
    # Decisive halt: in-flight work is cancelled and autonomy drops to the floor.
    assert jid in result["cancelled_jobs"]
    assert result["cancelled_count"] >= 1
    assert result["autonomy_level"] == "read_only"

    # The job is genuinely terminal in the backend, not just in app state.
    _, fetched = _get(server, f"/v1/cockpit/jobs/{jid}")
    assert fetched["status"] in {"CANCELLED", "CANCELED"}


# ---------------------------------------------------------------------------
# coding lanes — audit (read-only) / plan (stage only) / execute (gated)
# ---------------------------------------------------------------------------


def test_coding_audit_classifies_and_routes(server) -> None:
    status, raw = _post(
        server, "/v1/cockpit/coding/audit", {"prompt": "add a unit test for the parser"}
    )
    assert status == 200
    payload = json.loads(raw)
    assert payload["intent"] == "test"
    assert payload["risk_class"].startswith("RC")
    assert payload["owner_gate_required"] in (True, False)
    assert "primary_worker" in payload


def test_coding_audit_requires_prompt(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/coding/audit", {})
    assert exc.value.code == 400


def test_coding_plan_builds_and_validates_packet(server) -> None:
    status, raw = _post(
        server,
        "/v1/cockpit/coding/plan",
        {"prompt": "refactor the memory store to add a category field"},
    )
    assert status == 200
    payload = json.loads(raw)
    packet = payload["packet"]
    assert packet["mission"]
    assert packet["branch"]
    assert packet["risk_class"].startswith("RC")
    assert payload["validation"]["ok"] is True
    assert payload["markdown"].startswith("#")  # rendered packet markdown


def test_coding_execute_stages_when_unauthorized(server) -> None:
    # An execute lane requires the owner phrase; without it we STAGE (200),
    # never run. A real orchestrator job is created and left pending approval.
    status, raw = _post(
        server,
        "/v1/cockpit/coding/execute",
        {"prompt": "implement a new endpoint in the gateway"},
    )
    assert status == 200
    payload = json.loads(raw)
    assert payload["status"] == "approval_required"
    assert payload["authorization_required"] is True
    assert payload["job"]["id"]
    assert payload["worker_id"].endswith("-execute")
    assert "send authorization exactly" in payload["authorization_hint"]


def test_coding_execute_requires_prompt(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/coding/execute", {})
    assert exc.value.code == 400


def test_coding_execute_reuses_staged_job_id(server) -> None:
    # The cockpit's approval retry passes the staged job's id back. Without a
    # job_id every call submits a fresh job; with it, the gateway resumes the
    # same job instead of leaking the staged one (and creating a second).
    status, raw = _post(
        server,
        "/v1/cockpit/coding/execute",
        {"prompt": "implement a new endpoint in the gateway"},
    )
    assert status == 200
    staged_id = json.loads(raw)["job"]["id"]
    assert staged_id

    # A naked re-send creates a *different* job (the leak this guards against).
    status, raw = _post(
        server,
        "/v1/cockpit/coding/execute",
        {"prompt": "implement a new endpoint in the gateway"},
    )
    assert json.loads(raw)["job"]["id"] != staged_id

    # Re-sending with the staged id resumes that exact job.
    status, raw = _post(
        server,
        "/v1/cockpit/coding/execute",
        {"prompt": "implement a new endpoint in the gateway", "job_id": staged_id},
    )
    assert status == 200
    assert json.loads(raw)["job"]["id"] == staged_id


# ---------------------------------------------------------------------------
# models/local — honest local-model status (Gemma / Ollama)
# ---------------------------------------------------------------------------


def test_models_local_is_honest_when_runtime_unreachable(server, monkeypatch) -> None:
    from gateway.cockpit import generate as cockpit_generate

    # No reachable runtime → never fabricate installed models or readiness.
    def _boom(_base=None):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(cockpit_generate, "installed_chat_models", _boom)

    status, payload = _get(server, "/v1/cockpit/models/local")
    assert status == 200
    assert payload["reachable"] is False
    assert payload["reach_error"]
    assert payload["installed"] == []
    assert payload["runtime_status"] in {"not_configured", "configured"}
    assert payload["ollama_base"].startswith("http")


def test_models_local_labels_are_evidence_based(server, monkeypatch) -> None:
    from gateway.cockpit import generate as cockpit_generate

    monkeypatch.setattr(
        cockpit_generate,
        "installed_chat_models",
        lambda _base=None: ["gemma3:latest", "qwen3-coder:7b"],
    )

    status, payload = _get(server, "/v1/cockpit/models/local")
    assert status == 200
    assert payload["reachable"] is True
    assert payload["runtime_status"] == "runtime_reachable"
    names = {m["name"] for m in payload["installed"]}
    assert names == {"gemma3:latest", "qwen3-coder:7b"}
    allowed = {"promoted_for_task", "fallback_only", "variant_installed"}
    for m in payload["installed"]:
        # Honest vocabulary only — a GET never claims "smoke_tested" / "ready".
        assert m["status"] in allowed
        assert isinstance(m["promoted_for"], list)
        assert isinstance(m["fallback_for"], list)


def test_models_local_smoke_reports_blocked_without_runtime(server, monkeypatch) -> None:
    from gateway.cockpit import generate as cockpit_generate

    def _boom(_base=None):
        raise RuntimeError("no local Ollama chat model installed")

    monkeypatch.setattr(cockpit_generate, "pick_model", _boom)

    status, raw = _post(server, "/v1/cockpit/models/local/smoke", {})
    assert status == 200
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert payload["error"]


# ---------------------------------------------------------------------------
# evidence — search (read-only) / verify (non-mutating claim audit)
# ---------------------------------------------------------------------------


def test_evidence_search_empty_is_honest(server) -> None:
    _, payload = _get(server, "/v1/cockpit/evidence/search?q=transformers")
    assert payload["items"] == []  # honest empty, never fabricated


def test_evidence_verify_requires_claim(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, "/v1/cockpit/evidence/verify", {})
    assert exc.value.code == 400


# ---------------------------------------------------------------------------
# model routes (evidence-backed task-class routing)
# ---------------------------------------------------------------------------


def test_model_routes_covers_all_task_classes(server) -> None:
    _, payload = _get(server, "/v1/cockpit/model-routes")
    assert "routes" in payload and payload["routes"]
    task_classes = {r["task_class"] for r in payload["routes"]}
    assert task_classes == set(payload["task_classes"])
    # Each decision carries an explanation and a fallback chain (contract).
    for r in payload["routes"]:
        assert r["why"]
        assert "fallback_chain" in r
        assert "paid_enabled" in r


def test_model_route_override_pins_model(server, home: Path) -> None:
    status, raw = _post(
        server,
        "/v1/cockpit/model-routes/override",
        {"task_class": "summarization", "model": "my-local-model"},
    )
    assert status == 200
    assert json.loads(raw)["changed"]["model"] == "my-local-model"
    # The pin is reflected in the routes view.
    _, payload = _get(server, "/v1/cockpit/model-routes")
    summ = next(r for r in payload["routes"] if r["task_class"] == "summarization")
    assert summ["chosen"] == "my-local-model"
    assert summ["route_tier"] == "owner_override"


def test_model_route_override_unknown_task_is_400(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(
            server,
            "/v1/cockpit/model-routes/override",
            {"task_class": "not_a_class", "model": "x"},
        )
    assert exc.value.code == 400


def test_combined_invalid_task_does_not_flip_paid(server) -> None:
    # A combined body — valid paid authorization + an *invalid* task class —
    # must reject the whole request (400) and leave the money-spend gate
    # untouched. The paid override must not be written before validation fails.
    _, before = _get(server, "/v1/cockpit/model-routes")
    assert before["paid_enabled"] is False
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(
            server,
            "/v1/cockpit/model-routes/override",
            {
                "paid_enabled": True,
                "authorization": "Yes, with authorization.",
                "task_class": "not_a_class",
            },
        )
    assert exc.value.code == 400
    _, after = _get(server, "/v1/cockpit/model-routes")
    assert after["paid_enabled"] is False


def test_paid_toggle_requires_owner_phrase(server) -> None:
    # Wrong/absent phrase → 403, money-spend gate never bypassed.
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(
            server,
            "/v1/cockpit/model-routes/override",
            {"paid_enabled": True, "authorization": "go ahead"},
        )
    assert exc.value.code == 403
    # Exact phrase → enabled + reflected.
    status, raw = _post(
        server,
        "/v1/cockpit/model-routes/override",
        {"paid_enabled": True, "authorization": "Yes, with authorization."},
    )
    assert status == 200
    assert json.loads(raw)["changed"]["paid_enabled"] is True
    _, payload = _get(server, "/v1/cockpit/model-routes")
    assert payload["paid_enabled"] is True


def test_model_route_override_no_secret_keys(server) -> None:
    # Even with an api_key-looking field, nothing secret is stored/echoed.
    status, raw = _post(
        server,
        "/v1/cockpit/model-routes/override",
        {"task_class": "research", "model": "qwen", "api_key": "sk-should-be-ignored"},
    )
    assert status == 200
    assert "sk-should-be-ignored" not in raw.decode()
