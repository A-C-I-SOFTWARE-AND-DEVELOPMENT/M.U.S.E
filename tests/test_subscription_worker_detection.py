"""Tests for subscription-aware worker lane detection + handoff packets
(muse_cli.jarvis_prime.worker_registry).

Detection is policy-only: it never requires API keys, never reads
credentials, and degrades to "unavailable" when the official CLI is not
on PATH. Detectors are injected so the tests don't depend on whether
claude/codex happen to be installed on the host.
"""

from __future__ import annotations

from muse_cli.jarvis_prime import worker_registry as wr
from muse_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE


def _available(version: str = "1.0.0"):
    return lambda: (True, version, "/usr/bin/tool", "")


def _missing():
    return lambda: (False, None, None, "not on PATH")


# ---------------------------------------------------------------------------
# canonical lanes
# ---------------------------------------------------------------------------


def test_three_canonical_lanes_registered() -> None:
    ids = set(wr.lane_ids())
    assert ids == {"claude_code_builder", "codex_reviewer", "codex_bounded_fix"}


def test_builder_edits_reviewer_does_not() -> None:
    assert wr.lane("claude_code_builder").edits_branch is True
    assert wr.lane("codex_reviewer").edits_branch is False
    assert wr.lane("codex_bounded_fix").edits_branch is True


def test_reviewer_consumes_builder_output() -> None:
    # The reviewer reads the builder's output rather than editing in parallel.
    assert wr.lane("codex_reviewer").consumes_from == "claude_code_builder"


# ---------------------------------------------------------------------------
# detection is policy-only (no keys), injectable
# ---------------------------------------------------------------------------


def test_detection_reports_available_without_any_api_key() -> None:
    statuses = wr.detect_lanes(
        claude_detector=_available("claude 1.2.3"),
        codex_detector=_available("codex 0.9"),
    )
    by = {s.lane.id: s for s in statuses}
    assert by["claude_code_builder"].available is True
    assert by["claude_code_builder"].version == "claude 1.2.3"
    assert by["codex_reviewer"].available is True


def test_detection_missing_tool_is_unavailable_not_error() -> None:
    statuses = wr.detect_lanes(
        claude_detector=_missing(), codex_detector=_missing()
    )
    assert all(s.available is False for s in statuses)
    # A missing tool yields an explanatory detail, never an exception.
    assert all(s.detail for s in statuses)


def test_detect_lane_to_dict_has_no_secret_fields() -> None:
    status = wr.detect_lane("claude_code_builder", claude_detector=_available())
    d = status.to_dict()
    # Detection surface must not carry tokens/keys.
    assert "token" not in d and "api_key" not in d and "key" not in d
    assert set(d) >= {"id", "tool", "available", "role"}


# ---------------------------------------------------------------------------
# handoff packet format
# ---------------------------------------------------------------------------


def test_handoff_packet_has_required_fields() -> None:
    packet = wr.build_handoff_packet(
        mission="Add a free-first launch path",
        repo_root="/repo",
        branch="claude/jarvis-launch",
        risk_class="RC2",
        lane_id="claude_code_builder",
        allowed_files=["muse_cli/jarvis_prime/launch.py"],
        acceptance_criteria=["hermes jarvis launch exits 0"],
        verification_commands=["pytest tests/test_jarvis_launch_cli.py"],
        rollback_plan="git revert the launch commit",
        owner_gated_actions=["production_deploy"],
    )
    d = packet.to_dict()
    for field in (
        "mission",
        "repo_root",
        "branch",
        "risk_class",
        "allowed_files",
        "forbidden_actions",
        "acceptance_criteria",
        "verification_commands",
        "rollback_plan",
        "owner_gated_actions",
    ):
        assert field in d, field
    assert packet.owner_authorization_phrase == AUTHORIZATION_PHRASE


def test_handoff_packet_injects_base_forbidden_actions() -> None:
    packet = wr.build_handoff_packet(
        mission="m", repo_root="/r", branch="b", lane_id="codex_bounded_fix"
    )
    joined = " ".join(packet.forbidden_actions).lower()
    assert "secret" in joined
    assert "default branch" in joined
    assert "authorization phrase" in joined


def test_handoff_packet_render_includes_owner_phrase_when_gated() -> None:
    packet = wr.build_handoff_packet(
        mission="m", repo_root="/r", branch="b",
        owner_gated_actions=["package_publish"],
    )
    rendered = packet.render()
    assert "package_publish" in rendered
    assert AUTHORIZATION_PHRASE in rendered


def test_build_handoff_packet_rejects_unknown_lane() -> None:
    import pytest

    with pytest.raises(KeyError):
        wr.build_handoff_packet(
            mission="m", repo_root="/r", branch="b", lane_id="nonexistent_lane"
        )
