"""Unit tests for the canonical cockpit contract adapters.

Pure mapping tests (no server, no network): the adapters must project the
JARVIS-Prime subsystem records into the Android product-spec schema with
honest derivation and zero fabricated fields.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from gateway.cockpit import contract
from hermes_cli.decision_ledger import DecisionLedger
from hermes_cli.jarvis_prime.memory import MemoryRecord
from hermes_cli.job_queue import JobQueueEntry, WorkerQueueEntry


def _ledger(**kw) -> DecisionLedger:
    base = dict(
        decision="Add OAuth callback handler",
        plain_english_summary="Wire the OAuth return path",
        context="User asked to finish OAuth login",
        evidence_reviewed="Looked at src/auth/*.py and the provider docs",
        selected_model_worker="codex_cli",
        why_this_choice="Codex is fastest for bounded edits",
        validation_plan="Run the auth unit tests",
        approval_required="no - trivial bounded change",
        final_decision="proceed - implement the handler",
        confidence="high - well understood",
        open_risks="N/A - additive, behind a flag",
        rollback_plan="N/A - additive change",
        cost_latency_quality_tradeoff="cheap, fast, high quality",
        created_at=1000.0,
        slug="add-oauth",
    )
    base.update(kw)
    return DecisionLedger(**base)  # ty: ignore[invalid-argument-type]


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


# ---------------------------------------------------------------------------
# Orchestrator Job → canonical CockpitJob (the /orchestrate-flow bridge)
# ---------------------------------------------------------------------------


def test_orchestrator_job_projects_canonical_shape() -> None:
    from hermes_cli.orchestrator import Job

    # created_at/updated_at are MICROSECOND epochs (orchestrator _now()).
    job = Job(
        id="orc-abc123",
        prompt="Add a worker-runs projection\nignored second line",
        status="completed",
        created_at=1_700_000_000_000_000,
        updated_at=1_700_000_001_000_000,
    )
    out = contract.orchestrator_job(job)
    assert out["id"] == "orc-abc123"
    assert out["title"] == "Add a worker-runs projection"  # first line only
    assert out["status"] == "COMPLETED"
    assert out["worker_id"] == ""
    # microsecond epoch → seconds → honest ISO (2023, not a year ~55000)
    assert out["created_at"].startswith("2023-")
    # fields the orchestrator Job genuinely doesn't carry are null, not faked
    assert out["branch"] is None
    assert out["remote"] is None
    assert out["validation_summary"] is None
    # key set is identical to the JobQueue projection (one canonical shape)
    assert set(out.keys()) == set(
        contract.cockpit_job(JobQueueEntry(job_id="j", created_at=5.0)).keys()
    )


def test_orchestrator_job_status_mapping_and_published() -> None:
    from hermes_cli.orchestrator import Job

    assert contract.orchestrator_job(Job(id="o", prompt="p", status="blocked"))[
        "status"
    ] == "BLOCKED"
    assert contract.orchestrator_job(Job(id="o", prompt="p", status="queued"))[
        "status"
    ] == "QUEUED"
    # an unknown orchestrator state falls back honestly to QUEUED (never crashes)
    assert contract.orchestrator_job(Job(id="o", prompt="p", status="weird"))[
        "status"
    ] == "QUEUED"
    # published_at wins and drives publish_state
    published = Job(id="o", prompt="p", status="completed", published_at=1_700_000_000_000_000)
    out = contract.orchestrator_job(published)
    assert out["status"] == "PUBLISHED"
    assert out["publish_state"] == "SUCCEEDED"


# ---------------------------------------------------------------------------
# Job detail — Job + ledger → canonical JobDetail (timeline / workers / files)
# ---------------------------------------------------------------------------


def test_orchestrator_job_detail_folds_ledger_into_workers_and_files() -> None:
    from hermes_cli.orchestrator import Job

    job = Job(
        id="orc-detail",
        prompt="Refactor the parser\nsecond line ignored",
        status="completed",
        created_at=1_700_000_000_000_000,
        approvals={"execute": 1_700_000_000_000_000},
    )
    ledger = [
        {"ts": "2023-11-14T22:13:20+00:00", "kind": "submit", "prompt": "Refactor"},
        {"ts": "2023-11-14T22:13:21+00:00", "kind": "worker_dispatch",
         "worker_id": "codex-execute", "available": True, "reason": "ready"},
        {"ts": "2023-11-14T22:13:25+00:00", "kind": "worker_result",
         "worker_id": "codex-execute", "ok": True, "summary": "done"},
        {"ts": "2023-11-14T22:13:26+00:00", "kind": "worker_score",
         "worker_id": "codex-execute", "value": 0.9, "rationale": "clean",
         "files": ["src/parser.py"]},
    ]
    out = contract.orchestrator_job_detail(job, ledger)
    assert out["id"] == "orc-detail"
    assert out["objective"] == "Refactor the parser"
    assert out["status"] == "COMPLETED"
    # workers folded from the ledger trail; latest status wins (SUCCESS)
    assert len(out["workers"]) == 1
    assert out["workers"][0]["id"] == "codex-execute"
    assert out["workers"][0]["status"] == "SUCCESS"
    # files come from worker_score; honest empty commands (not tracked)
    assert out["files_touched"] == ["src/parser.py"]
    assert out["commands_run"] == []
    assert out["test_results"] is None
    # approval recorded on the job surfaces in the detail
    assert out["approvals"][0]["state"] == "APPROVED"
    # timeline preserves order and tags actors
    assert [e["kind"] for e in out["timeline"]] == [
        "submit", "worker_dispatch", "worker_result", "worker_score",
    ]
    assert out["timeline"][0]["actor"] == "owner"
    assert out["timeline"][1]["actor"] == "worker"


def test_queue_job_detail_projects_workers_and_timeline() -> None:
    from hermes_cli.job_queue import JobQueueEntry, WorkerQueueEntry, WorkerStatus

    entry = JobQueueEntry(
        job_id="job_q1",
        prompt="Ship the thing",
        repo_root="/tmp/proj",
        created_at=5.0,
        updated_at=6.0,
        note="waiting on worker",
        workers=[
            WorkerQueueEntry(worker_id="codex_cli", status=WorkerStatus.FAILED,
                             attempts=2, last_error="boom"),
        ],
    )
    out = contract.queue_job_detail(entry)
    assert out["id"] == "job_q1"
    assert out["objective"] == "Ship the thing"
    assert out["workers"][0]["status"] == "FAILED"
    assert out["workers"][0]["attempts"] == 2
    assert out["workers"][0]["error"] == "boom"
    # submit anchors the timeline; a worker row follows
    assert out["timeline"][0]["kind"] == "submit"
    assert any("codex_cli" in e["summary"] for e in out["timeline"])
    # current_step surfaces the human-readable note
    assert out["current_step"] == "waiting on worker"
    # canonical shape parity with the orchestrator detail projection
    assert set(out.keys()) == set(
        contract.orchestrator_job_detail(
            __import__("hermes_cli.orchestrator", fromlist=["Job"]).Job(
                id="o", prompt="p"
            ),
            [],
        ).keys()
    )


# ---------------------------------------------------------------------------
# Audit — DecisionLedger → canonical AuditRecord / ProofRecord
# ---------------------------------------------------------------------------


def test_audit_record_maps_ledger_honestly() -> None:
    rec = contract.audit_record(_ledger())
    assert rec["id"] == "add-oauth"
    assert rec["user_request"].startswith("User asked")
    assert rec["action"].startswith("proceed")
    assert rec["risk_tier"] == "LOW"  # open_risks "N/A — ..." reads as none
    assert rec["route"]["destination"] == "CODEX"
    assert rec["route"]["model"] == "codex_cli"
    assert rec["route"]["duration_ms"] == 0  # honest: not tracked
    assert rec["approval_state"] == "UNNECESSARY"  # "no"
    assert rec["result"] == "SUCCESS"  # "proceed"
    assert rec["confidence"] == 0.95  # "high"
    assert rec["proof_id"] == "add-oauth"
    assert set(rec.keys()) == {
        "id", "timestamp", "user_request", "action", "risk_tier",
        "route", "approval_state", "result", "confidence", "proof_id",
    }
    assert set(rec["route"].keys()) == {"destination", "model", "reason", "duration_ms"}


def test_audit_record_derivation_for_risk_approval_result() -> None:
    rec = contract.audit_record(_ledger(
        open_risks="May hit the provider rate limit under load",
        approval_required="yes - owner must confirm the scope",
        final_decision="blocked - waiting on a secret",
        confidence="medium - some unknowns",
        selected_model_worker="claude_code",
    ))
    assert rec["risk_tier"] == "MODERATE"  # real flagged risk
    assert rec["approval_state"] == "APPROVED"  # "yes"
    assert rec["result"] == "BLOCKED"
    assert rec["confidence"] == 0.7  # "medium"
    assert rec["route"]["destination"] == "CLAUDE"


def test_audit_proof_maps_nested_bundle_with_honest_absences() -> None:
    proof = contract.audit_proof(_ledger())
    assert proof["audit_id"] == "add-oauth"
    assert proof["rationale"].startswith("Codex is fastest")
    assert len(proof["evidence"]) == 1
    assert proof["evidence"][0]["kind"] == "DOC_LINK"
    assert proof["verification"]["status"] == "PASSED"  # validation_plan present
    assert len(proof["approvals"]) == 1
    assert proof["approvals"][0]["state"] == "UNNECESSARY"
    assert proof["rollback"] is None  # "N/A — additive change" → none
    assert len(proof["worker_runs"]) == 1
    assert proof["worker_runs"][0]["worker"] == "codex_cli"
    assert proof["files_changed"] == []  # never fabricated
    assert proof["tests_run"] == []
    assert set(proof.keys()) == {
        "id", "audit_id", "rationale", "evidence", "tests_run", "files_changed",
        "verification", "approvals", "rollback", "impact_report", "worker_runs",
    }


def test_audit_proof_surfaces_rollback_when_present() -> None:
    proof = contract.audit_proof(_ledger(
        rollback_plan="Revert the commit\nRedeploy the previous build",
    ))
    assert proof["rollback"] is not None
    assert proof["rollback"]["steps"] == ["Revert the commit", "Redeploy the previous build"]
    assert proof["rollback"]["automatic"] is False


# ---------------------------------------------------------------------------
# Approvals — proposal -> canonical ApprovalCard (+ native proposal view)
# ---------------------------------------------------------------------------


def _proposal(**kw) -> dict:
    base = {
        "kind": "skill_update",
        "target_path": "skills/foo/SKILL.md",
        "rationale": "improve the foo skill",
        "risk_class": "RC2",
        "requires_owner_approval": True,
        "status": "proposed",
        "created_at": "2026-05-30T00:00:00+00:00",
    }
    base.update(kw)
    return base


def test_approval_card_tier_mapping() -> None:
    assert contract.approval_card_tier("RC0") == "LOW"
    assert contract.approval_card_tier("RC2") == "RISKY"
    assert contract.approval_card_tier("RC3") == "SERIOUS"
    assert contract.approval_card_tier("RC4") == "CRITICAL"
    assert contract.approval_card_tier("???") == "RISKY"  # floor, never SAFE


def test_approval_card_status_mapping() -> None:
    assert contract.approval_card_status("proposed") == "PENDING"
    assert contract.approval_card_status("approved") == "APPROVED"
    assert contract.approval_card_status("rejected") == "REJECTED"
    assert contract.approval_card_status("weird") == "PENDING"


def test_approval_card_projection() -> None:
    card = contract.approval_card(_proposal(), approval_id="abc123")
    assert card["id"] == "abc123"
    assert card["tier"] == "RISKY"
    assert card["status"] == "PENDING"
    assert card["requester"] == "jarvis"
    assert card["summary"] == "improve the foo skill"
    assert card["title"] == "Self-update: skill_update (SKILL.md)"
    assert "skills/foo/SKILL.md" in card["proposed_action"]
    assert card["expires_at"] is None
    assert set(card.keys()) == {
        "id", "title", "summary", "requester", "tier", "status",
        "created_at", "expires_at", "proposed_action", "edited_note",
    }


def test_proposal_view_keeps_native_shape() -> None:
    view = contract.proposal_view(_proposal(), proposal_id="abc123")
    assert view["risk_class"] == "RC2"
    assert view["risk_level"] == "medium"
    assert view["target"] == "skills/foo/SKILL.md"
    assert view["requires_owner_approval"] is True


# ---------------------------------------------------------------------------
# Skills — installed-skill projection
# ---------------------------------------------------------------------------


def test_skill_entry_projection() -> None:
    e = contract.skill_entry("/jarvis-prime", {"name": "jarvis-prime", "description": "Route owner work."})
    assert e == {
        "id": "jarvis-prime",
        "command": "/jarvis-prime",
        "name": "jarvis-prime",
        "description": "Route owner work.",
    }


def test_skill_entry_tolerates_missing_fields() -> None:
    e = contract.skill_entry("/foo", {})
    assert e["id"] == "foo"
    assert e["command"] == "/foo"
    assert e["name"] == "" and e["description"] == ""


# ---------------------------------------------------------------------------
# Navigation — orchestrator navigation_decision -> cockpit view
# ---------------------------------------------------------------------------


def test_navigation_view_projection() -> None:
    entry = {
        "kind": "navigation_decision",
        "job_id": "j1",
        "created_at": "2026-05-30T12:00:00Z",
        "objective": "fix upload",
        "method": "deterministic-multi-signal",
        "ranked_files": [
            {"path": "svc/uploader.py", "rank": 1, "confidence": 0.91,
             "rationale": "matches symbol", "signals": {"lexical": 0.8}},
        ],
        "verify_with": ["pytest tests/test_uploader.py"],
    }
    v = contract.navigation_view(entry)
    assert v["job_id"] == "j1"
    assert v["objective"] == "fix upload"
    assert v["method"] == "deterministic-multi-signal"
    assert v["candidate_files"][0]["path"] == "svc/uploader.py"
    assert v["candidate_files"][0]["confidence"] == 0.91
    assert v["candidate_files"][0]["rank"] == 1
    assert v["verify_with"] == ["pytest tests/test_uploader.py"]
    assert set(v.keys()) == {
        "job_id", "objective", "created_at", "method", "candidate_files", "verify_with",
    }


def test_navigation_view_job_id_override() -> None:
    v = contract.navigation_view({"objective": "x"}, job_id="job_42")
    assert v["job_id"] == "job_42"
    assert v["candidate_files"] == []


# ---------------------------------------------------------------------------
# Coding packet + evidence adapters
# ---------------------------------------------------------------------------


def test_coding_packet_projects_work_packet() -> None:
    from hermes_cli.jarvis_prime import natural_language_coder as nlc

    packet = nlc.build_work_packet("add a unit test for the parser")
    out = contract.coding_packet(packet)
    assert out["mission"]
    assert out["branch"]
    assert out["risk_class"].startswith("RC")
    assert isinstance(out["allowed_files"], list)
    assert isinstance(out["verification_plan"], list)


def test_evidence_artifact_projects_research_artifact() -> None:
    from hermes_cli.jarvis_prime import research_vault as rv

    art = rv.ResearchArtifact(
        id="abc123",
        title="PEP 659",
        source_uri="https://peps.python.org/pep-0659/",
        source_type=rv.SourceType.OFFICIAL_DOC,
        evidence_strength=rv.EvidenceStrength.PRIMARY,
        excerpt="specializing adaptive interpreter",
    )
    out = contract.evidence_artifact(art)
    assert out["id"] == "abc123"
    assert out["source_type"] == "official_doc"
    assert out["evidence_strength"] == "primary"


class _FakeReport:
    """Minimal stand-in for epistemics.AuditReport (outcome + findings)."""

    class _Outcome:
        def __init__(self, value: str) -> None:
            self.value = value

    def __init__(self, outcome: str, findings=()) -> None:
        self.outcome = self._Outcome(outcome)
        self.findings = list(findings)


def _artifact(strength: str = "primary", freshness_due=None):
    from hermes_cli.jarvis_prime import research_vault as rv

    return rv.ResearchArtifact(
        id="x",
        title="t",
        source_uri="https://example.com",
        evidence_strength=rv.EvidenceStrength(strength),
        freshness_due=freshness_due,
    )


def test_evidence_verdict_insufficient_when_no_matches() -> None:
    v = contract.evidence_verdict("claim", [], _FakeReport("needs_research"))
    assert v["verdict"] == "insufficient_evidence"
    assert v["supporting_sources"] == []
    assert v["contradicting_sources"] == []
    assert v["confidence"] <= 0.4


def test_evidence_verdict_supported_on_clean_audit_with_match() -> None:
    v = contract.evidence_verdict("claim", [_artifact("primary")], _FakeReport("pass"))
    assert v["verdict"] == "supported"
    assert v["confidence"] >= 0.9
    assert v["freshness_status"] == "unknown"  # no freshness date set


def test_evidence_verdict_partial_when_needs_citations() -> None:
    v = contract.evidence_verdict(
        "claim", [_artifact("moderate")], _FakeReport("needs_citations")
    )
    assert v["verdict"] == "partially_supported"


def test_evidence_verdict_stale_when_freshness_past_due() -> None:
    from datetime import timedelta

    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    v = contract.evidence_verdict("claim", [_artifact("primary", past)], _FakeReport("pass"))
    assert v["verdict"] == "stale"
    assert v["freshness_status"] == "stale"
