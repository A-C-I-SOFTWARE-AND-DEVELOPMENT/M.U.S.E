"""Tests for ``muse_cli.validation`` — Phase 15 additions.

The Phase 14 surface is covered in ``tests/test_validation_gates.py``;
this file focuses on Phase 15 additions:

* ``remote.tunnel`` / ``remote.workers`` / ``remote.queue``
  discovery and reporting against a synthetic ``remote/`` tree.
* End-to-end assertions on ``results.json`` / ``summary.md`` /
  ``commands.log`` artefacts when remote checks are present.
* Re-checks of the cross-cutting invariants the new checks must
  honour (no false positives on empty workspaces, no critical
  blocking from remote state).
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

from muse_cli.validation import (
    CATEGORY_REMOTE,
    REMOTE_QUEUE_STALE_S,
    REMOTE_WORKER_STALE_S,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_SKIPPED,
    STATUS_WARN,
    CheckResult,
    ValidationRunner,
)


# ── Helpers ─────────────────────────────────────────────────────────────────


def _git(*args: str, cwd: Path) -> None:
    proc = subprocess.run(  # noqa: S603 — args are test-controlled.
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} -> {proc.returncode}: {proc.stderr}")


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "-b", "main", cwd=path)
    _git("config", "user.email", "test@example.com", cwd=path)
    _git("config", "user.name", "Test", cwd=path)
    _git("config", "commit.gpgsign", "false", cwd=path)
    (path / ".gitignore").write_text(
        "validation/\nmonitoring/\n", encoding="utf-8"
    )
    _git("add", ".gitignore", cwd=path)
    _git("commit", "--no-gpg-sign", "-q", "-m", "init", cwd=path)


def _by_name(results: list[CheckResult]) -> dict[str, CheckResult]:
    return {r.name: r for r in results}


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    _init_repo(tmp_path)
    return tmp_path


# ── Discovery ──────────────────────────────────────────────────────────────


class TestRemoteDiscovery:
    def test_no_remote_dir_skips_remote_checks(self, workspace: Path) -> None:
        report = ValidationRunner(workspace).run()
        names = {r.name for r in report.results}
        assert not any(n.startswith("remote.") for n in names)

    def test_empty_remote_dir_runs_all_three_with_skipped_status(
        self, workspace: Path
    ) -> None:
        (workspace / "remote").mkdir()
        report = ValidationRunner(workspace).run()
        by_name = _by_name(report.results)
        for n in ("remote.tunnel", "remote.workers", "remote.queue"):
            assert n in by_name, f"expected {n} to be discovered"
            assert by_name[n].status == STATUS_SKIPPED

    def test_remote_checks_never_block_publish(self, workspace: Path) -> None:
        # Even when every remote signal is broken, the publish gate
        # must stay open — remote state is observability, not a gate.
        remote = workspace / "remote"
        remote.mkdir()
        (remote / "tunnel.json").write_text(
            json.dumps({"state": "down"}), encoding="utf-8"
        )
        (remote / "queue.json").write_text("{not valid", encoding="utf-8")
        report = ValidationRunner(workspace).run()
        assert report.publish_allowed is True
        assert report.blocking_failures == []


# ── Tunnel ─────────────────────────────────────────────────────────────────


class TestRemoteTunnel:
    def test_up_state_passes(self, workspace: Path) -> None:
        remote = workspace / "remote"
        remote.mkdir()
        (remote / "tunnel.json").write_text(
            json.dumps({"state": "up", "url": "https://x.example"}),
            encoding="utf-8",
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["remote.tunnel"]
        assert result.status == STATUS_PASS
        assert result.metadata["state"] == "up"
        assert result.metadata["url"] == "https://x.example"

    def test_down_state_warns(self, workspace: Path) -> None:
        remote = workspace / "remote"
        remote.mkdir()
        (remote / "tunnel.json").write_text(
            json.dumps({"state": "down"}), encoding="utf-8"
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["remote.tunnel"]
        assert result.status == STATUS_WARN

    def test_malformed_tunnel_json_fails_check_but_not_publish(
        self, workspace: Path
    ) -> None:
        remote = workspace / "remote"
        remote.mkdir()
        (remote / "tunnel.json").write_text("{not json", encoding="utf-8")
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["remote.tunnel"]
        assert result.status == STATUS_FAIL
        # remote.tunnel is non-critical → publish stays open.
        assert "remote.tunnel" not in report.blocking_failures
        assert report.publish_allowed is True

    def test_unknown_state_warns_with_message(self, workspace: Path) -> None:
        remote = workspace / "remote"
        remote.mkdir()
        (remote / "tunnel.json").write_text(
            json.dumps({"state": "weird"}), encoding="utf-8"
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["remote.tunnel"]
        assert result.status == STATUS_WARN
        assert "weird" in result.summary


# ── Remote workers ─────────────────────────────────────────────────────────


class TestRemoteWorkerHeartbeats:
    def test_fresh_heartbeat_passes(self, workspace: Path) -> None:
        worker = workspace / "remote" / "workers" / "w-1"
        worker.mkdir(parents=True)
        (worker / "heartbeat.json").write_text(
            json.dumps({"timestamp": time.time(), "state": "idle"}),
            encoding="utf-8",
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["remote.workers"]
        assert result.status == STATUS_PASS
        assert result.metadata["fresh"] == 1

    def test_stale_heartbeat_warns(self, workspace: Path) -> None:
        worker = workspace / "remote" / "workers" / "w-1"
        worker.mkdir(parents=True)
        old = time.time() - (REMOTE_WORKER_STALE_S + 60)
        (worker / "heartbeat.json").write_text(
            json.dumps({"timestamp": old}), encoding="utf-8"
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["remote.workers"]
        assert result.status == STATUS_WARN
        assert result.metadata["fresh"] == 0
        assert len(result.metadata["stale"]) == 1

    def test_mixed_fresh_and_stale(self, workspace: Path) -> None:
        wroot = workspace / "remote" / "workers"
        (wroot / "fresh").mkdir(parents=True)
        (wroot / "stale").mkdir(parents=True)
        (wroot / "fresh" / "heartbeat.json").write_text(
            json.dumps({"timestamp": time.time()}), encoding="utf-8"
        )
        (wroot / "stale" / "heartbeat.json").write_text(
            json.dumps({"timestamp": 1.0}), encoding="utf-8"
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["remote.workers"]
        assert result.status == STATUS_WARN
        assert result.metadata["fresh"] == 1

    def test_unparseable_heartbeat_counted_as_stale(self, workspace: Path) -> None:
        worker = workspace / "remote" / "workers" / "w-1"
        worker.mkdir(parents=True)
        (worker / "heartbeat.json").write_text("not json", encoding="utf-8")
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["remote.workers"]
        assert result.status == STATUS_WARN
        assert result.metadata["fresh"] == 0

    def test_non_object_heartbeat_does_not_crash(self, workspace: Path) -> None:
        worker = workspace / "remote" / "workers" / "w-1"
        worker.mkdir(parents=True)
        # A list / null parses but isn't a dict — must degrade to
        # stale, not raise AttributeError.
        (worker / "heartbeat.json").write_text("[]", encoding="utf-8")
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["remote.workers"]
        assert result.status == STATUS_WARN
        assert result.metadata["fresh"] == 0
        assert len(result.metadata["stale"]) == 1

    def test_updated_at_key_accepted_as_timestamp(self, workspace: Path) -> None:
        # Schema docs accept `updated_at` alongside `timestamp` /
        # `heartbeat`; validation must honor it or fresh workers get
        # incorrectly flagged stale.
        worker = workspace / "remote" / "workers" / "w-1"
        worker.mkdir(parents=True)
        (worker / "heartbeat.json").write_text(
            json.dumps({"updated_at": time.time()}), encoding="utf-8"
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["remote.workers"]
        assert result.status == STATUS_PASS
        assert result.metadata["fresh"] == 1


# ── Remote queue ───────────────────────────────────────────────────────────


class TestRemoteQueue:
    def test_empty_queue_passes(self, workspace: Path) -> None:
        remote = workspace / "remote"
        remote.mkdir()
        (remote / "queue.json").write_text(
            json.dumps({"jobs": []}), encoding="utf-8"
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["remote.queue"]
        assert result.status == STATUS_PASS
        assert result.metadata["depth"] == 0

    def test_queue_with_jobs_reports_depth(self, workspace: Path) -> None:
        remote = workspace / "remote"
        remote.mkdir()
        now = time.time()
        (remote / "queue.json").write_text(
            json.dumps(
                {
                    "jobs": [
                        {"id": "a", "enqueued_at": now},
                        {"id": "b", "enqueued_at": now - 60},
                    ]
                }
            ),
            encoding="utf-8",
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["remote.queue"]
        assert result.status == STATUS_PASS
        assert result.metadata["depth"] == 2

    def test_old_queue_head_warns(self, workspace: Path) -> None:
        remote = workspace / "remote"
        remote.mkdir()
        now = time.time()
        old_age = REMOTE_QUEUE_STALE_S + 60
        (remote / "queue.json").write_text(
            json.dumps(
                {
                    "jobs": [
                        {"id": "stuck", "enqueued_at": now - old_age},
                    ]
                }
            ),
            encoding="utf-8",
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["remote.queue"]
        assert result.status == STATUS_WARN
        assert result.metadata["depth"] == 1
        assert result.metadata["oldest_age_s"] >= int(old_age)

    def test_bare_list_queue_accepted(self, workspace: Path) -> None:
        remote = workspace / "remote"
        remote.mkdir()
        (remote / "queue.json").write_text(
            json.dumps([{"id": "x"}, {"id": "y"}, {"id": "z"}]),
            encoding="utf-8",
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["remote.queue"]
        assert result.status == STATUS_PASS
        assert result.metadata["depth"] == 3

    def test_malformed_queue_fails_check_but_not_publish(
        self, workspace: Path
    ) -> None:
        remote = workspace / "remote"
        remote.mkdir()
        (remote / "queue.json").write_text("{bad", encoding="utf-8")
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["remote.queue"]
        assert result.status == STATUS_FAIL
        assert "remote.queue" not in report.blocking_failures
        assert report.publish_allowed is True

    def test_non_list_jobs_payload_fails(self, workspace: Path) -> None:
        # ``{"jobs": {...}}`` is a real schema drift — silently
        # coercing it to depth=0 would hide a broken queue writer.
        remote = workspace / "remote"
        remote.mkdir()
        (remote / "queue.json").write_text(
            json.dumps({"jobs": {"a": 1}}), encoding="utf-8"
        )
        report = ValidationRunner(workspace).run()
        result = _by_name(report.results)["remote.queue"]
        assert result.status == STATUS_FAIL
        assert "list" in result.summary


# ── Filtering ──────────────────────────────────────────────────────────────


class TestRemoteFiltering:
    def test_only_remote_drops_everything_else(self, workspace: Path) -> None:
        (workspace / "remote").mkdir()
        report = ValidationRunner(workspace, only=[CATEGORY_REMOTE]).run()
        categories = {r.category for r in report.results}
        assert categories == {CATEGORY_REMOTE}

    def test_skip_remote_drops_only_remote(self, workspace: Path) -> None:
        (workspace / "remote").mkdir()
        report = ValidationRunner(workspace, skip=[CATEGORY_REMOTE]).run()
        categories = {r.category for r in report.results}
        assert CATEGORY_REMOTE not in categories
        # The other categories should still be there (git at minimum).
        assert "git" in categories


# ── Artefact shape ─────────────────────────────────────────────────────────


class TestRemoteArtefacts:
    def test_remote_checks_show_up_in_results_json(self, workspace: Path) -> None:
        remote = workspace / "remote"
        remote.mkdir()
        (remote / "tunnel.json").write_text(
            json.dumps({"state": "up", "url": "x"}), encoding="utf-8"
        )
        ValidationRunner(workspace).run()
        data = json.loads(
            (workspace / "validation" / "results.json").read_text(encoding="utf-8")
        )
        names = {c["name"] for c in data["checks"]}
        for n in ("remote.tunnel", "remote.workers", "remote.queue"):
            assert n in names

    def test_remote_checks_show_up_in_summary_md(self, workspace: Path) -> None:
        (workspace / "remote").mkdir()
        ValidationRunner(workspace).run()
        md = (workspace / "validation" / "summary.md").read_text(encoding="utf-8")
        assert "remote.tunnel" in md
        assert "remote.workers" in md
        assert "remote.queue" in md
