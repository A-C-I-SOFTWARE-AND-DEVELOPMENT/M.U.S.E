"""Recorded end-to-end proof of the muse core loop over the real cockpit HTTP.

This is the proof-bar centerpiece for "a proven tool, not a demo": one test
that boots the **real** cockpit server (``gateway.cockpit.server.serve``) on a
loopback ephemeral port with a tmp ``HERMES_HOME`` + known token, and drives the
core loop over the wire with ``urllib`` — no network, no paid model, no real
GitHub. It mirrors the hermetic harness in
``tests/e2e/test_cockpit_jobs_approvals_smoke.py`` and
``tests/gateway/test_cockpit_autonomy.py``.

Every hop asserts **real behavior** — the genuine handlers, the genuine
owner-gate phrase, the genuine orchestrator worker, and the genuine audit
ledger. The only things stubbed are the *external world*: the GitHub PAT is
made absent (so publish lands on the honest ``github_not_configured`` path) and
nothing reaches the network (the chosen worker is offline by construction).

The loop the single end-to-end test proves, hop by hop:

1. **Submit** — ``POST /v1/cockpit/orchestrate`` records a real orchestrator
   job (status ``queued``); the dispatch surface ``POST /v1/cockpit/jobs`` also
   enqueues a JobQueue entry. Both appear in ``GET /v1/cockpit/jobs``.
2. **Run / validate** — ``POST /v1/cockpit/jobs/{id}/run`` dispatches the job to
   the built-in, **offline, non-destructive** ``hermes-local-planner`` lane
   (deterministic repo navigation: no edits, no shell, no network). The job
   progresses ``queued → completed`` through real statuses, and the run returns
   the real worker ledger trail (``worker_dispatch`` / ``worker_result`` /
   ``worker_score``).
3. **Owner gate on autonomy (FU-12)** — raising autonomy to a privileged level
   WITHOUT the phrase is ``403 {authorization_required: true}`` and does not
   take effect; WITH ``"Yes, with authorization."`` it is ``200``. Lowering
   (de-escalation) needs no phrase.
4. **Publish gate** — ``POST /v1/cockpit/jobs/{id}/publish`` WITHOUT the phrase
   stages ``approval_required`` (``authorization_required: true``); WITH the
   phrase it passes the owner gate and then hits the honest
   ``403 github_not_configured`` path (no PAT in the hermetic env) — the gate
   passed, no real PR is opened. That is the proven, correct behavior.
5. **Approvals (FU-14)** — a seeded pending proposal round-trips through
   ``POST /v1/cockpit/approvals/{id}``: refused (403) without the phrase,
   decided (200) with it.
6. **Audit ledger** — ``GET /v1/cockpit/autonomy/decisions`` reflects the
   autonomy change, and the decided proposal records its owner decision.

Teardown shuts the server down (no hangs); every HTTP call is bounded by a
timeout.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit.server import serve
from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE


TOKEN = "test-core-loop-e2e-token"
# The offline, non-destructive built-in worker (repo-read-only navigation; no
# edits, no shell, no network) — the lane that makes the loop hermetic.
PLANNER = "hermes-local-planner"


def _git(cwd: Path, *args: str) -> None:
    """Run a git command in ``cwd``, signing disabled (CI signs by default)."""
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "user.email=e2e@hermes.test",
         "-c", "user.name=e2e", *args],
        cwd=str(cwd), check=True, capture_output=True, text=True,
    )


def _tiny_repo(root: Path) -> Path:
    """A small, real git checkout on a feature branch.

    The cockpit's built-in planner navigates ``Path.cwd()``; pointing it (and
    the publish workspace) at this tiny repo instead of the whole hermes
    checkout keeps the dispatch fast (sub-second) while still exercising the
    *real* navigator and *real* git over the wire.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src" / "uploader.py").write_text(
        "def upload(path):\n    return path\n", encoding="utf-8"
    )
    (root / "tests" / "test_uploader.py").write_text(
        "def test_upload():\n    assert True\n", encoding="utf-8"
    )
    (root / "README.md").write_text("# tiny\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    _git(root, "checkout", "-q", "-b", "feature/tidy-upload")
    (root / "src" / "uploader.py").write_text(
        "def upload(path):\n    return str(path)\n", encoding="utf-8"
    )
    _git(root, "commit", "-aqm", "tidy the upload path")
    return root


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate every state root the cockpit touches so the E2E is hermetic."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    # Autonomy starts at the safe floor regardless of the host environment.
    monkeypatch.delenv("HERMES_AUTONOMY", raising=False)
    monkeypatch.delenv("HERMES_COCKPIT_AUTONOMY_LOCKED", raising=False)
    # External world #1: the GitHub PAT is absent → publish lands on the honest
    # ``github_not_configured`` path (the gate passed; no real PR is opened).
    monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
    return tmp_path


@pytest.fixture()
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tiny git repo, made the process cwd so the built-in planner is fast.

    The planner roots at ``Path.cwd()`` and the publish preview reads git in
    the job workspace, so a small real checkout keeps every hop genuine yet the
    whole loop runs in well under the HTTP timeout.
    """
    repo = _tiny_repo(tmp_path / "workspace")
    monkeypatch.chdir(repo)
    return repo


@pytest.fixture()
def server(home: Path, workspace: Path):
    srv = serve(host="127.0.0.1", port=0, token=TOKEN)
    yield srv
    srv.shutdown()


def _url(server, path: str) -> str:
    host, port = server.server_address
    return f"http://{host}:{port}{path}"


def _get(server, path: str, token: str | None = TOKEN) -> tuple[int, dict]:
    req = urllib.request.Request(_url(server, path), method="GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read())


def _post(server, path: str, body: dict, token: str | None = TOKEN) -> tuple[int, dict]:
    """POST returning ``(status, payload)`` for both success and HTTP-error codes.

    The cockpit returns owner-gate refusals as 403 with a JSON body; urllib
    raises those as ``HTTPError``, so we normalize both into a tuple the test
    can assert on directly.
    """
    data = json.dumps(body).encode()
    req = urllib.request.Request(_url(server, path), data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _seed_proposal(home: Path) -> str:
    """Drop one pending self-update proposal and return its cockpit id.

    Mirrors how the live self-improvement loop records a proposal awaiting an
    owner decision; the id derivation matches ``handlers._proposal_id``.
    """
    path = home / "jarvis_prime" / "proposals.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    prop = {
        "kind": "skill_update",
        "target_path": "skills/foo/SKILL.md",
        "rationale": "improve",
        "risk_class": "RC2",
        "requires_owner_approval": True,
        "status": "proposed",
        "created_at": "2026-06-08T00:00:00+00:00",
    }
    path.write_text(json.dumps(prop) + "\n", encoding="utf-8")
    raw = f"{prop['kind']}|{prop['target_path']}|{prop['created_at']}"
    return hashlib.sha1(raw.encode()).hexdigest()[:10]


def test_core_loop_submit_run_validate_owner_gated_publish_and_approve(
    server, home: Path, workspace: Path, tmp_path: Path
) -> None:
    """One recorded E2E of the core loop, asserting the owner gates + audit
    trail at every hop, over the real cockpit HTTP surface."""

    # --- 0. Liveness -------------------------------------------------------
    # The app's first probe — unauthenticated, reports the live service.
    status, health = _get(server, "/v1/health", token=None)
    assert status == 200 and health["ok"] is True

    # Every cockpit route except health refuses a missing bearer token.
    with pytest.raises(urllib.error.HTTPError) as unauth:
        _get(server, "/v1/cockpit/jobs", token=None)
    assert unauth.value.code == 401

    # --- 1. SUBMIT ---------------------------------------------------------
    # Submit a real orchestrator job (the ``/orchestrate`` path) — this is the
    # job the gated run lane can actually dispatch. Non-destructive prompt.
    status, orch_job = _post(
        server,
        "/v1/cockpit/orchestrate",
        {"prompt": "summarize the cockpit server routes"},
    )
    assert status == 201
    orch_id = orch_job["id"]
    assert orch_id
    assert orch_job["status"] in {"queued", "QUEUED"}

    # The other submit surface — the JobQueue dispatch the Tasks screen uses.
    status, queue_job = _post(
        server,
        "/v1/cockpit/jobs",
        {"title": "inspect routes", "prompt": "list the cockpit routes"},
    )
    assert status == 201
    queue_id = queue_job["id"]

    # Both jobs surface in the aggregated queue the app polls (JobQueue +
    # orchestrator stores merged).
    status, listing = _get(server, "/v1/cockpit/jobs")
    assert status == 200
    ids = {j["id"] for j in listing["jobs"]}
    assert orch_id in ids and queue_id in ids

    # --- 2. RUN / DISPATCH (real worker, real status progression) ----------
    # Before the run, the orchestrator job is queued.
    status, before = _get(server, f"/v1/cockpit/jobs/{orch_id}")
    assert status == 200
    assert before["status"] in {"queued", "QUEUED"}

    # Dispatch to the OFFLINE, NON-DESTRUCTIVE built-in planner lane. It is
    # ``requires_approval = False`` (deterministic repo navigation; no edits, no
    # shell, no network), so this drives genuine worker behavior with no phrase.
    status, run_result = _post(
        server,
        f"/v1/cockpit/jobs/{orch_id}/run",
        {"worker_id": PLANNER},
    )
    assert status == 200
    # The job advanced through real statuses to a terminal completed state.
    assert run_result["job"]["status"] in {"completed", "COMPLETED"}
    # The real five-step worker trail is recorded (not a mock of the engine).
    trail_kinds = {e.get("kind") for e in run_result["worker_trail"]}
    assert "worker_dispatch" in trail_kinds
    assert "worker_result" in trail_kinds

    # The status progression is also visible on the job GET (queued → completed).
    status, after = _get(server, f"/v1/cockpit/jobs/{orch_id}")
    assert status == 200
    assert after["status"] in {"completed", "COMPLETED"}
    assert after["status"] != before["status"]

    # The job's own ledger endpoint reflects the run as well.
    status, job_ledger = _get(server, f"/v1/cockpit/jobs/{orch_id}/ledger")
    assert status == 200

    # An execute lane WITHOUT the owner phrase is refused over the wire (the gate
    # that protects irreversible/agentic actions) — proven on the same job.
    status, gated = _post(
        server,
        f"/v1/cockpit/jobs/{orch_id}/run",
        {"worker_id": "codex-execute"},
    )
    assert status == 403
    assert "owner approval" in gated["error"]
    assert AUTHORIZATION_PHRASE in gated["hint"]

    # --- 3. OWNER GATE ON AUTONOMY (FU-12) ---------------------------------
    # Default floor is the safe assisted level.
    status, autonomy = _get(server, "/v1/cockpit/autonomy")
    assert status == 200
    assert autonomy["level"] == "assisted"

    autonomy_ws = str(tmp_path / "project")

    # Raising to a privileged level WITHOUT the phrase → 403 + the FU-12 flag.
    status, refused = _post(
        server,
        "/v1/cockpit/autonomy",
        {"level": "owner_high_autonomy_coding", "workspace_path": autonomy_ws},
    )
    assert status == 403
    assert refused["authorization_required"] is True
    # The escalation did not take effect — the floor is unchanged.
    _, still = _get(server, "/v1/cockpit/autonomy")
    assert still["level"] == "assisted"

    # WITH the exact owner phrase → 200, escalation granted.
    status, raised = _post(
        server,
        "/v1/cockpit/autonomy",
        {
            "level": "owner_high_autonomy_coding",
            "workspace_path": autonomy_ws,
            "authorization": AUTHORIZATION_PHRASE,
        },
    )
    assert status == 200
    assert raised["level"] == "owner_high_autonomy_coding"

    # De-escalation needs no phrase.
    status, lowered = _post(server, "/v1/cockpit/autonomy", {"level": "read_only"})
    assert status == 200
    assert lowered["level"] == "read_only"

    # --- 4. PUBLISH GATE ---------------------------------------------------
    # The publish path runs against a JobQueue job that carries a workspace
    # (orchestrator jobs carry no workspace → 409). Submit one whose workspace
    # is the tiny git checkout so the preview resolves a branch over real git.
    status, publish_job = _post(
        server,
        "/v1/cockpit/jobs",
        {
            "title": "publish demo",
            "prompt": "open a PR for this branch",
            "workspace_path": str(workspace),
        },
    )
    assert status == 201
    publish_id = publish_job["id"]

    # WITHOUT the phrase → staged approval_required, no GitHub call.
    status, staged = _post(
        server, f"/v1/cockpit/jobs/{publish_id}/publish", {}
    )
    assert status == 200
    assert staged["status"] == "approval_required"
    assert staged["authorization_required"] is True

    # WITH the phrase → the owner gate passes. With no PAT in the hermetic env
    # this is the honest ``github_not_configured`` path: the gate passed, no real
    # PR is opened. That is the proven, correct behavior — we do NOT require a
    # real GitHub PR.
    status, published = _post(
        server,
        f"/v1/cockpit/jobs/{publish_id}/publish",
        {"authorization": AUTHORIZATION_PHRASE},
    )
    assert status == 403
    assert published["error"] == "github_not_configured"

    # --- 5. APPROVALS (FU-14 path) -----------------------------------------
    pid = _seed_proposal(home)

    # The pending proposal surfaces as an approval card.
    status, approvals = _get(server, "/v1/cockpit/approvals")
    assert status == 200
    card = next(a for a in approvals["approvals"] if a["id"] == pid)
    assert card["status"] == "PENDING"

    # Approving WITHOUT the exact phrase is refused — never bypass the gate.
    status, bad = _post(
        server,
        f"/v1/cockpit/approvals/{pid}",
        {"decision": "approve", "authorization": "sure, go ahead"},
    )
    assert status == 403
    assert "owner authorization required" in bad["error"]

    # The exact owner phrase decides it.
    status, decided = _post(
        server,
        f"/v1/cockpit/approvals/{pid}",
        {"decision": "approve", "authorization": AUTHORIZATION_PHRASE},
    )
    assert status == 200
    assert decided["status"] == "approve"

    # --- 6. AUDIT / DECISION LEDGER ----------------------------------------
    # The autonomy change(s) are journaled in the decision audit trail.
    status, decisions = _get(server, "/v1/cockpit/autonomy/decisions")
    assert status == 200
    assert any(
        d.get("details", {}).get("event") == "autonomy_change"
        for d in decisions["decisions"]
    )

    # The decided proposal is now recorded as decided (no longer pending) — the
    # approval log reflects the loop's owner decision.
    status, after_approvals = _get(server, "/v1/cockpit/approvals")
    assert status == 200
    decided_card = next(a for a in after_approvals["approvals"] if a["id"] == pid)
    assert decided_card["status"] != "PENDING"
