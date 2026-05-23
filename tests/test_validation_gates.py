"""Tests for hermes_cli.validation_gates."""

from __future__ import annotations

import pytest

from hermes_cli.merge_engine import MergeArtifact
from hermes_cli.validation_gates import (
    GATES,
    gate_policy,
    gate_secrets,
    gate_size,
    gate_structure,
    gate_unicode,
    run_gates,
)


def _good_artifact(body: str | None = None) -> MergeArtifact:
    return MergeArtifact(
        title="ok",
        body=body or (
            "**Worker:** codex\n"
            "**Role:** test\n"
            "## Summary\nA reasonable proposal body that is long enough.\n"
        ),
        contributors=["codex"],
        is_draw=False,
    )


def test_five_gates_are_registered() -> None:
    assert len(GATES) == 5
    assert {g.__name__ for g in GATES} == {
        "gate_structure", "gate_size", "gate_secrets", "gate_unicode", "gate_policy",
    }


def test_run_gates_all_pass_on_good_artifact() -> None:
    report = run_gates(_good_artifact())
    assert report.passed
    assert len(report.gates) == 5
    assert all(g.passed for g in report.gates)


def test_structure_gate_fails_when_markers_missing() -> None:
    art = MergeArtifact(title="x", body="just text\n", contributors=[], is_draw=False)
    assert not gate_structure(art).passed


def test_structure_gate_draw_path() -> None:
    art = MergeArtifact(
        title="x",
        body="Arbiter flagged a draw: tied scores\n",
        contributors=["a", "b"],
        is_draw=True,
    )
    assert gate_structure(art).passed


def test_size_gate_rejects_too_short() -> None:
    art = MergeArtifact(title="x", body="x", contributors=[], is_draw=False)
    assert not gate_size(art).passed


def test_size_gate_rejects_too_long() -> None:
    art = MergeArtifact(title="x", body="x" * 100_000, contributors=[], is_draw=False)
    assert not gate_size(art).passed


@pytest.mark.parametrize("payload", [
    "AKIAABCDEFGHIJKLMNOP",
    "sk-" + "a" * 30,
    "ghp_" + "a" * 35,
    "xoxb-1234567890-abcdef",
    "-----BEGIN PRIVATE KEY-----",
    "Authorization: Bearer abcdef1234567890ABCDEF12345",
])
def test_secrets_gate_catches_credentials(payload: str) -> None:
    art = MergeArtifact(
        title="x",
        body="**Worker:** x\n**Role:** test\n## Summary\n" + payload,
        contributors=[], is_draw=False,
    )
    assert not gate_secrets(art).passed


def test_secrets_gate_clean_body() -> None:
    assert gate_secrets(_good_artifact()).passed


def test_unicode_gate_rejects_nul() -> None:
    art = MergeArtifact(title="x", body="abc\x00def", contributors=[], is_draw=False)
    assert not gate_unicode(art).passed


def test_unicode_gate_rejects_bom() -> None:
    art = MergeArtifact(title="x", body="﻿hello", contributors=[], is_draw=False)
    assert not gate_unicode(art).passed


def test_unicode_gate_accepts_emoji() -> None:
    art = MergeArtifact(title="x", body="hello world", contributors=[], is_draw=False)
    assert gate_unicode(art).passed


def test_policy_gate_rejects_destructive_commands() -> None:
    art = MergeArtifact(
        title="x",
        body="**Worker:** x\n**Role:** test\n## Summary\nrun rm -rf /etc to clean up.",
        contributors=[], is_draw=False,
    )
    assert not gate_policy(art).passed


def test_policy_gate_accepts_safe_text() -> None:
    art = MergeArtifact(
        title="x",
        body="**Worker:** x\n**Role:** test\n## Summary\nuse rm -rf /tmp/scratch for cleanup.",
        contributors=[], is_draw=False,
    )
    assert gate_policy(art).passed


def test_report_to_dict_round_trip() -> None:
    report = run_gates(_good_artifact())
    payload = report.to_dict()
    assert payload["passed"] is True
    assert len(payload["gates"]) == 5
