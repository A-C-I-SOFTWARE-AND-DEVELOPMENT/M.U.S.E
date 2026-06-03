"""Tests for the Learning Dataset ingest bridges."""

from __future__ import annotations

import json

from hermes_cli.jarvis_prime.learning_dataset import (
    CandidateStatus,
    DatasetStore,
    QualityGates,
    TraceType,
)
from hermes_cli.jarvis_prime.learning_ingest import (
    from_research_artifact,
    from_trajectory_file,
)
from hermes_cli.jarvis_prime.research_vault import (
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
    assert "https://spec.example.org" in cand.provenance.citations
    assert cand.status == CandidateStatus.PENDING

    # And it should be exportable as an eval case once approved.
    store.approve(cand.id)
    out = tmp_path / "eval.jsonl"
    assert store.export_eval_cases(out) == 1
    rec = json.loads(out.read_text().splitlines()[0])
    assert rec["citations"] == ["https://spec.example.org"]
