"""Unified navigator + dispatcher (gap analysis G03).

Proves the two gap-analysis findings are closed by the extension in
``hermes_cli.jarvis_prime.aos_council.dispatcher``:

* "navigator/planner is not unified" — :func:`unified_dispatch` composes the
  council :class:`CouncilSession` (who) with a :class:`NavigationResult`
  (where) into one :class:`DispatchPlan` carrying a single
  ``dispatch_decision`` ledger record (not separate navigation + council
  entries).
* "dispatcher/task queue is not generalized" — the :class:`TaskQueue` speaks
  the ``queue.json`` contract (pending / in_flight / completed / failed) from
  ``docs/orchestration/hermes-orchestration-pipeline.md`` and emits tasks for
  council members *and* navigation edit sites, so the dispatcher is no longer
  registry-only.

The tests are hermetic: a synthetic registry + a fake Navigator (no repo
indexing, no model calls, no filesystem writes).
"""

from __future__ import annotations

from hermes_cli.jarvis_prime.aos_council import (
    DispatchPlan,
    Task,
    TaskQueue,
    dispatch,
    unified_dispatch,
)

REG = {
    "policies": {
        "default_slack_council_max": 6,
        "owner_gate_phrase": "Yes, with authorization.",
    },
    "active_council": [
        {"id": "council-director", "role": "Router.", "path": "x.md"},
        {"id": "evidence-architect", "role": "Evidence."},
    ],
    "domain_specialists": [
        {
            "id": "principal-systems-architect",
            "domain": "architecture",
            "when_to_use": "Architecture changes, cross-service design, scaling, data models.",
            "when_not_to_use": "Simple edits, copy-only changes.",
            "required_inputs": ["mission brief"],
            "required_output": "Architecture memo.",
            "verification_method": "Run tests.",
            "owner_gate": "Yes, with authorization.",
        },
        {
            "id": "commercial-strategist",
            "domain": "business",
            "when_to_use": "Pricing, market, positioning, business model.",
            "when_not_to_use": "Pure engineering.",
            "required_inputs": [],
            "required_output": "GTM memo.",
            "verification_method": "Check market evidence.",
            "owner_gate": "",
        },
    ],
}


# --- fakes for the navigation half (no repo indexing) ----------------------


class _FakeEditSite:
    def __init__(self, path: str, rank: int, confidence: float):
        self.path = path
        self.rank = rank
        self.confidence = confidence
        self.rationale = "lexical+path match"
        self.suggested_tests = ["tests/test_a.py"]

    def to_dict(self) -> dict:
        return {"path": self.path, "rank": self.rank}


class _FakeNavigationResult:
    def __init__(self, edit_sites):
        self.edit_sites = edit_sites

    def worker_packet(self):
        return {
            "candidate_files": [s.path for s in self.edit_sites],
            "edit_sites": [s.to_dict() for s in self.edit_sites],
            "verify_with": ["tests/test_a.py"],
            "navigation_method": "lexical+path+symbol (deterministic, no LLM)",
        }

    def to_ledger_record(self, *, job_id=None):
        return {
            "kind": "navigation_decision",
            "job_id": job_id,
            "objective": "x",
            "ranked_files": [{"path": s.path, "rank": s.rank} for s in self.edit_sites],
        }

    def to_dict(self):
        return {"edit_sites": [s.to_dict() for s in self.edit_sites]}


class FakeNavigator:
    """Stand-in for hermes_cli.jarvis_prime.navigation.navigator.Navigator."""

    def navigate(self, request: str, *, limit: int = 5):
        return _FakeNavigationResult(
            [_FakeEditSite("src/api.py", 1, 0.9), _FakeEditSite("src/web.py", 2, 0.6)]
        )


# --- tests -----------------------------------------------------------------


def test_unified_dispatch_council_only_has_no_navigation():
    """A non-code request (no navigator) yields a council-only plan."""
    plan = unified_dispatch("pricing and business model positioning", registry=REG)
    assert isinstance(plan, DispatchPlan)
    assert plan.navigation is None
    # 2 council + 1 matching specialist = 3 tasks
    assert plan.queue.total == 3
    assert all(t.status == "pending" for t in plan.queue.pending)
    assert plan.owner_gated is False


def test_unified_dispatch_composes_navigator_and_dispatcher():
    """The unified plan carries both who (council) and where (navigation)."""
    plan = unified_dispatch(
        "Redesign the cross-service architecture for scaling",
        registry=REG,
        navigator=FakeNavigator(),
    )
    assert plan.navigation is not None
    # 2 council + 1 specialist + 2 edit sites = 5 tasks
    assert plan.queue.total == 5
    kinds = [t.kind for t in plan.queue.pending]
    assert kinds.count("council") == 2
    assert kinds.count("specialist") == 1
    assert kinds.count("edit_site") == 2
    # owner-gate propagates from the council session
    assert plan.owner_gated is True


