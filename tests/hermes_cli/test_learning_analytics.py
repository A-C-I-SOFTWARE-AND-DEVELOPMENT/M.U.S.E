"""Tests for the optional DuckDB/Parquet learning-dataset analytics tier."""

from __future__ import annotations

import pytest

pytest.importorskip("duckdb")  # optional extra; skip cleanly when absent

from hermes_cli.jarvis_prime.learning_analytics import export_parquet, query_dataset
from hermes_cli.jarvis_prime.learning_dataset import (
    CandidateStatus,
    DatasetStore,
    Provenance,
    QualityGates,
    SourceTrust,
    TraceType,
)


def _seed_store(tmp_path):
    store = DatasetStore(path=tmp_path / "ds.jsonl")
    # An approved, fully-gated coding trace.
    coding = store.add_candidate(
        TraceType.CODING_TASK,
        {"conversations": [{"from": "human", "value": "fix bug"}]},
        Provenance(source_kind="trajectory", source_uri="job://1", trust=SourceTrust.OWNER),
        QualityGates(tests_passed=True, reviewer_passed=True, rollback_available=True),
    )
    store.approve(coding.id, note="ok")
    # A pending research trace that should NOT appear in the default export.
    store.add_candidate(
        TraceType.RESEARCH_ANSWER,
        {"question": "q", "answer": "a"},
        Provenance(source_kind="research_vault", citations=("https://example.org",)),
        QualityGates(citations_verified=True, reviewer_passed=True),
    )
    return store


def test_export_parquet_default_is_approved_only(tmp_path):
    store = _seed_store(tmp_path)
    out = tmp_path / "ds.parquet"
    n = export_parquet(store, out)
    assert n == 1  # only the approved coding trace
    assert out.exists()

    rows = query_dataset("SELECT trace_type, status FROM dataset", out)
    assert len(rows) == 1
    assert rows[0]["trace_type"] == "coding_task_trace"
    assert rows[0]["status"] == "approved"


def test_export_parquet_status_none_exports_all(tmp_path):
    store = _seed_store(tmp_path)
    out = tmp_path / "all.parquet"
    n = export_parquet(store, out, status=None)
    assert n == 2

    rows = query_dataset(
        "SELECT trace_type, count(*) AS c FROM dataset GROUP BY 1 ORDER BY 1", out
    )
    counts = {r["trace_type"]: r["c"] for r in rows}
    assert counts.get("coding_task_trace") == 1
    assert counts.get("research_answer_trace") == 1


def test_export_parquet_empty_store(tmp_path):
    store = DatasetStore(path=tmp_path / "empty.jsonl")
    out = tmp_path / "empty.parquet"
    n = export_parquet(store, out)
    assert n == 0
    # Querying the empty (but typed) parquet must not error.
    rows = query_dataset("SELECT count(*) AS c FROM dataset", out)
    assert rows[0]["c"] == 0
