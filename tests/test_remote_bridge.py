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

    def test_http_transport_is_stub(self, endpoint_root: Path, tmp_path: Path):
        endpoint = rb.RemoteEndpoint(
            name="x",
            transport=rb.TRANSPORT_HTTP,
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
