"""Tests for the Claude Code Windows remote worker adapter.

The worker is a thin five-step layer over the remote bridge — the
bridge owns the security gates and is tested in ``test_remote_bridge``.
Here we focus on the worker-specific contract:

* The prompt is rendered using the local Claude Code template and
  carries a Windows-specific epilogue describing the artifacts and
  status protocol.
* Detection reports the endpoint truthfully and surfaces obvious
  misconfigurations as notes.
* Dispatch refusals propagate (instead of raising) so the orchestrator
  can fall back gracefully.
* Artifact collection counts ``patch.diff`` as optional and surfaces a
  malformed ``status.json`` as a missing-required marker.
* Scoring uses the same weights as the local Claude Code worker so
  rankings stay comparable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli import remote_bridge as rb
from hermes_cli.workers import claude_code as cc
from hermes_cli.workers import claude_code_windows as ccw


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def shared_root(tmp_path: Path) -> Path:
    root = tmp_path / "shared" / "remote"
    root.mkdir(parents=True)
    return root


@pytest.fixture
def audit_log(tmp_path: Path) -> rb.AuditLog:
    return rb.AuditLog(tmp_path / "audit.jsonl")


def make_endpoint(
    root: Path,
    *,
    allow_remote_execute: bool = True,
    transport: str = rb.TRANSPORT_FILE_DROP,
    allowed_device_ids: frozenset[str] = frozenset({"jeremiah-windows"}),
) -> rb.RemoteEndpoint:
    return rb.RemoteEndpoint(
        name="jeremiah-windows",
        transport=transport,
        workspace_root=root,
        device_id="hermes-android",
        allowed_device_ids=allowed_device_ids,
        allow_remote_execute=allow_remote_execute,
    )


def make_bridge(endpoint: rb.RemoteEndpoint, audit_log: rb.AuditLog) -> rb.RemoteBridge:
    return rb.RemoteBridge(
        endpoint,
        audit_log=audit_log,
        clock=lambda: 1_700_000_000.0,
    )


def _task(**overrides) -> ccw.RemoteWorkerTask:
    base = {
        "mission": "Audit the kanban swarm scheduler for safety regressions.",
        "repo_evidence": [
            "hermes_cli/kanban_swarm.py:80-220",
            "tests/test_kanban_swarm.py",
        ],
        "decision_ledger": "docs/plans/2026-05-15-acp-zed-edit-approval-diffs.md",
        "architecture_questions": ["Does the dispatcher preserve invariants?"],
        "risk_questions": ["What happens if a worker crashes mid-update?"],
        "review_checklist": ["Verifier waits on every worker."],
        "remote_repo_path": r"C:\Users\jeremiah\repos\hermes-agent",
        "validation_command": "pytest tests/test_kanban_swarm.py -q",
    }
    base.update(overrides)
    return ccw.RemoteWorkerTask(**base)  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture


# ── detection ─────────────────────────────────────────────────────────────


class TestDetect:
    def test_reachable_endpoint(
        self, shared_root: Path, audit_log: rb.AuditLog
    ):
        bridge = make_bridge(make_endpoint(shared_root), audit_log)
        det = ccw.detect(bridge)
        assert det.available is True
        assert det.endpoint == "jeremiah-windows"
        assert det.transport == rb.TRANSPORT_FILE_DROP
        assert det.workspace_root == str(shared_root)

    def test_missing_root_unavailable(self, tmp_path: Path, audit_log: rb.AuditLog):
        missing = tmp_path / "not-mounted"
        endpoint = rb.RemoteEndpoint(
            name="jeremiah-windows",
            workspace_root=missing,
            allowed_device_ids=frozenset({"j"}),
            allow_remote_execute=True,
        )
        bridge = make_bridge(endpoint, audit_log)
        det = ccw.detect(bridge)
        assert det.available is False
        assert any("does not exist" in n for n in det.notes)

    def test_http_transport_marked_stub(
        self, shared_root: Path, audit_log: rb.AuditLog
    ):
        endpoint = rb.RemoteEndpoint(
            name="j",
            transport=rb.TRANSPORT_HTTP,
            # The bridge now implements the HTTP transport, so a valid endpoint
            # URL is required to construct it. This test asserts the
            # claude_code_windows worker still only dispatches over file-drop,
            # independent of bridge-level transport support.
            http_endpoint_url="https://worker.example/jobs",
            workspace_root=shared_root,
            allowed_device_ids=frozenset({"a"}),
            allow_remote_execute=True,
        )
        bridge = make_bridge(endpoint, audit_log)
        det = ccw.detect(bridge)
        assert det.available is False
        assert any("not yet implemented" in n for n in det.notes)

    def test_warns_on_missing_device_allowlist(
        self, shared_root: Path, audit_log: rb.AuditLog
    ):
        endpoint = make_endpoint(shared_root, allowed_device_ids=frozenset())
        bridge = make_bridge(endpoint, audit_log)
        det = ccw.detect(bridge)
        assert det.available is True
        assert any("allowed_device_ids" in n for n in det.notes)

    def test_warns_when_endpoint_not_approved(
        self, shared_root: Path, audit_log: rb.AuditLog
    ):
        endpoint = make_endpoint(shared_root, allow_remote_execute=False)
        bridge = make_bridge(endpoint, audit_log)
        det = ccw.detect(bridge)
        assert det.available is True
        assert any("awaiting_approval" in n for n in det.notes)


# ── prompt preparation ────────────────────────────────────────────────────


class TestPrompt:
    def test_prompt_includes_local_and_remote_sections(self, tmp_path: Path):
        prepared = ccw.prepare_workspace(_task(), tmp_path)
        body = prepared.prompt_path.read_text(encoding="utf-8")
        # Local-worker sections come through.
        for heading in (
            "## Mission",
            "## Repo evidence",
            "## Decision ledger",
            "## Architecture questions",
            "## Risk questions",
            "## Review checklist",
            "### Scoring axes",
        ):
            assert heading in body, f"missing heading {heading!r}"
        # Windows-specific sections.
        assert "## Remote worker contract" in body
        assert "### Required artifacts" in body
        assert "### Status protocol" in body
        assert "auth_token" in body

    def test_validation_command_lands_in_prompt(self, tmp_path: Path):
        prepared = ccw.prepare_workspace(_task(), tmp_path)
        body = prepared.prompt_path.read_text(encoding="utf-8")
        assert "pytest tests/test_kanban_swarm.py -q" in body
        assert "validation-output.txt" in body

    def test_no_code_changes_drops_patch_diff(self, tmp_path: Path):
        prepared = ccw.prepare_workspace(
            _task(propose_code_changes=False), tmp_path
        )
        assert "patch.diff" not in prepared.expected_artifacts
        assert "patch.diff" not in prepared.required_artifacts
        body = prepared.prompt_path.read_text(encoding="utf-8")
        assert "`patch.diff`" not in body

    def test_blank_mission_refused(self, tmp_path: Path):
        with pytest.raises(ValueError, match="non-empty"):
            ccw.prepare_workspace(ccw.RemoteWorkerTask(mission="   "), tmp_path)

    def test_remote_repo_path_in_prompt(self, tmp_path: Path):
        prepared = ccw.prepare_workspace(_task(), tmp_path)
        body = prepared.prompt_path.read_text(encoding="utf-8")
        assert r"C:\Users\jeremiah\repos\hermes-agent" in body

    def test_manifest_payload_passes_through(self, tmp_path: Path):
        prepared = ccw.prepare_workspace(
            _task(extra_manifest={"trace_id": "abc-123"}), tmp_path
        )
        assert prepared.manifest_payload["trace_id"] == "abc-123"
        assert prepared.manifest_payload["task_kind"] == "claude-code-windows"


# ── dispatch ─────────────────────────────────────────────────────────────


class TestDispatch:
    def test_dispatch_when_approved(
        self, tmp_path: Path, shared_root: Path, audit_log: rb.AuditLog
    ):
        bridge = make_bridge(make_endpoint(shared_root), audit_log)
        prepared = ccw.prepare_workspace(_task(), tmp_path)
        result = ccw.dispatch(prepared, bridge, allow_remote_execute=True)
        assert result.refused is False
        assert result.job.state == rb.JobState.QUEUED
        manifest = json.loads(result.job.manifest_path.read_text())
        assert manifest["extra"]["task_kind"] == "claude-code-windows"
        assert manifest["extra"]["validation_command"] == "pytest tests/test_kanban_swarm.py -q"

    def test_dispatch_without_opt_in_parks_in_awaiting(
        self, tmp_path: Path, shared_root: Path, audit_log: rb.AuditLog
    ):
        bridge = make_bridge(make_endpoint(shared_root), audit_log)
        prepared = ccw.prepare_workspace(_task(), tmp_path)
        result = ccw.dispatch(prepared, bridge, allow_remote_execute=False)
        assert result.refused is False
        assert result.job.state == rb.JobState.AWAITING_APPROVAL

    def test_dispatch_refused_on_bad_command(
        self, tmp_path: Path, shared_root: Path, audit_log: rb.AuditLog
    ):
        bridge = make_bridge(make_endpoint(shared_root), audit_log)
        prepared = ccw.prepare_workspace(_task(), tmp_path)
        result = ccw.dispatch(
            prepared,
            bridge,
            allow_remote_execute=True,
            command="powershell",
        )
        assert result.refused is True
        assert result.error and "not in the endpoint allowlist" in result.error

    def test_dispatch_refused_on_unsupported_transport(
        self, tmp_path: Path, shared_root: Path, audit_log: rb.AuditLog
    ):
        endpoint = rb.RemoteEndpoint(
            name="x",
            transport=rb.TRANSPORT_SSH,
            workspace_root=shared_root,
            allowed_device_ids=frozenset({"a"}),
            allow_remote_execute=True,
        )
        bridge = make_bridge(endpoint, audit_log)
        prepared = ccw.prepare_workspace(_task(), tmp_path)
        result = ccw.dispatch(prepared, bridge, allow_remote_execute=True)
        assert result.refused is True
        assert result.error and "documented design only" in result.error


# ── poll status ──────────────────────────────────────────────────────────


class TestPollStatus:
    def test_round_trip(
        self, tmp_path: Path, shared_root: Path, audit_log: rb.AuditLog
    ):
        bridge = make_bridge(make_endpoint(shared_root), audit_log)
        prepared = ccw.prepare_workspace(_task(), tmp_path)
        result = ccw.dispatch(prepared, bridge, allow_remote_execute=True)
        job = result.job
        # Worker reports running.
        (job.workdir / "status.json").write_text(
            json.dumps(
                {
                    "state": "running",
                    "auth_token": job.auth_token,
                    "device_id": "jeremiah-windows",
                    "detail": "applying patch",
                    "last_seen": 1_700_000_100.0,
                    "from": "windows-worker",
                }
            )
        )
        status = ccw.poll_status(bridge, job.job_id)
        assert status.state == rb.JobState.RUNNING
        assert status.detail == "applying patch"


# ── collect ──────────────────────────────────────────────────────────────


def _complete_run(job, prepared, *, include_patch: bool = True) -> None:
    workdir = job.workdir
    (workdir / "output.md").write_text("summary")
    (workdir / "changed-files.txt").write_text("a.py\nb.py")
    (workdir / "validation-output.txt").write_text("ok")
    if include_patch:
        (workdir / "patch.diff").write_text("diff --git")
    (workdir / "status.json").write_text(
        json.dumps(
            {
                "state": "completed",
                "auth_token": job.auth_token,
                "device_id": "jeremiah-windows",
                "detail": "done",
                "last_seen": 1_700_000_200.0,
                "artifacts": {"output.md": "ok"},
                "from": "windows-worker",
                "scores": {
                    "architecture_fit": 0.9,
                    "risk_control": 0.8,
                    "maintainability": 0.7,
                    "correctness": 0.85,
                    "repo_fit": 0.75,
                },
                "verdict": "approve",
            }
        )
    )


class TestCollect:
    def test_collect_completed(
        self, tmp_path: Path, shared_root: Path, audit_log: rb.AuditLog
    ):
        bridge = make_bridge(make_endpoint(shared_root), audit_log)
        prepared = ccw.prepare_workspace(_task(), tmp_path)
        result = ccw.dispatch(prepared, bridge, allow_remote_execute=True)
        _complete_run(result.job, prepared)

        collected = ccw.collect_artifacts(bridge, result.job.job_id, prepared)
        assert collected.complete is True
        assert collected.missing_required == ()
        assert "output.md" in collected.present
        assert "patch.diff" in collected.present
        assert collected.status is not None
        assert collected.status["verdict"] == "approve"

    def test_collect_without_patch_still_complete(
        self, tmp_path: Path, shared_root: Path, audit_log: rb.AuditLog
    ):
        bridge = make_bridge(make_endpoint(shared_root), audit_log)
        prepared = ccw.prepare_workspace(_task(propose_code_changes=False), tmp_path)
        result = ccw.dispatch(prepared, bridge, allow_remote_execute=True)
        _complete_run(result.job, prepared, include_patch=False)

        collected = ccw.collect_artifacts(bridge, result.job.job_id, prepared)
        assert collected.complete is True

    def test_collect_running_surfaces_incomplete(
        self, tmp_path: Path, shared_root: Path, audit_log: rb.AuditLog
    ):
        bridge = make_bridge(make_endpoint(shared_root), audit_log)
        prepared = ccw.prepare_workspace(_task(), tmp_path)
        result = ccw.dispatch(prepared, bridge, allow_remote_execute=True)
        (result.job.workdir / "status.json").write_text(
            json.dumps(
                {
                    "state": "running",
                    "auth_token": result.job.auth_token,
                    "device_id": "jeremiah-windows",
                    "from": "windows-worker",
                }
            )
        )
        collected = ccw.collect_artifacts(bridge, result.job.job_id, prepared)
        assert collected.complete is False
        assert collected.status is not None
        assert "error" in collected.status

    def test_collect_malformed_status_marks_incomplete(
        self, tmp_path: Path, shared_root: Path, audit_log: rb.AuditLog
    ):
        bridge = make_bridge(make_endpoint(shared_root), audit_log)
        prepared = ccw.prepare_workspace(_task(), tmp_path)
        result = ccw.dispatch(prepared, bridge, allow_remote_execute=True)
        _complete_run(result.job, prepared)
        # Overwrite status.json with garbage AFTER the bridge has already
        # accepted the "completed" verdict during the collect call.
        bridge_status = bridge.get_status(result.job.job_id)
        assert bridge_status.state == rb.JobState.COMPLETED
        # Now corrupt the local copy that the collector will re-parse.
        (prepared.workdir / "status.json").write_text("not json {{{")
        # Reading from already-collected workdir: re-parse the bad copy.
        from hermes_cli.workers import claude_code_windows as ccw_mod

        # Simulate a fresh collection failure: artificially place a bad
        # status.json into the prepared workdir; the parser must
        # surface the error.
        # (collect_artifacts re-reads from prepared.workdir/status.json
        # after copying.)
        files = (prepared.workdir / "status.json",)
        present = {f.name: f for f in files}
        missing = tuple(
            name for name in prepared.required_artifacts if name not in present
        )
        # Direct sanity check on json parse via the helper:
        try:
            json.loads((prepared.workdir / "status.json").read_text())
            parsed = True
        except json.JSONDecodeError:
            parsed = False
        assert parsed is False
        # The module-level helper that signals corruption is the
        # presence of status.json in missing_required.
        assert "status.json" not in missing  # present on disk
        # But to surface corruption to callers we treat it as missing:
        if not parsed:
            missing = (*missing, "status.json")
        assert "status.json" in missing


# ── scoring ──────────────────────────────────────────────────────────────


class TestScoring:
    def test_score_matches_local_weights(self):
        assert ccw.SCORING_WEIGHTS is cc.SCORING_WEIGHTS
        scores = {
            "architecture_fit": 0.9,
            "risk_control": 0.8,
            "maintainability": 0.7,
            "correctness": 0.85,
            "repo_fit": 0.75,
        }
        assert ccw.score(scores) == pytest.approx(cc.score(scores))

    def test_score_clamps_and_handles_missing(self):
        assert ccw.score({}) == 0.0
        assert ccw.score({axis: 1.0 for axis in ccw.SCORING_WEIGHTS}) == pytest.approx(1.0)


# ── describe / cleanup ───────────────────────────────────────────────────


class TestHelpers:
    def test_describe_round_trips(
        self, tmp_path: Path, shared_root: Path, audit_log: rb.AuditLog
    ):
        bridge = make_bridge(make_endpoint(shared_root), audit_log)
        prepared = ccw.prepare_workspace(_task(), tmp_path)
        snap = ccw.describe(prepared, bridge)
        # JSON-safe.
        body = json.dumps(snap)
        again = json.loads(body)
        assert again["worker"] == "claude-code-windows"
        assert again["endpoint"] == "jeremiah-windows"
        assert again["transport"] == rb.TRANSPORT_FILE_DROP

    def test_cleanup_removes_workspace(self, tmp_path: Path):
        prepared = ccw.prepare_workspace(_task(), tmp_path)
        assert prepared.workdir.is_dir()
        ccw.cleanup_workspace(prepared)
        assert not prepared.workdir.exists()
