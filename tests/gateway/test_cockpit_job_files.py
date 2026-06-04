"""End-to-end tests for the read-only cockpit job-workspace browse routes.

Covers ``/jobs/{id}/files-changed|validation|tree|file`` — the read-only
companions to ``/diff`` and ``/validate``. Hermetic: the real stdlib server on
a random loopback port with a tmp HERMES_HOME and a known token, over urllib.
No network, no third-party deps.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from gateway.cockpit.server import serve

TOKEN = "test-cockpit-token-123"


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Keep HERMES_HOME (the cockpit's secret/state dir) in its own subtree so the
    # job workspaces created under tmp_path are NOT inside it — the file readers
    # deny any path that resolves into ~/.hermes.
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes_home"))
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


def _get(server, path: str):
    req = urllib.request.Request(_url(server, path), method="GET")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read())


def _post(server, path: str, body: dict):
    data = json.dumps(body).encode()
    req = urllib.request.Request(_url(server, path), data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status, json.loads(resp.read())


def _dispatch(server, workspace_path: str) -> str:
    body = {
        "title": "Build feature",
        "worker_id": "codex_cli",
        "prompt": "## Goal\nDo it",
        "workspace_path": workspace_path,
    }
    status, job = _post(server, "/v1/cockpit/jobs", body)
    assert status == 201
    return job["id"]


# ── files-changed ──────────────────────────────────────────────────────────


def test_files_changed_honest_empty_on_non_git_workspace(server, home: Path) -> None:
    ws = home / "plain"
    ws.mkdir()
    jid = _dispatch(server, str(ws))
    status, body = _get(server, f"/v1/cockpit/jobs/{jid}/files-changed")
    assert status == 200
    assert body == {"files": []}


def test_files_changed_unknown_job_is_404(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "/v1/cockpit/jobs/nope/files-changed")
    assert exc.value.code == 404


# ── validation (read companion to /validate) ───────────────────────────────


def test_validation_honest_empty_before_any_run(server, home: Path) -> None:
    ws = home / "ws_v"
    ws.mkdir()
    jid = _dispatch(server, str(ws))
    status, body = _get(server, f"/v1/cockpit/jobs/{jid}/validation")
    assert status == 200
    assert body["gates"] == []
    assert body["policy"]["all_must_pass"] is True


def test_validation_returns_persisted_gates_after_validate(server, home: Path) -> None:
    ws = home / "ws_v2"
    ws.mkdir()
    jid = _dispatch(server, str(ws))
    # Running the gates persists <ws>/validation/results.json.
    _, ran = _post(server, f"/v1/cockpit/jobs/{jid}/validate", {})
    status, got = _get(server, f"/v1/cockpit/jobs/{jid}/validation")
    assert status == 200
    # The read companion projects the same persisted report — no drift.
    assert got["gates"] == ran["gates"]
    assert (ws / "validation" / "results.json").is_file()


def test_validation_unknown_job_is_404(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "/v1/cockpit/jobs/nope/validation")
    assert exc.value.code == 404


# ── tree (folder browser) ──────────────────────────────────────────────────


def test_tree_lists_files_and_dirs(server, home: Path) -> None:
    ws = home / "ws_t"
    (ws / "sub").mkdir(parents=True)
    (ws / "sub" / "a.py").write_text("print('hi')\n", encoding="utf-8")
    (ws / "top.txt").write_text("x\n", encoding="utf-8")
    jid = _dispatch(server, str(ws))

    status, root = _get(server, f"/v1/cockpit/jobs/{jid}/tree")
    assert status == 200
    by_name = {e["name"]: e for e in root["entries"]}
    assert by_name["sub"]["kind"] == "dir"
    assert by_name["top.txt"]["kind"] == "file"
    assert by_name["top.txt"]["size"] == 2

    status, sub = _get(server, f"/v1/cockpit/jobs/{jid}/tree?path=sub")
    assert status == 200
    assert sub["path"] == "sub"
    assert [e["name"] for e in sub["entries"]] == ["a.py"]


def test_tree_rejects_path_traversal(server, home: Path) -> None:
    ws = home / "ws_t2"
    ws.mkdir()
    jid = _dispatch(server, str(ws))
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, f"/v1/cockpit/jobs/{jid}/tree?path=../../etc")
    assert exc.value.code == 400


def test_tree_honest_empty_when_no_workspace(server) -> None:
    from hermes_cli import orchestrator as orch

    jid = orch.submit_job("Add a /healthz endpoint").id
    status, body = _get(server, f"/v1/cockpit/jobs/{jid}/tree")
    assert status == 200
    assert body["entries"] == []


# ── file (single-file preview) ─────────────────────────────────────────────


def test_file_returns_text_content(server, home: Path) -> None:
    ws = home / "ws_f"
    ws.mkdir()
    (ws / "hello.py").write_text("print('hi')\n", encoding="utf-8")
    jid = _dispatch(server, str(ws))
    status, body = _get(server, f"/v1/cockpit/jobs/{jid}/file?path=hello.py")
    assert status == 200
    assert body["content"] == "print('hi')\n"
    assert body["encoding"] == "utf-8"
    assert body["truncated"] is False


def test_file_binary_is_truncated_null_content(server, home: Path) -> None:
    ws = home / "ws_f2"
    ws.mkdir()
    (ws / "blob.bin").write_bytes(b"\x00\x01\x02\xff\xfe")
    jid = _dispatch(server, str(ws))
    status, body = _get(server, f"/v1/cockpit/jobs/{jid}/file?path=blob.bin")
    assert status == 200
    assert body["truncated"] is True
    assert body["content"] is None


def test_file_rejects_path_traversal(server, home: Path) -> None:
    ws = home / "ws_f3"
    ws.mkdir()
    jid = _dispatch(server, str(ws))
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, f"/v1/cockpit/jobs/{jid}/file?path=../../etc/passwd")
    assert exc.value.code == 400


def test_file_missing_is_404(server, home: Path) -> None:
    ws = home / "ws_f4"
    ws.mkdir()
    jid = _dispatch(server, str(ws))
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, f"/v1/cockpit/jobs/{jid}/file?path=nope.txt")
    assert exc.value.code == 404


def test_file_requires_path_param(server, home: Path) -> None:
    ws = home / "ws_f5"
    ws.mkdir()
    jid = _dispatch(server, str(ws))
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, f"/v1/cockpit/jobs/{jid}/file")
    assert exc.value.code == 400


# ── workspace-root guards (unvalidated workspace_path) ─────────────────────


def test_file_refuses_reading_into_hermes_home(server, home: Path) -> None:
    # The exfiltration vector: dispatch a job rooted at a parent of ~/.hermes,
    # then try to read its .env (provider keys). Must be refused, not served.
    hermes_home = home / "hermes_home"
    hermes_home.mkdir(parents=True, exist_ok=True)
    (hermes_home / ".env").write_text("OPENAI_API_KEY=sk-secret\n", encoding="utf-8")
    jid = _dispatch(server, str(home))  # workspace = parent of HERMES_HOME
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, f"/v1/cockpit/jobs/{jid}/file?path=hermes_home/.env")
    assert exc.value.code == 403


def test_file_refuses_when_workspace_is_hermes_home(server, home: Path) -> None:
    hermes_home = home / "hermes_home"
    hermes_home.mkdir(parents=True, exist_ok=True)
    (hermes_home / ".env").write_text("OPENAI_API_KEY=sk-secret\n", encoding="utf-8")
    jid = _dispatch(server, str(hermes_home))  # workspace == HERMES_HOME
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, f"/v1/cockpit/jobs/{jid}/file?path=.env")
    assert exc.value.code == 403


def test_tree_refuses_browsing_hermes_home(server, home: Path) -> None:
    hermes_home = home / "hermes_home"
    (hermes_home / "cockpit").mkdir(parents=True, exist_ok=True)
    jid = _dispatch(server, str(home))
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, f"/v1/cockpit/jobs/{jid}/tree?path=hermes_home")
    assert exc.value.code == 403


def test_tree_and_file_disabled_on_non_loopback_cockpit(server, home: Path) -> None:
    from gateway.cockpit import handlers

    ws = home / "ws_remote"
    ws.mkdir()
    (ws / "a.py").write_text("x\n", encoding="utf-8")
    jid = _dispatch(server, str(ws))
    handlers.configure_runtime(allow_remote_execute=True)
    try:
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(server, f"/v1/cockpit/jobs/{jid}/file?path=a.py")
        assert exc.value.code == 403
        with pytest.raises(urllib.error.HTTPError) as exc2:
            _get(server, f"/v1/cockpit/jobs/{jid}/tree")
        assert exc2.value.code == 403
    finally:
        handlers.configure_runtime(allow_remote_execute=False)


# ── publish/preview (read-only, pure git) ──────────────────────────────────


def _init_git_repo(ws: Path) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }

    def run(*args: str) -> None:
        subprocess.run(["git", "-C", str(ws), *args], check=True,
                       capture_output=True, env=env)

    run("init", "-q", "-b", "main")
    (ws / "a.txt").write_text("base\n", encoding="utf-8")
    run("add", "-A")
    run("commit", "-qm", "base commit")
    run("checkout", "-qb", "feature")
    (ws / "b.txt").write_text("feature\n", encoding="utf-8")
    run("add", "-A")
    run("commit", "-qm", "feat: add b")


def test_publish_preview_lists_commits_ahead_of_base(server, home: Path) -> None:
    ws = home / "repo"
    _init_git_repo(ws)
    jid = _dispatch(server, str(ws))
    status, body = _get(server, f"/v1/cockpit/jobs/{jid}/publish/preview")
    assert status == 200
    assert body["base"] == "main"
    assert body["branch"] == "feature"
    subjects = [c["subject"] for c in body["commits"]]
    assert subjects == ["feat: add b"]
    assert body["default_title"] == "feat: add b"
    assert body["default_body"] and "feat: add b" in body["default_body"]
    assert body["existing_pr_url"] is None


def test_publish_preview_honest_empty_without_git_workspace(server, home: Path) -> None:
    ws = home / "plain2"
    ws.mkdir()
    jid = _dispatch(server, str(ws))
    status, body = _get(server, f"/v1/cockpit/jobs/{jid}/publish/preview")
    assert status == 200
    assert body["commits"] == []
    assert body["default_title"] is None


def test_publish_preview_no_workspace_is_null(server) -> None:
    from hermes_cli import orchestrator as orch

    jid = orch.submit_job("Add a /healthz endpoint").id
    status, body = _get(server, f"/v1/cockpit/jobs/{jid}/publish/preview")
    assert status == 200
    assert body["remote"] is None
    assert body["commits"] == []


def test_publish_preview_unknown_job_is_404(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(server, "/v1/cockpit/jobs/nope/publish/preview")
    assert exc.value.code == 404


# ── revalidate / override ──────────────────────────────────────────────────


def _write_results(ws: Path, checks: list, blocking=None) -> None:
    vdir = ws / "validation"
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "results.json").write_text(
        json.dumps({
            "checks": checks,
            "publish_allowed": not (blocking or []),
            "blocking_failures": blocking or [],
        }),
        encoding="utf-8",
    )


def test_revalidate_reruns_and_returns_snapshot(server, home: Path) -> None:
    ws = home / "ws_re"
    ws.mkdir()
    jid = _dispatch(server, str(ws))
    status, body = _post(server, f"/v1/cockpit/jobs/{jid}/revalidate", {})
    assert status == 200
    assert body["policy"]["all_must_pass"] is True
    assert isinstance(body["gates"], list)


def test_override_records_non_critical_gate(server, home: Path) -> None:
    ws = home / "ws_ov"
    ws.mkdir()
    _write_results(ws, [
        {"name": "lint", "category": "x", "status": "warn", "summary": "style",
         "critical": False},
    ])
    jid = _dispatch(server, str(ws))
    status, body = _post(server, f"/v1/cockpit/jobs/{jid}/override",
                         {"gate_ids": ["lint"], "note": "accepted by owner"})
    assert status == 200
    gate = {g["id"]: g for g in body["gates"]}["lint"]
    assert gate["override_applied"] is True
    assert gate["override_note"] == "accepted by owner"
    # GET /validation reflects the recorded override.
    _, got = _get(server, f"/v1/cockpit/jobs/{jid}/validation")
    assert {g["id"]: g for g in got["gates"]}["lint"]["override_applied"] is True


def test_override_clears_publish_block(server, home: Path) -> None:
    ws = home / "ws_ov2"
    ws.mkdir()
    _write_results(ws, [
        {"name": "tests", "category": "x", "status": "fail", "summary": "1 failed",
         "critical": False},
    ], blocking=["tests"])
    jid = _dispatch(server, str(ws))
    status, body = _post(server, f"/v1/cockpit/jobs/{jid}/override",
                         {"gate_ids": ["tests"], "note": "flaky, overriding"})
    assert status == 200
    assert body["publish_allowed"] is True  # the only blocker is overridden


def test_override_refuses_critical_gate(server, home: Path) -> None:
    ws = home / "ws_ov3"
    ws.mkdir()
    _write_results(ws, [
        {"name": "secrets", "category": "x", "status": "fail", "summary": "leak",
         "critical": True},
    ], blocking=["secrets"])
    jid = _dispatch(server, str(ws))
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, f"/v1/cockpit/jobs/{jid}/override",
              {"gate_ids": ["secrets"], "note": "please"})
    assert exc.value.code == 403


def test_override_requires_note(server, home: Path) -> None:
    ws = home / "ws_ov4"
    ws.mkdir()
    _write_results(ws, [
        {"name": "lint", "category": "x", "status": "warn", "summary": "", "critical": False},
    ])
    jid = _dispatch(server, str(ws))
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, f"/v1/cockpit/jobs/{jid}/override", {"gate_ids": ["lint"], "note": ""})
    assert exc.value.code == 403


def test_override_unknown_gate_is_404(server, home: Path) -> None:
    ws = home / "ws_ov5"
    ws.mkdir()
    _write_results(ws, [
        {"name": "lint", "category": "x", "status": "warn", "summary": "", "critical": False},
    ])
    jid = _dispatch(server, str(ws))
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, f"/v1/cockpit/jobs/{jid}/override", {"gate_ids": ["ghost"], "note": "x"})
    assert exc.value.code == 404


def test_override_no_results_is_409(server, home: Path) -> None:
    ws = home / "ws_ov6"
    ws.mkdir()  # no validation/results.json
    jid = _dispatch(server, str(ws))
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, f"/v1/cockpit/jobs/{jid}/override", {"gate_ids": ["lint"], "note": "x"})
    assert exc.value.code == 409
