"""Tests for ``hermes_cli.approval_policy``.

The policy is a small state machine — these tests cover the decision
matrix one row at a time and verify the audit log records redacted
context.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli import approval_policy as ap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _req(action: ap.Action, **kwargs) -> ap.ApprovalRequest:
    kwargs.setdefault("summary", "test")
    return ap.ApprovalRequest(action=action, **kwargs)


# ---------------------------------------------------------------------------
# READ_ONLY
# ---------------------------------------------------------------------------


class TestReadOnly:
    def test_safe_read_is_allowed(self):
        r = ap.evaluate(_req(ap.Action.SAFE_READ), autonomy=ap.AutonomyLevel.READ_ONLY)
        assert r.decision is ap.Decision.ALLOW

    @pytest.mark.parametrize(
        "action",
        [
            ap.Action.SAFE_LOCAL_WRITE,
            ap.Action.LOCAL_COMMAND,
            ap.Action.DESTRUCTIVE_COMMAND,
            ap.Action.GITHUB_PUSH,
            ap.Action.SUPABASE_CHANGE,
            ap.Action.VERCEL_DEPLOY,
            ap.Action.SECRET_ACCESS,
        ],
    )
    def test_other_actions_denied(self, action):
        r = ap.evaluate(_req(action), autonomy=ap.AutonomyLevel.READ_ONLY)
        assert r.decision is ap.Decision.DENY
        assert not r.needs_prompt


# ---------------------------------------------------------------------------
# ASSISTED (default)
# ---------------------------------------------------------------------------


class TestAssisted:
    def test_safe_read_allowed(self):
        r = ap.evaluate(_req(ap.Action.SAFE_READ), autonomy=ap.AutonomyLevel.ASSISTED)
        assert r.decision is ap.Decision.ALLOW

    def test_safe_local_write_confirms(self):
        r = ap.evaluate(
            _req(ap.Action.SAFE_LOCAL_WRITE), autonomy=ap.AutonomyLevel.ASSISTED
        )
        assert r.decision is ap.Decision.CONFIRM
        assert r.needs_prompt

    def test_local_command_confirms(self):
        r = ap.evaluate(
            _req(ap.Action.LOCAL_COMMAND), autonomy=ap.AutonomyLevel.ASSISTED
        )
        assert r.decision is ap.Decision.CONFIRM

    def test_github_push_confirms(self):
        r = ap.evaluate(
            _req(ap.Action.GITHUB_PUSH, branch="feature", remote_branch="feature"),
            autonomy=ap.AutonomyLevel.ASSISTED,
        )
        assert r.decision is ap.Decision.CONFIRM
        assert r.needs_prompt


# ---------------------------------------------------------------------------
# AUTONOMOUS
# ---------------------------------------------------------------------------


class TestAutonomous:
    @pytest.mark.parametrize(
        "action",
        [
            ap.Action.SAFE_READ,
            ap.Action.SAFE_LOCAL_WRITE,
            ap.Action.LOCAL_COMMAND,
            ap.Action.SECRET_ACCESS,
            ap.Action.CONTINUOUS_LISTEN,
        ],
    )
    def test_auto_allow_set(self, action):
        r = ap.evaluate(_req(action), autonomy=ap.AutonomyLevel.AUTONOMOUS)
        assert r.decision is ap.Decision.ALLOW

    def test_destructive_still_confirms(self):
        r = ap.evaluate(
            _req(ap.Action.DESTRUCTIVE_COMMAND), autonomy=ap.AutonomyLevel.AUTONOMOUS
        )
        assert r.decision is ap.Decision.CONFIRM
        assert r.needs_prompt

    def test_supabase_change_confirms(self):
        r = ap.evaluate(
            _req(ap.Action.SUPABASE_CHANGE, target="orchestrator_db"),
            autonomy=ap.AutonomyLevel.AUTONOMOUS,
        )
        assert r.decision is ap.Decision.CONFIRM

    def test_vercel_deploy_confirms(self):
        r = ap.evaluate(
            _req(ap.Action.VERCEL_DEPLOY, target="prod"),
            autonomy=ap.AutonomyLevel.AUTONOMOUS,
        )
        assert r.decision is ap.Decision.CONFIRM


# ---------------------------------------------------------------------------
# YOLO
# ---------------------------------------------------------------------------


class TestYolo:
    @pytest.mark.parametrize(
        "action",
        [
            ap.Action.SAFE_READ,
            ap.Action.SAFE_LOCAL_WRITE,
            ap.Action.LOCAL_COMMAND,
            ap.Action.DESTRUCTIVE_COMMAND,
            ap.Action.REMOTE_COMMAND,
            ap.Action.SECRET_ACCESS,
            ap.Action.SUPABASE_CHANGE,
            ap.Action.VERCEL_DEPLOY,
            ap.Action.CONTINUOUS_LISTEN,
        ],
    )
    def test_most_actions_allowed(self, action):
        r = ap.evaluate(
            _req(action, target="something"), autonomy=ap.AutonomyLevel.YOLO
        )
        assert r.decision is ap.Decision.ALLOW

    def test_github_push_to_feature_branch_allowed(self):
        r = ap.evaluate(
            _req(
                ap.Action.GITHUB_PUSH,
                branch="feature/x",
                remote_branch="feature/x",
            ),
            autonomy=ap.AutonomyLevel.YOLO,
        )
        assert r.decision is ap.Decision.ALLOW

    def test_remote_secret_transfer_without_target_denied(self):
        r = ap.evaluate(
            _req(ap.Action.REMOTE_SECRET_TRANSFER, target=""),
            autonomy=ap.AutonomyLevel.YOLO,
        )
        assert r.decision is ap.Decision.DENY

    def test_remote_secret_transfer_with_target_still_confirms_in_yolo(self):
        # YOLO_HARD_LIMITS keeps this in the confirm path.
        r = ap.evaluate(
            _req(ap.Action.REMOTE_SECRET_TRANSFER, target="worker-01"),
            autonomy=ap.AutonomyLevel.YOLO,
        )
        assert r.decision is ap.Decision.CONFIRM

    def test_public_tunnel_without_allowlist_denied(self):
        r = ap.evaluate(
            _req(ap.Action.PUBLIC_TUNNEL, target="cloudflared"),
            autonomy=ap.AutonomyLevel.YOLO,
        )
        assert r.decision is ap.Decision.DENY

    def test_public_tunnel_with_allowlist_still_confirms(self):
        r = ap.evaluate(
            _req(
                ap.Action.PUBLIC_TUNNEL,
                target="cloudflared",
                details={"allowlisted": True},
            ),
            autonomy=ap.AutonomyLevel.YOLO,
        )
        assert r.decision is ap.Decision.CONFIRM


# ---------------------------------------------------------------------------
# Always-deny rules
# ---------------------------------------------------------------------------


class TestAlwaysDeny:
    def test_force_push_to_main_denied(self):
        r = ap.evaluate(
            _req(
                ap.Action.GITHUB_FORCE_PUSH,
                branch="feature",
                remote_branch="main",
            ),
            autonomy=ap.AutonomyLevel.YOLO,
        )
        assert r.decision is ap.Decision.DENY

    def test_force_push_to_master_denied(self):
        r = ap.evaluate(
            _req(
                ap.Action.GITHUB_FORCE_PUSH,
                branch="feature",
                remote_branch="master",
            ),
            autonomy=ap.AutonomyLevel.AUTONOMOUS,
        )
        assert r.decision is ap.Decision.DENY

    def test_force_push_to_feature_branch_confirms(self):
        r = ap.evaluate(
            _req(
                ap.Action.GITHUB_FORCE_PUSH,
                branch="feature/x",
                remote_branch="feature/x",
            ),
            autonomy=ap.AutonomyLevel.ASSISTED,
        )
        assert r.decision is ap.Decision.CONFIRM

    def test_custom_protected_branches(self):
        r = ap.evaluate(
            _req(
                ap.Action.GITHUB_FORCE_PUSH,
                branch="feature",
                remote_branch="staging",
            ),
            autonomy=ap.AutonomyLevel.YOLO,
            protected_branches=frozenset({"staging"}),
        )
        assert r.decision is ap.Decision.DENY


# ---------------------------------------------------------------------------
# Env var autonomy detection
# ---------------------------------------------------------------------------


class TestAutonomyFromEnv:
    def test_default_is_assisted(self, monkeypatch):
        monkeypatch.delenv("HERMES_AUTONOMY", raising=False)
        r = ap.evaluate(_req(ap.Action.SAFE_LOCAL_WRITE))
        assert r.decision is ap.Decision.CONFIRM

    def test_yolo_from_env(self, monkeypatch):
        monkeypatch.setenv("HERMES_AUTONOMY", "yolo")
        r = ap.evaluate(_req(ap.Action.SAFE_LOCAL_WRITE))
        assert r.decision is ap.Decision.ALLOW

    def test_invalid_env_falls_back(self, monkeypatch):
        monkeypatch.setenv("HERMES_AUTONOMY", "wishful")
        # Should fall back to assisted, which confirms safe writes.
        r = ap.evaluate(_req(ap.Action.SAFE_LOCAL_WRITE))
        assert r.decision is ap.Decision.CONFIRM


# ---------------------------------------------------------------------------
# record_decision
# ---------------------------------------------------------------------------


class TestRecordDecision:
    def test_appends_a_json_line(self, tmp_path: Path):
        log = tmp_path / "approval.log"
        req = _req(
            ap.Action.GITHUB_PUSH,
            summary="push feature branch",
            target="origin/feature",
            branch="feature",
            remote_branch="feature",
        )
        result = ap.evaluate(req, autonomy=ap.AutonomyLevel.ASSISTED)
        ap.record_decision(req, result, log_path=log)
        contents = log.read_text(encoding="utf-8").strip().splitlines()
        assert len(contents) == 1
        entry = json.loads(contents[0])
        assert entry["action"] == "github_push"
        assert entry["decision"] == "confirm"
        assert entry["branch"] == "feature"

    def test_redacts_secret_in_summary(self, tmp_path: Path):
        log = tmp_path / "approval.log"
        token = "sk-" + "A" * 40
        req = _req(
            ap.Action.SECRET_ACCESS,
            summary=f"fetch OPENAI_API_KEY for caller (cached={token})",
            target="OPENAI_API_KEY",
        )
        result = ap.evaluate(req, autonomy=ap.AutonomyLevel.AUTONOMOUS)
        ap.record_decision(req, result, log_path=log)
        body = log.read_text(encoding="utf-8")
        assert token not in body
        assert "<redacted:" in body

    def test_redacts_details_values(self, tmp_path: Path):
        log = tmp_path / "approval.log"
        token = "ghp_" + "C" * 36
        req = _req(
            ap.Action.REMOTE_SECRET_TRANSFER,
            summary="ship token to worker",
            target="worker-01",
            details={"value": token},
        )
        result = ap.evaluate(req, autonomy=ap.AutonomyLevel.AUTONOMOUS)
        ap.record_decision(req, result, log_path=log)
        body = log.read_text(encoding="utf-8")
        assert token not in body


# ---------------------------------------------------------------------------
# Sanity: every Action has at least one branch.
# ---------------------------------------------------------------------------


def test_every_action_has_a_decision_under_assisted():
    for action in ap.Action:
        req = _req(action, target="x", details={"allowlisted": True})
        r = ap.evaluate(req, autonomy=ap.AutonomyLevel.ASSISTED)
        assert r.decision in (ap.Decision.ALLOW, ap.Decision.CONFIRM, ap.Decision.DENY)
