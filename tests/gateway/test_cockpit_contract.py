"""Unit tests for the canonical cockpit contract adapters.

Pure mapping tests (no server, no network): the adapters must project the
JARVIS-Prime subsystem records into the Android product-spec schema with
honest derivation and zero fabricated fields.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from gateway.cockpit import contract
from hermes_cli.jarvis_prime.memory import MemoryRecord
from hermes_cli.job_queue import JobQueueEntry, WorkerQueueEntry


def test_confidence_to_enum_buckets() -> None:
    assert contract.confidence_to_enum(1.0) == "CONFIRMED"
    assert contract.confidence_to_enum(0.85) == "HIGH"
    assert contract.confidence_to_enum(0.6) == "MEDIUM"
    assert contract.confidence_to_enum(0.1) == "LOW"


def test_confidence_to_float_accepts_enum_or_number() -> None:
    assert contract.confidence_to_float("HIGH") == 0.85
    assert contract.confidence_to_float(0.42) == 0.42
    assert contract.confidence_to_float("nonsense") == 1.0
    # bool must not be read as a confidence number
    assert contract.confidence_to_float(True) == 1.0


def test_durability_round_trips_through_store_values() -> None:
    assert contract.durability_from_store("working") == "EPHEMERAL"
    assert contract.durability_from_store("session") == "SESSION"
    assert contract.durability_from_store("durable") == "PERMANENT"
    # UI enums map to store buckets...
    assert contract.durability_to_store("PERMANENT") == "durable"
    assert contract.durability_to_store("EPHEMERAL") == "working"
    assert contract.durability_to_store("SHORT_TERM") == "session"
    # ...and raw store values are tolerated too (no information loss).
    assert contract.durability_to_store("durable") == "durable"
    assert contract.durability_to_store("working") == "working"
    assert contract.durability_to_store(None) == "session"


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, "UNCATEGORIZED"),
        ("", "UNCATEGORIZED"),
        ("owner preference", "OWNER_PREFERENCE"),
        ("PROJECT_MEMORY", "PROJECT_MEMORY"),
        ("totally-made-up", "UNCATEGORIZED"),
    ],
)
def test_normalize_category(raw, expected) -> None:
    assert contract.normalize_category(raw) == expected


def test_memory_item_projects_full_canonical_shape() -> None:
    captured = datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc)
    recalled = datetime(2026, 5, 30, 13, 0, tzinfo=timezone.utc)
    record = MemoryRecord(
        key="deploy_window",
        value="after 6pm ET",
        durability="durable",
        captured_at=captured,
        last_recalled_at=recalled,
        tags=("ops",),
        source="agent",
        confidence=0.9,
        citations=("seen in chat",),
        category="OWNER_PREFERENCE",
    )
    item = contract.memory_item(record)

    assert item["id"] == "deploy_window"  # id == key keeps DELETE addressable
    assert item["title"] == "deploy_window"
    assert item["content"] == "after 6pm ET"
    assert item["category"] == "OWNER_PREFERENCE"
    assert item["durability"] == "PERMANENT"
    assert item["confidence"] == "HIGH"
    assert item["tags"] == ["ops"]
    assert item["created_at"] == captured.isoformat()
    assert item["updated_at"] == captured.isoformat()  # not invented as "now"
    assert item["last_accessed_at"] == recalled.isoformat()
    assert item["provenance"] == {
        "source": "agent",
        "session_id": None,  # genuinely absent — honest null, not faked
        "recorded_at": captured.isoformat(),
        "note": "seen in chat",
    }
    assert item["redacted"] is False
    assert item["hidden"] is False


def test_memory_item_uncategorized_when_no_signal() -> None:
    record = MemoryRecord(key="k", value="v", durability="session")
    item = contract.memory_item(record)
    assert item["category"] == "UNCATEGORIZED"  # never guessed
    assert item["provenance"]["note"] is None


def test_memory_item_keys_match_android_memoryitem() -> None:
    """The emitted object must carry exactly the product-spec fields."""
    record = MemoryRecord(key="k", value="v", durability="session")
    item = contract.memory_item(record)
    assert set(item.keys()) == {
        "id",
        "category",
        "title",
        "content",
        "durability",
        "confidence",
        "provenance",
        "created_at",
        "updated_at",
        "last_accessed_at",
        "tags",
        "redacted",
        "hidden",
    }
    assert set(item["provenance"].keys()) == {
        "source",
        "session_id",
        "recorded_at",
        "note",
    }


# ---------------------------------------------------------------------------
# Jobs — JobQueueEntry → canonical CockpitJob
# ---------------------------------------------------------------------------


def test_job_status_maps_queue_states() -> None:
    assert contract.job_status("queued") == "QUEUED"
    assert contract.job_status("running") == "RUNNING"
    assert contract.job_status("paused") == "PAUSED"
    assert contract.job_status("blocked") == "BLOCKED"
    assert contract.job_status("disconnected") == "DISCONNECTED"
    assert contract.job_status("completed") == "COMPLETED"
    assert contract.job_status("failed") == "FAILED"
    assert contract.job_status("cancelled") == "CANCELLED"
    assert contract.job_status("nonsense") == "QUEUED"  # honest fallback


def test_job_status_workflow_override() -> None:
    # A pipeline-set workflow status wins when canonical...
    assert contract.job_status("running", "waiting_for_approval") == "WAITING_FOR_APPROVAL"
    assert contract.job_status("completed", "published") == "PUBLISHED"
    # ...but an unknown workflow value is ignored (falls back to the state).
    assert contract.job_status("running", "bogus") == "RUNNING"


def test_normalize_publish_state() -> None:
    assert contract.normalize_publish_state("in_progress") == "IN_PROGRESS"
    assert contract.normalize_publish_state("SUCCEEDED") == "SUCCEEDED"
    assert contract.normalize_publish_state(None) is None
    assert contract.normalize_publish_state("made-up") is None


def test_cockpit_job_full_shape() -> None:
    entry = JobQueueEntry(
        job_id="job_1",
        prompt="First line\nsecond line",
        state="running",
        created_at=1000.0,
        updated_at=2000.0,
        repo_root="/w",
        workers=[WorkerQueueEntry(worker_id="codex_cli")],
        metadata={
            "title": "Add OAuth",
            "branch": "feature/oauth",
            "base_branch": "main",
            "remote": "origin",
            "validation": {"pass": 3, "fail": 1, "pending": 0},
            "publish_state": "in_progress",
        },
    )
    job = contract.cockpit_job(entry)
    assert job["id"] == "job_1"
    assert job["title"] == "Add OAuth"
    assert job["worker_id"] == "codex_cli"
    assert job["status"] == "RUNNING"
    assert job["workspace_path"] == "/w"
    assert job["branch"] == "feature/oauth"
    assert job["base_branch"] == "main"
    assert job["validation_summary"] == {"pass": 3, "fail": 1, "pending": 0}
    assert job["publish_state"] == "IN_PROGRESS"
    assert job["created_at"].startswith("1970-")  # epoch 1000s → honest ISO


def test_cockpit_job_derives_title_and_honest_nulls() -> None:
    entry = JobQueueEntry(
        job_id="job_2", prompt="Do the thing", state="queued",
        created_at=10.0, updated_at=10.0,
    )
    job = contract.cockpit_job(entry)
    assert job["title"] == "Do the thing"  # derived from the prompt's first line
    assert job["worker_id"] == ""
    assert job["branch"] is None
    assert job["base_branch"] is None
    assert job["remote"] is None
    assert job["validation_summary"] is None  # never fabricated
    assert job["publish_state"] is None
    assert job["workspace_path"] is None


def test_cockpit_job_key_set_matches_contract() -> None:
    entry = JobQueueEntry(job_id="j", created_at=5.0)
    assert set(contract.cockpit_job(entry).keys()) == {
        "id",
        "title",
        "worker_id",
        "status",
        "created_at",
        "updated_at",
        "workspace_path",
        "branch",
        "base_branch",
        "remote",
        "validation_summary",
        "publish_state",
    }
