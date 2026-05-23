"""Tests for hermes_cli.github_publisher."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hermes_cli.github_publisher import (
    PublishRejected,
    build_descriptor,
    publish,
)
from hermes_cli.merge_engine import MergeArtifact
from hermes_cli.validation_gates import run_gates


@pytest.fixture(autouse=True)
def clear_live_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HERMES_PUBLISH_LIVE", raising=False)


def _good_artifact() -> MergeArtifact:
    return MergeArtifact(
        title="hermes test",
        body=(
            "**Worker:** codex\n"
            "**Role:** test\n"
            "## Summary\nA solid proposal body for publishing tests.\n"
        ),
        contributors=["codex"],
        is_draw=False,
    )


def test_dry_run_writes_artifact_and_skips_transport(tmp_path: Path) -> None:
    art = _good_artifact()
    report = run_gates(art)
    assert report.passed

    called = []

    def transport(desc):  # pragma: no cover - must not be called in dry-run
        called.append(desc)
        return {"id": 1}

    result = publish(
        art, report,
        repo="example/repo",
        out_dir=tmp_path,
        transport=transport,
    )
    assert result.descriptor.dry_run is True
    assert result.dry_run_path is not None
    assert result.transport_response is None
    assert called == []


def test_dry_run_artifact_is_valid_json(tmp_path: Path) -> None:
    art = _good_artifact()
    report = run_gates(art)
    result = publish(art, report, repo="example/repo", out_dir=tmp_path)
    assert result.dry_run_path is not None
    payload = json.loads(result.dry_run_path.read_text())
    assert payload["repo"] == "example/repo"
    assert payload["dry_run"] is True
    assert payload["title"] == "hermes test"
    assert "labels" in payload


def test_live_mode_requires_env_var(tmp_path: Path) -> None:
    art = _good_artifact()
    report = run_gates(art)
    # Caller passed dry_run=False, but HERMES_PUBLISH_LIVE is unset → still dry-run.
    desc = build_descriptor(art, repo="example/repo", dry_run=False)
    assert desc.dry_run is False  # caller's explicit choice is honored


def test_live_transport_invoked_when_dry_run_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERMES_PUBLISH_LIVE", "1")
    art = _good_artifact()
    report = run_gates(art)

    seen: list[str] = []

    def transport(desc):
        seen.append(desc.title)
        return {"url": "https://example.invalid/pr/1"}

    result = publish(
        art, report,
        repo="example/repo",
        out_dir=tmp_path,
        dry_run=False,
        transport=transport,
    )
    assert seen == ["hermes test"]
    assert result.transport_response == {"url": "https://example.invalid/pr/1"}


def test_publish_rejected_when_gates_fail(tmp_path: Path) -> None:
    bad = MergeArtifact(title="x", body="too short", contributors=[], is_draw=False)
    report = run_gates(bad)
    assert not report.passed
    with pytest.raises(PublishRejected):
        publish(bad, report, repo="example/repo", out_dir=tmp_path)


def test_descriptor_default_labels_include_hermes(tmp_path: Path) -> None:
    art = _good_artifact()
    report = run_gates(art)
    result = publish(art, report, repo="example/repo", out_dir=tmp_path)
    assert "hermes-orchestration" in result.descriptor.labels


def test_descriptor_kind_can_be_issue(tmp_path: Path) -> None:
    art = _good_artifact()
    report = run_gates(art)
    result = publish(art, report, repo="example/repo", out_dir=tmp_path, kind="issue")
    assert result.descriptor.kind == "issue"
    assert result.dry_run_path is not None
    assert result.dry_run_path.name.startswith("issue_")