def test_unified_dispatch_uses_underlying_dispatch_unchanged():
    """unified_dispatch is built on dispatch, not a parallel router."""
    plan = unified_dispatch(
        "Redesign the cross-service architecture for scaling",
        registry=REG,
        navigator=FakeNavigator(),
    )
    direct = dispatch("Redesign the cross-service architecture for scaling", registry=REG)
    assert [m.id for m in plan.session.council] == [m.id for m in direct.council]
    assert [m.id for m in plan.session.specialists] == [m.id for m in direct.specialists]


def test_worker_packet_combines_navigation_and_council():
    plan = unified_dispatch(
        "Redesign the cross-service architecture for scaling",
        registry=REG,
        navigator=FakeNavigator(),
    )
    pkt = plan.worker_packet()
    assert pkt["candidate_files"] == ["src/api.py", "src/web.py"]
    assert pkt["verify_with"] == ["tests/test_a.py"]
    assert len(pkt["council"]) == 3
    assert "queue" in pkt and pkt["queue"]["pending"]


def test_worker_packet_council_only_has_empty_navigation_fields():
    plan = unified_dispatch("pricing and business model positioning", registry=REG)
    pkt = plan.worker_packet()
    assert pkt["candidate_files"] == []
    assert pkt["edit_sites"] == []
    assert pkt["verify_with"] == []


def test_ledger_record_is_single_dispatch_decision():
    """One dispatch_decision record replaces separate navigation + council entries."""
    plan = unified_dispatch(
        "Redesign the cross-service architecture for scaling",
        registry=REG,
        navigator=FakeNavigator(),
    )
    rec = plan.to_ledger_record(job_id="job-42")
    assert rec["kind"] == "dispatch_decision"
    assert rec["job_id"] == "job-42"
    assert rec["owner_gated"] is True
    # navigation is embedded, not a separate top-level record
    assert "navigation" in rec
    assert rec["navigation"]["kind"] == "navigation_decision"
    assert "council" in rec and "queue" in rec


def test_ledger_record_council_only_omits_navigation():
    plan = unified_dispatch("pricing and business model positioning", registry=REG)
    rec = plan.to_ledger_record()
    assert "navigation" not in rec
    assert rec["kind"] == "dispatch_decision"


def test_task_queue_matches_queue_json_contract():
    """to_dict() serializes to the pending/in_flight/completed/failed shape."""
    plan = unified_dispatch("pricing and business model positioning", registry=REG)
    qd = plan.queue.to_dict()
    assert set(qd) == {"pending", "in_flight", "completed", "failed"}
    assert len(qd["pending"]) == 3
    assert qd["in_flight"] == [] and qd["completed"] == [] and qd["failed"] == []


def test_task_queue_claim_complete_fail_lifecycle():
    plan = unified_dispatch("pricing and business model positioning", registry=REG)
    q = plan.queue
    tid = q.pending[0].id
    # claim moves pending -> in_flight
    claimed = q.claim(tid)
    assert claimed is not None and claimed.status == "in_flight"
    assert q.claim(tid) is None  # already claimed
    # complete moves in_flight -> completed
    assert q.complete(tid) is True
    assert q.complete(tid) is False
    # fail path on another task
    tid2 = q.pending[0].id
    assert q.claim(tid2) is not None
    assert q.fail(tid2) is True
    assert q.fail(tid2) is False
    assert q.total == 3
    qd = q.to_dict()
    assert len(qd["completed"]) == 1 and len(qd["failed"]) == 1
    assert len(qd["in_flight"]) == 0


def test_task_queue_from_tasks_seeds_all_pending():
    tasks = [Task(id=f"t{i}", assignee=f"a{i}", kind="council") for i in range(4)]
    q = TaskQueue.from_tasks(tasks)
    assert len(q.pending) == 4
    assert all(t.status == "pending" for t in q.pending)
    assert q.in_flight == [] and q.completed == [] and q.failed == []


def test_render_includes_council_navigation_and_queue():
    plan = unified_dispatch(
        "Redesign the cross-service architecture for scaling",
        registry=REG,
        navigator=FakeNavigator(),
    )
    text = plan.render()
    assert "Unified dispatch plan" in text
    assert "Navigation (where to edit)" in text
    assert "Task queue" in text
    assert "src/api.py" in text


def test_edit_site_tasks_carry_rank_and_tests():
    plan = unified_dispatch(
        "Redesign the cross-service architecture for scaling",
        registry=REG,
        navigator=FakeNavigator(),
    )
    edit_tasks = [t for t in plan.queue.pending if t.kind == "edit_site"]
    assert len(edit_tasks) == 2
    paths = sorted(t.assignee for t in edit_tasks)
    assert paths == ["src/api.py", "src/web.py"]
    assert edit_tasks[0].payload["suggested_tests"] == ["tests/test_a.py"]
    assert "rank" in edit_tasks[0].payload and "confidence" in edit_tasks[0].payload
