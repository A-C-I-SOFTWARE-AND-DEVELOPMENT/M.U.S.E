"""Tests for the Learning Dataset ingest bridges."""

from __future__ import annotations

import json

from muse_cli.jarvis_prime.learning_dataset import (
    CandidateStatus,
    DatasetStore,
    QualityGates,
    TraceType,
)
from muse_cli.jarvis_prime.learning_ingest import (
    from_research_artifact,
    from_trajectory_file,
)
from muse_cli.jarvis_prime.research_vault import (
    EvidenceStrength,
    ResearchArtifact,
    SourceType,
)


def test_from_trajectory_file_maps_completed_and_failed(tmp_path):
    traj = tmp_path / "trajectory_samples.jsonl"
    lines = [
        {
            "conversations": [{"from": "human", "value": "do X"}],
            "completed": True,
            "model": "m",
            "timestamp": "t1",
        },
        {
            "conversations": [{"from": "human", "value": "do Y"}],
            "completed": False,
            "model": "m",
            "timestamp": "t2",
        },
    ]
    traj.write_text("\n".join(json.dumps(x) for x in lines) + "\n")

    store = DatasetStore(path=tmp_path / "ds.jsonl")
    created = from_trajectory_file(
        traj,
        store,
        quality=QualityGates(
            tests_passed=True, reviewer_passed=True, rollback_available=True
        ),
    )
    # Completed → coding task; failed → negative failed_attempt.
    types = {c.trace_type for c in created}
    assert TraceType.CODING_TASK in types
    assert TraceType.FAILED_ATTEMPT in types
    failed = [c for c in created if c.trace_type == TraceType.FAILED_ATTEMPT][0]
    assert failed.is_negative


def test_completed_trace_imports_when_quality_asserted(tmp_path):
    """A completed trajectory imports as a coding_task_trace only when the
    operator asserts its verification gates (never auto-minted)."""
    traj = tmp_path / "trajectory_samples.jsonl"
    traj.write_text(
        json.dumps(
            {
                "conversations": [{"from": "human", "value": "do X"}],
                "completed": True,
                "model": "m",
                "timestamp": "t1",
            }
        )
        + "\n"
    )

    # Without asserted gates → skipped (not stored).
    bare = DatasetStore(path=tmp_path / "bare.jsonl")
    assert from_trajectory_file(traj, bare) == []
    assert any("quality gates not met" in d for d in bare.load_diagnostics)

    # With asserted gates → imported as a coding_task_trace.
    store = DatasetStore(path=tmp_path / "ds.jsonl")
    created = from_trajectory_file(
        traj,
        store,
        quality=QualityGates(
            tests_passed=True, reviewer_passed=True, rollback_available=True
        ),
    )
    assert len(created) == 1
    assert created[0].trace_type == TraceType.CODING_TASK


def test_default_path_is_profile_aware(tmp_path, monkeypatch):
    """The default store path honors HERMES_HOME (per AGENTS.md), never the
    raw process-user home."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from muse_cli.jarvis_prime.learning_dataset import default_dataset_path

    assert default_dataset_path() == tmp_path / "jarvis_prime" / "learning_dataset.jsonl"


def test_from_research_artifact_carries_citation(tmp_path):
    art = ResearchArtifact(
        id="abc123",
        title="Spec",
        source_uri="https://spec.example.org",
        source_type=SourceType.OFFICIAL_DOC,
        evidence_strength=EvidenceStrength.PRIMARY,
        excerpt="The spec says foo.",
        summary="foo is required",
    )
    store = DatasetStore(path=tmp_path / "ds.jsonl")
    cand = from_research_artifact(
        art,
        store,
        question="Is foo required?",
        answer="Yes.",
        citations_verified=True,
    )
    assert cand.trace_type == TraceType.RESEARCH_ANSWER
    assert cand.provenance.citations == ("https://spec.example.org",)
    assert cand.status == CandidateStatus.PENDING

    # And it should be exportable as an eval case once approved.
    store.approve(cand.id)
    out = tmp_path / "eval.jsonl"
    assert store.export_eval_cases(out) == 1
    rec = json.loads(out.read_text().splitlines()[0])
    assert rec["citations"] == ["https://spec.example.org"]
