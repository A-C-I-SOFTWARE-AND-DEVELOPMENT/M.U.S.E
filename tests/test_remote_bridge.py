"""Tests for the Hermes remote-execution bridge.

Covers the Phase 10 safety properties enumerated in
``docs/remote/claude-code-windows-bridge.md``:

* The default transport is the file-drop protocol; HTTP / WebSocket /
  SSH transports are explicit stubs.
* Dispatches require both endpoint-level and per-call opt-in before
  the manifest is marked ``allow_remote_execute=True``.
* The command allowlist is enforced before the manifest is written.
* ``.env`` transfers refuse unless explicitly opted in.
* Per-job tokens authenticate status replies; mismatched tokens are
  treated as forgeries.
* Device IDs are checked against the endpoint allowlist.
* Every action is recorded in the audit log with secrets scrubbed.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from hermes_cli import remote_bridge as rb


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def endpoint_root(tmp_path: Path) -> Path:
    root = tmp_path / "shared" / "hermes-remote"
    root.mkdir(parents=True)
    return root


@pytest.fixture
def audit_log(tmp_path: Path) -> rb.AuditLog:
    return rb.AuditLog(tmp_path / "audit.log.jsonl")


def make_endpoint(
    root: Path,
    *,
    allow_remote_execute: bool = True,
    allowed_device_ids: frozenset[str] = frozenset({"jeremiah-windows"}),
    command_allowlist: tuple[str, ...] = ("claude",),
    permit_env_transfer: bool = False,
) -> rb.RemoteEndpoint:
    return rb.RemoteEndpoint(
        name="jeremiah-windows",
        transport=rb.TRANSPORT_FILE_DROP,
        workspace_root=root,
        device_id="hermes-android",
        allowed_device_ids=allowed_device_ids,
        command_allowlist=command_allowlist,
        allow_remote_execute=allow_remote_execute,
        permit_env_transfer=permit_env_transfer,
    )


@pytest.fixture
def bridge(endpoint_root: Path, audit_log: rb.AuditLog) -> rb.RemoteBridge:
    endpoint = make_endpoint(endpoint_root)
    return rb.RemoteBridge(endpoint, audit_log=audit_log, clock=lambda: 1_700_000_000.0)


# ── configuration ────────────────────────────────────────────────────────


class TestRemoteEndpoint:
    def test_default_transport_is_file_drop(self, endpoint_root: Path):
        endpoint = rb.RemoteEndpoint(name="x", workspace_root=endpoint_root)
        assert endpoint.transport == rb.TRANSPORT_FILE_DROP

    def test_blank_name_rejected(self, endpoint_root: Path):
        with pytest.raises(ValueError, match="non-empty"):
            rb.RemoteEndpoint(name="   ", workspace_root=endpoint_root)

    def test_unknown_transport_rejected(self, endpoint_root: Path):
        with pytest.raises(ValueError, match="unsupported transport"):
            rb.RemoteEndpoint(
                name="x", transport="carrier-pigeon", workspace_root=endpoint_root
            )

    def test_empty_command_allowlist_rejected(self, endpoint_root: Path):
        with pytest.raises(ValueError, match="command_allowlist"):
            rb.RemoteEndpoint(
                name="x", workspace_root=endpoint_root, command_allowlist=()
            )

    def test_from_mapping_normalises_paths_and_sets(self, endpoint_root: Path):
        endpoint = rb.RemoteEndpoint.from_mapping(
            {
                "name": "win",
                "workspace_root": str(endpoint_root),
                "allowed_device_ids": ["a", "b"],
                "command_allowlist": ["claude"],
                "notes": ["one", "two"],
            }
        )
        assert isinstance(endpoint.workspace_root, Path)
        assert endpoint.allowed_device_ids == frozenset({"a", "b"})
        assert endpoint.command_allowlist == ("claude",)
        assert endpoint.notes == ("one", "two")


# ── secret scrubbing ─────────────────────────────────────────────────────


class TestScrubSecrets:
    def test_redacts_sk_key(self):
        out = rb.scrub_secrets("authorize with sk-abc123def456ghi789jklmno")
        assert "sk-abc123" not in out
        assert "redacted" in out

    def test_redacts_github_pat(self):
        out = rb.scrub_secrets("token=ghp_1234567890abcdefghij1234567890abcdef")
        assert "ghp_1234567890" not in out

    def test_redacts_url_basic_auth(self):
        out = rb.scrub_secrets("https://alice:hunter2@example.com/x")
        assert "alice:hunter2" not in out
        # Scheme survives so the endpoint stays diagnosable.
        assert "https://" in out

    def test_redacts_jwt(self):
        token = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
            ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        out = rb.scrub_secrets(f"Auth: {token}")
        assert token not in out

    def test_redacts_authorization_header(self):
        out = rb.scrub_secrets("Authorization: Bearer abcdef.ghij.klmnopq=")
        assert "abcdef.ghij" not in out

    def test_redacts_in_nested_structures(self):
        data = {
            "command": "claude --print",
            "env": [{"OPENAI_API_KEY": "sk-zzzzzzzzzzzzzzzzzzzzzzzzzz"}],
        }
        out = rb.scrub_secrets(data)
        assert "sk-zzzzzz" not in json.dumps(out)
        # Non-secret fields untouched.
        assert out["command"] == "claude --print"

    def test_preserves_non_secret_values(self):
        assert rb.scrub_secrets(42) == 42
        assert rb.scrub_secrets(None) is None
        assert rb.scrub_secrets(True) is True
        assert rb.scrub_secrets("hello world") == "hello world"


# ── audit log ────────────────────────────────────────────────────────────


class TestAuditLog:
    def test_records_event_with_scrubbed_secrets(self, tmp_path: Path):
        log = rb.AuditLog(tmp_path / "audit.jsonl")
        log.record({"event": "test", "token": "sk-aaaaaaaaaaaaaaaaaaaaaa"})
        entries = log.read_all()
        assert len(entries) == 1
        assert entries[0]["event"] == "test"
        assert "sk-aaaaaaa" not in json.dumps(entries[0])
        assert "ts" in entries[0]

    def test_skips_malformed_lines(self, tmp_path: Path):
        path = tmp_path / "audit.jsonl"
        path.write_text('{"event":"ok"}\nnot json\n{"event":"also-ok"}\n')
        log = rb.AuditLog(path)
        entries = log.read_all()
        assert len(entries) == 2
        assert entries[0]["event"] == "ok"
        assert entries[1]["event"] == "also-ok"

    def test_read_all_on_missing_file_returns_empty(self, tmp_path: Path):
        log = rb.AuditLog(tmp_path / "does-not-exist.jsonl")
        assert log.read_all() == []


# ── dispatch ─────────────────────────────────────────────────────────────


class TestDispatch:
    def test_default_refuses_remote_execute_without_explicit_opt_in(
        self, bridge: rb.RemoteBridge
    ):
        job = bridge.dispatch(
            prompt="audit kanban swarm",
            expected_artifacts=("output.md", "status.json"),
            command="claude",
            allow_remote_execute=False,
        )
        assert job.state == rb.JobState.AWAITING_APPROVAL
        manifest = json.loads(job.manifest_path.read_text(encoding="utf-8"))
        assert manifest["allow_remote_execute"] is False

    def test_explicit_opt_in_yields_queued(self, bridge: rb.RemoteBridge):
        job = bridge.dispatch(
            prompt="audit kanban swarm",
            expected_artifacts=("output.md", "status.json"),
            command="claude",
            allow_remote_execute=True,
        )
        assert job.state == rb.JobState.QUEUED
        manifest = json.loads(job.manifest_path.read_text(encoding="utf-8"))
        assert manifest["allow_remote_execute"] is True

    def test_endpoint_opt_out_overrides_caller(self, endpoint_root: Path):
        endpoint = make_endpoint(endpoint_root, allow_remote_execute=False)
        bridge = rb.RemoteBridge(endpoint, audit_log=rb.AuditLog(endpoint_root / "audit.jsonl"))
        job = bridge.dispatch(
            prompt="x",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        assert job.state == rb.JobState.AWAITING_APPROVAL

    def test_command_not_in_allowlist_refused(self, bridge: rb.RemoteBridge):
        with pytest.raises(rb.BridgeError, match="not in the endpoint allowlist"):
            bridge.dispatch(
                prompt="hi",
                expected_artifacts=("status.json",),
                command="powershell",
                allow_remote_execute=True,
            )
        events = bridge.audit_log.read_all()
        assert any(e.get("reason") == "command_not_allowlisted" for e in events)

    def test_env_transfer_refused_by_default(
        self, bridge: rb.RemoteBridge, tmp_path: Path
    ):
        env_file = tmp_path / ".env"
        env_file.write_text("OPENAI_API_KEY=sk-deadbeefdeadbeefdeadbeef\n")
        with pytest.raises(rb.BridgeError, match="refusing to ship .env"):
            bridge.dispatch(
                prompt="hi",
                expected_artifacts=("status.json",),
                allow_remote_execute=True,
                env_files=[env_file],
            )

    def test_env_transfer_requires_both_opt_ins(
        self, endpoint_root: Path, tmp_path: Path
    ):
        # endpoint permits, but caller didn't opt into remote execute → refuse.
        endpoint = make_endpoint(endpoint_root, permit_env_transfer=True)
        bridge = rb.RemoteBridge(
            endpoint, audit_log=rb.AuditLog(tmp_path / "audit.jsonl")
        )
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=val\n")
        with pytest.raises(rb.BridgeError):
            bridge.dispatch(
                prompt="hi",
                expected_artifacts=("status.json",),
                allow_remote_execute=False,
                env_files=[env_file],
            )

    def test_env_transfer_allowed_when_both_opt_in(
        self, endpoint_root: Path, tmp_path: Path
    ):
        endpoint = make_endpoint(endpoint_root, permit_env_transfer=True)
        bridge = rb.RemoteBridge(
            endpoint, audit_log=rb.AuditLog(tmp_path / "audit.jsonl")
        )
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=val\n")
        job = bridge.dispatch(
            prompt="hi",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
            env_files=[env_file],
        )
        env_dir = job.workdir / "env"
        assert (env_dir / ".env").is_file()

    def test_blank_prompt_refused(self, bridge: rb.RemoteBridge):
        with pytest.raises(rb.BridgeError, match="prompt must be non-empty"):
            bridge.dispatch(
                prompt="   ",
                expected_artifacts=("status.json",),
                allow_remote_execute=True,
            )

    @pytest.mark.parametrize(
        "transport", [rb.TRANSPORT_WEBSOCKET, rb.TRANSPORT_SSH]
    )
    def test_websocket_and_ssh_transports_are_stubs(
        self, endpoint_root: Path, tmp_path: Path, transport: str
    ):
        endpoint = rb.RemoteEndpoint(
            name="x",
            transport=transport,
            workspace_root=endpoint_root,
            allowed_device_ids=frozenset({"a"}),
            allow_remote_execute=True,
        )
        bridge = rb.RemoteBridge(
            endpoint, audit_log=rb.AuditLog(tmp_path / "audit.jsonl")
        )
        with pytest.raises(rb.TransportNotImplementedError):
            bridge.dispatch(
                prompt="hi",
                expected_artifacts=("status.json",),
                allow_remote_execute=True,
            )
        # The refusal is audit-logged so a misread config name is visible.
        events = bridge.audit_log.read_all()
        assert any(e.get("reason") == "transport_stub" for e in events)

    def test_dispatch_writes_prompt_and_manifest(self, bridge: rb.RemoteBridge):
        job = bridge.dispatch(
            prompt="audit",
            expected_artifacts=("output.md", "status.json"),
            required_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        assert job.prompt_path.read_text(encoding="utf-8") == "audit"
        manifest = json.loads(job.manifest_path.read_text(encoding="utf-8"))
        assert manifest["job_id"] == job.job_id
        assert manifest["command"] == "claude"
        assert manifest["device_id"] == "hermes-android"
        assert manifest["auth_token"] == job.auth_token
        assert manifest["expected_artifacts"] == ["output.md", "status.json"]
        assert manifest["required_artifacts"] == ["status.json"]

    def test_dispatch_records_audit_entry(self, bridge: rb.RemoteBridge):
        job = bridge.dispatch(
            prompt="x",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        events = bridge.audit_log.read_all()
        dispatched = [e for e in events if e.get("event") == "dispatch"]
        assert len(dispatched) == 1
        assert dispatched[0]["job_id"] == job.job_id
        assert dispatched[0]["approved"] is True

    def test_prompt_secrets_not_in_audit_log(self, bridge: rb.RemoteBridge):
        bridge.dispatch(
            prompt="run with sk-zzzzzzzzzzzzzzzzzzzzzzzzzzzzz",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        body = bridge.audit_log.path.read_text(encoding="utf-8")
        assert "sk-zzzzzz" not in body

    def test_attachments_written(self, bridge: rb.RemoteBridge):
        job = bridge.dispatch(
            prompt="x",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
            attachments={"context.md": "hello"},
        )
        assert (job.workdir / "context.md").is_file()
        assert (job.workdir / "context.md").read_text() == "hello"

    def test_attachment_path_traversal_refused(self, bridge: rb.RemoteBridge):
        # ``../escape.txt`` would land outside the job workdir if accepted.
        # The bridge refuses rather than silently sanitising so callers see
        # a hard error instead of a renamed file.
        with pytest.raises(ValueError, match="unsafe filename"):
            bridge.dispatch(
                prompt="x",
                expected_artifacts=("status.json",),
                allow_remote_execute=True,
                attachments={"../escape.txt": "nope"},
            )


# ── status ───────────────────────────────────────────────────────────────


def _write_worker_status(
    workdir: Path,
    *,
    token: str,
    state: str = "completed",
    device_id: str = "jeremiah-windows",
    **extra,
) -> None:
    payload = {
        "schema": "hermes.remote.status.v1",
        "job_id": workdir.name,
        "state": state,
        "auth_token": token,
        "device_id": device_id,
        "last_seen": 1_700_000_500.0,
        "detail": "worker says hi",
        "artifacts": {"output.md": "summary"},
        "from": "windows-worker",
        **extra,
    }
    (workdir / "status.json").write_text(json.dumps(payload, indent=2))


class TestStatus:
    def test_initial_status_is_queued(self, bridge: rb.RemoteBridge):
        job = bridge.dispatch(
            prompt="x",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        status = bridge.get_status(job.job_id)
        assert status.state == rb.JobState.QUEUED

    def test_completed_status_round_trips(self, bridge: rb.RemoteBridge):
        job = bridge.dispatch(
            prompt="x",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        _write_worker_status(job.workdir, token=job.auth_token, state="completed")
        status = bridge.get_status(job.job_id)
        assert status.state == rb.JobState.COMPLETED
        assert status.artifacts == {"output.md": "summary"}
        assert status.last_seen == pytest.approx(1_700_000_500.0)

    def test_token_mismatch_rejected(self, bridge: rb.RemoteBridge):
        job = bridge.dispatch(
            prompt="x",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        _write_worker_status(job.workdir, token="forged-token")
        status = bridge.get_status(job.job_id)
        assert status.state == rb.JobState.UNKNOWN
        assert "mismatch" in status.detail
        events = bridge.audit_log.read_all()
        assert any(e.get("reason") == "status_token_mismatch" for e in events)

    def test_device_not_allowlisted_rejected(self, bridge: rb.RemoteBridge):
        job = bridge.dispatch(
            prompt="x",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        _write_worker_status(
            job.workdir, token=job.auth_token, device_id="hacker-laptop"
        )
        status = bridge.get_status(job.job_id)
        assert status.state == rb.JobState.UNKNOWN
        assert "allowlist" in status.detail
        events = bridge.audit_log.read_all()
        assert any(
            e.get("reason") == "status_device_not_allowlisted" for e in events
        )

    def test_unknown_job_id(self, bridge: rb.RemoteBridge):
        status = bridge.get_status("does-not-exist")
        assert status.state == rb.JobState.UNKNOWN

    def test_malformed_status_json(self, bridge: rb.RemoteBridge):
        job = bridge.dispatch(
            prompt="x",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        (job.workdir / "status.json").write_text("not json {{{")
        status = bridge.get_status(job.job_id)
        assert status.state == rb.JobState.UNKNOWN


# ── collect ──────────────────────────────────────────────────────────────


class TestCollect:
    def test_refuses_while_running(self, bridge: rb.RemoteBridge, tmp_path: Path):
        job = bridge.dispatch(
            prompt="x",
            expected_artifacts=("output.md", "status.json"),
            allow_remote_execute=True,
        )
        _write_worker_status(job.workdir, token=job.auth_token, state="running")
        with pytest.raises(rb.BridgeError, match="refusing to collect"):
            bridge.collect_artifacts(job.job_id, tmp_path / "out")

    def test_completed_copies_artifacts(self, bridge: rb.RemoteBridge, tmp_path: Path):
        job = bridge.dispatch(
            prompt="x",
            expected_artifacts=("output.md", "patch.diff", "status.json"),
            allow_remote_execute=True,
        )
        (job.workdir / "output.md").write_text("summary")
        (job.workdir / "patch.diff").write_text("diff")
        _write_worker_status(job.workdir, token=job.auth_token, state="completed")

        dest = tmp_path / "collected"
        files = bridge.collect_artifacts(job.job_id, dest)
        names = {p.name for p in files}
        assert "output.md" in names
        assert "patch.diff" in names
        assert "status.json" in names
        assert (dest / "output.md").read_text() == "summary"

        # Audit log records the collect.
        events = bridge.audit_log.read_all()
        assert any(e.get("event") == "collect" for e in events)


# ── cancel ───────────────────────────────────────────────────────────────


class TestCancel:
    def test_cancel_writes_sentinel_and_updates_status(
        self, bridge: rb.RemoteBridge
    ):
        job = bridge.dispatch(
            prompt="x",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        result = bridge.cancel(job.job_id, reason="user_changed_mind")
        assert result.state == rb.JobState.CANCELED
        assert (job.workdir / "cancel.json").is_file()
        status = json.loads((job.workdir / "status.json").read_text())
        assert status["state"] == "canceled"
        events = bridge.audit_log.read_all()
        assert any(e.get("event") == "cancel" for e in events)

    def test_cancel_unknown_job(self, bridge: rb.RemoteBridge):
        with pytest.raises(rb.BridgeError, match="unknown job_id"):
            bridge.cancel("nope")


# ── approval flow ────────────────────────────────────────────────────────


class TestApproval:
    def test_approve_promotes_awaiting(self, endpoint_root: Path, tmp_path: Path):
        endpoint = make_endpoint(endpoint_root, allow_remote_execute=False)
        bridge = rb.RemoteBridge(
            endpoint, audit_log=rb.AuditLog(tmp_path / "audit.jsonl")
        )
        job = bridge.dispatch(
            prompt="x",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        assert job.state == rb.JobState.AWAITING_APPROVAL
        promoted = bridge.approve(job.job_id)
        assert promoted.state == rb.JobState.QUEUED
        manifest = json.loads(job.manifest_path.read_text(encoding="utf-8"))
        assert manifest["allow_remote_execute"] is True

    def test_approve_unknown_refused(self, bridge: rb.RemoteBridge):
        with pytest.raises(rb.BridgeError):
            bridge.approve("does-not-exist")


# ── inspection ───────────────────────────────────────────────────────────


class TestListJobs:
    def test_lists_dispatched_jobs(self, bridge: rb.RemoteBridge):
        ids = []
        # Vary clock so job ids are unique.
        for i in range(3):
            bridge._clock = (lambda i=i: 1_700_000_000.0 + i)
            job = bridge.dispatch(
                prompt=f"job{i}",
                expected_artifacts=("status.json",),
                allow_remote_execute=True,
            )
            ids.append(job.job_id)
        listed = bridge.list_jobs()
        for j in ids:
            assert j in listed

    def test_empty_workspace(self, endpoint_root: Path, tmp_path: Path):
        endpoint = make_endpoint(endpoint_root)
        bridge = rb.RemoteBridge(
            endpoint, audit_log=rb.AuditLog(tmp_path / "audit.jsonl")
        )
        assert bridge.list_jobs() == []


# ── default audit path ───────────────────────────────────────────────────


class TestDefaultAuditPath:
    def test_respects_hermes_home_env(
        self,
        endpoint_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
        endpoint = make_endpoint(endpoint_root)
        bridge = rb.RemoteBridge(endpoint)
        assert tmp_path / "hermes-home" / "remote" in bridge.audit_log.path.parents


# ── http transport ───────────────────────────────────────────────────────


def _make_http_endpoint(
    root: Path,
    *,
    url: str = "https://worker.example/api/jobs",
    allow_remote_execute: bool = True,
    auth_token_env: str = "",
    http_max_attempts: int = 3,
) -> rb.RemoteEndpoint:
    return rb.RemoteEndpoint(
        name="http-worker",
        transport=rb.TRANSPORT_HTTP,
        workspace_root=root,
        device_id="hermes-android",
        allowed_device_ids=frozenset({"http-worker"}),
        allow_remote_execute=allow_remote_execute,
        auth_token_env=auth_token_env,
        http_endpoint_url=url,
        http_timeout_seconds=5.0,
        http_max_attempts=http_max_attempts,
    )


def _install_mock_client(
    monkeypatch: pytest.MonkeyPatch,
    handler,
    *,
    calls: list[httpx.Request] | None = None,
) -> None:
    """Patch ``remote_bridge.httpx.Client`` to route through a MockTransport.

    ``handler`` receives the outgoing :class:`httpx.Request` and returns an
    :class:`httpx.Response`. It may also raise (e.g. ``httpx.ConnectError``)
    to exercise the transport-error path. No real socket is ever opened.
    """

    real_client = httpx.Client

    def _wrapped(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        return handler(request)

    def _factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(transport=httpx.MockTransport(_wrapped), **kwargs)

    monkeypatch.setattr(rb.httpx, "Client", _factory)


class TestHttpTransport:
    def test_http_endpoint_requires_url(self, endpoint_root: Path):
        with pytest.raises(ValueError, match="http_endpoint_url"):
            rb.RemoteEndpoint(
                name="x",
                transport=rb.TRANSPORT_HTTP,
                workspace_root=endpoint_root,
            )

    def test_http_endpoint_rejects_non_http_scheme(self, endpoint_root: Path):
        with pytest.raises(ValueError, match="http://"):
            rb.RemoteEndpoint(
                name="x",
                transport=rb.TRANSPORT_HTTP,
                workspace_root=endpoint_root,
                http_endpoint_url="ftp://worker.example/api",
            )

    def test_success_posts_packet_and_returns_worker_state(
        self,
        endpoint_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"state": "running", "detail": "worker picked it up"},
            )

        _install_mock_client(monkeypatch, handler, calls=calls)
        endpoint = _make_http_endpoint(endpoint_root)
        bridge = rb.RemoteBridge(
            endpoint,
            audit_log=rb.AuditLog(tmp_path / "audit.jsonl"),
            clock=lambda: 1_700_000_000.0,
        )
        job = bridge.dispatch(
            prompt="audit kanban swarm",
            expected_artifacts=("output.md", "status.json"),
            allow_remote_execute=True,
        )

        # The worker's acknowledged state propagates to the RemoteJob and
        # the locally persisted status.json.
        assert job.state == rb.JobState.RUNNING
        assert job.detail == "worker picked it up"
        status = json.loads((job.workdir / "status.json").read_text())
        assert status["state"] == "running"

        # Exactly one POST carrying the full job packet was sent.
        assert len(calls) == 1
        sent = calls[0]
        assert sent.method == "POST"
        assert str(sent.url) == endpoint.http_endpoint_url
        body = json.loads(sent.content.decode("utf-8"))
        assert body["schema"] == "hermes.remote.job.v1"
        assert body["manifest"]["job_id"] == job.job_id
        assert body["manifest"]["auth_token"] == job.auth_token
        assert body["prompt"] == "audit kanban swarm"

        events = bridge.audit_log.read_all()
        assert any(e.get("event") == "http_dispatch" for e in events)

    def test_unapproved_job_is_not_posted(
        self,
        endpoint_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"state": "running"})

        _install_mock_client(monkeypatch, handler, calls=calls)
        # Endpoint opts out → job parks in awaiting_approval, no POST.
        endpoint = _make_http_endpoint(endpoint_root, allow_remote_execute=False)
        bridge = rb.RemoteBridge(
            endpoint, audit_log=rb.AuditLog(tmp_path / "audit.jsonl")
        )
        job = bridge.dispatch(
            prompt="x",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        assert job.state == rb.JobState.AWAITING_APPROVAL
        assert calls == []

    def test_bearer_token_read_from_env(
        self,
        endpoint_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["authorization"] = request.headers.get("authorization", "")
            return httpx.Response(200, json={"state": "queued"})

        _install_mock_client(monkeypatch, handler)
        monkeypatch.setenv("WORKER_BEARER", "s3cr3t-token-value")
        endpoint = _make_http_endpoint(
            endpoint_root, auth_token_env="WORKER_BEARER"
        )
        bridge = rb.RemoteBridge(
            endpoint, audit_log=rb.AuditLog(tmp_path / "audit.jsonl")
        )
        bridge.dispatch(
            prompt="x",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        assert seen["authorization"] == "Bearer s3cr3t-token-value"

    def test_token_value_never_hits_audit_log(
        self,
        endpoint_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"state": "queued"})

        _install_mock_client(monkeypatch, handler)
        monkeypatch.setenv("WORKER_BEARER", "supersecrettokenvalue123456")
        endpoint = _make_http_endpoint(
            endpoint_root, auth_token_env="WORKER_BEARER"
        )
        audit_path = tmp_path / "audit.jsonl"
        bridge = rb.RemoteBridge(endpoint, audit_log=rb.AuditLog(audit_path))
        bridge.dispatch(
            prompt="x",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        assert "supersecrettokenvalue123456" not in audit_path.read_text()

    def test_http_4xx_raises_bridge_error(
        self,
        endpoint_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, text="forbidden")

        _install_mock_client(monkeypatch, handler, calls=calls)
        endpoint = _make_http_endpoint(endpoint_root)
        bridge = rb.RemoteBridge(
            endpoint, audit_log=rb.AuditLog(tmp_path / "audit.jsonl")
        )
        with pytest.raises(rb.BridgeError, match="HTTP 403"):
            bridge.dispatch(
                prompt="x",
                expected_artifacts=("status.json",),
                allow_remote_execute=True,
            )
        # 4xx is a contract error — no retry.
        assert len(calls) == 1
        events = bridge.audit_log.read_all()
        assert any(e.get("reason") == "http_status_error" for e in events)

    def test_http_5xx_is_retried_then_fails(
        self,
        endpoint_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="unavailable")

        _install_mock_client(monkeypatch, handler, calls=calls)
        endpoint = _make_http_endpoint(endpoint_root, http_max_attempts=3)
        bridge = rb.RemoteBridge(
            endpoint, audit_log=rb.AuditLog(tmp_path / "audit.jsonl")
        )
        with pytest.raises(rb.BridgeError, match="HTTP 503"):
            bridge.dispatch(
                prompt="x",
                expected_artifacts=("status.json",),
                allow_remote_execute=True,
            )
        # Retried up to http_max_attempts before giving up.
        assert len(calls) == 3

    def test_http_5xx_then_success_recovers(
        self,
        endpoint_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        attempts = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            if attempts["n"] < 3:
                return httpx.Response(500, text="boom")
            return httpx.Response(200, json={"state": "running"})

        _install_mock_client(monkeypatch, handler)
        endpoint = _make_http_endpoint(endpoint_root, http_max_attempts=5)
        bridge = rb.RemoteBridge(
            endpoint, audit_log=rb.AuditLog(tmp_path / "audit.jsonl")
        )
        job = bridge.dispatch(
            prompt="x",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        assert job.state == rb.JobState.RUNNING
        assert attempts["n"] == 3

    def test_connection_error_raises_bridge_error(
        self,
        endpoint_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            raise httpx.ConnectError("connection refused", request=request)

        _install_mock_client(monkeypatch, handler)
        endpoint = _make_http_endpoint(endpoint_root, http_max_attempts=2)
        bridge = rb.RemoteBridge(
            endpoint, audit_log=rb.AuditLog(tmp_path / "audit.jsonl")
        )
        with pytest.raises(rb.BridgeError, match="could not reach"):
            bridge.dispatch(
                prompt="x",
                expected_artifacts=("status.json",),
                allow_remote_execute=True,
            )
        # Transport errors are retried too.
        assert len(calls) == 2
        events = bridge.audit_log.read_all()
        assert any(e.get("reason") == "http_connection_error" for e in events)

    def test_timeout_raises_bridge_error(
        self,
        endpoint_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=request)

        _install_mock_client(monkeypatch, handler)
        endpoint = _make_http_endpoint(endpoint_root, http_max_attempts=1)
        bridge = rb.RemoteBridge(
            endpoint, audit_log=rb.AuditLog(tmp_path / "audit.jsonl")
        )
        with pytest.raises(rb.BridgeError, match="timed out"):
            bridge.dispatch(
                prompt="x",
                expected_artifacts=("status.json",),
                allow_remote_execute=True,
            )
        events = bridge.audit_log.read_all()
        assert any(e.get("reason") == "http_timeout" for e in events)

    def test_local_artifacts_persist_after_http_failure(
        self,
        endpoint_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        # Even when the POST fails, the staged workspace stays on disk for
        # forensics — mirroring file-drop, which never deletes a staged job.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        _install_mock_client(monkeypatch, handler)
        endpoint = _make_http_endpoint(endpoint_root, http_max_attempts=1)
        bridge = rb.RemoteBridge(
            endpoint,
            audit_log=rb.AuditLog(tmp_path / "audit.jsonl"),
            clock=lambda: 1_700_000_000.0,
        )
        with pytest.raises(rb.BridgeError):
            bridge.dispatch(
                prompt="keepme",
                expected_artifacts=("status.json",),
                allow_remote_execute=True,
            )
        staged = bridge.list_jobs()
        assert len(staged) == 1
        workdir = endpoint_root / "jobs" / staged[0]
        assert (workdir / "prompt.md").read_text() == "keepme"
        assert (workdir / "manifest.json").is_file()

    def test_approve_posts_staged_http_job(
        self,
        endpoint_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        # An HTTP endpoint that opts out of auto-execute parks the job in
        # awaiting_approval with no POST. Approving it must then deliver the
        # packet to the worker — under HTTP nothing polls the workspace, so the
        # approval itself has to perform the hand-off.
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"state": "running", "detail": "worker accepted"}
            )

        _install_mock_client(monkeypatch, handler, calls=calls)
        endpoint = _make_http_endpoint(endpoint_root, allow_remote_execute=False)
        bridge = rb.RemoteBridge(
            endpoint,
            audit_log=rb.AuditLog(tmp_path / "audit.jsonl"),
            clock=lambda: 1_700_000_000.0,
        )
        job = bridge.dispatch(
            prompt="audit the scheduler",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        assert job.state == rb.JobState.AWAITING_APPROVAL
        assert calls == []  # nothing posted while awaiting approval

        status = bridge.approve(job.job_id)

        # The approval delivered the packet and folded the worker ack back in.
        assert status.state == rb.JobState.RUNNING
        assert status.detail == "worker accepted"
        assert len(calls) == 1
        body = json.loads(calls[0].content.decode("utf-8"))
        assert body["manifest"]["job_id"] == job.job_id
        assert body["manifest"]["allow_remote_execute"] is True
        assert body["prompt"] == "audit the scheduler"
        persisted = json.loads((job.workdir / "status.json").read_text())
        assert persisted["state"] == "running"

    def test_approve_http_delivery_failure_keeps_awaiting_approval(
        self,
        endpoint_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        # If the worker can't be reached at approval time, the job must stay
        # awaiting_approval (not silently flip to queued) so a later approve()
        # can retry the hand-off.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, text="forbidden")

        _install_mock_client(monkeypatch, handler)
        endpoint = _make_http_endpoint(
            endpoint_root, allow_remote_execute=False, http_max_attempts=1
        )
        bridge = rb.RemoteBridge(
            endpoint,
            audit_log=rb.AuditLog(tmp_path / "audit.jsonl"),
            clock=lambda: 1_700_000_000.0,
        )
        job = bridge.dispatch(
            prompt="x",
            expected_artifacts=("status.json",),
            allow_remote_execute=True,
        )
        with pytest.raises(rb.BridgeError):
            bridge.approve(job.job_id)
        persisted = json.loads((job.workdir / "status.json").read_text())
        assert persisted["state"] == rb.JobState.AWAITING_APPROVAL.value
