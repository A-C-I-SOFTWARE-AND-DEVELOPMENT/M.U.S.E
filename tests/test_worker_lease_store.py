"""Tests for the durable worker-lease store + host registry (Sprint 13).

The store tests are pure (no subprocesses, no network): they drive the
:class:`WorkerLeaseStore` against an isolated directory in ``tmp_path``.
The final test exercises :class:`ParallelRunner` to confirm lease
*recording* happens without altering run outcomes.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from hermes_cli import orchestrator_parallel as op
from hermes_cli.worker_lease import (
    LeaseStatus,
    WorkerLease,
    acquire,
)
from hermes_cli.worker_lease_store import (
    DEFAULT_HOST_ID,
    HostRecord,
    WorkerLeaseStore,
    default_store_dir,
    lease_from_dict,
    lease_to_dict,
)


# ─── helpers ──────────────────────────────────────────────────────────


def _pending(lease_id: str = "lease_1", job_id: str = "job_1") -> WorkerLease:
    return WorkerLease(
        lease_id=lease_id,
        job_id=job_id,
        worker_id="claude-code",
        host_id=DEFAULT_HOST_ID,
    )


def _running(
    lease_id: str = "lease_1",
    job_id: str = "job_1",
    *,
    now: float = 100.0,
    ttl: float = 30.0,
) -> WorkerLease:
    return acquire(_pending(lease_id, job_id), now=now, ttl=ttl)


# ─── serialization round-trip ────────────────────────────────────────


def test_lease_dict_round_trip_preserves_fields():
    lease = _running()
    again = lease_from_dict(lease_to_dict(lease))
    assert again == lease
    assert again.status is LeaseStatus.RUNNING


def test_lease_from_dict_coerces_numeric_strings():
    raw = lease_to_dict(_running())
    raw["expires_at"] = "130.0"  # simulate a value read back as a string
    lease = lease_from_dict(raw)
    assert lease.expires_at == 130.0


# ─── store API + persistence ─────────────────────────────────────────


def test_upsert_get_round_trip(tmp_path: Path):
    store = WorkerLeaseStore.load(tmp_path)
    lease = _running()
    store.upsert(lease)
    assert store.get("lease_1") == lease
    assert store.get("missing") is None


def test_upsert_replaces_existing_lease(tmp_path: Path):
    store = WorkerLeaseStore.load(tmp_path)
    store.upsert(_running())
    # Same lease_id, advanced state.
    from hermes_cli.worker_lease import complete

    done = complete(_running(), now=110.0)
    store.upsert(done)
    got = store.get("lease_1")
    assert got is not None
    assert got.status is LeaseStatus.COMPLETED
    # No duplicate rows: exactly one record persisted for the id.
    assert len(store.all_leases()) == 1


def test_for_job_filters_by_job(tmp_path: Path):
    store = WorkerLeaseStore.load(tmp_path)
    store.upsert(_running("a", "job_a"))
    store.upsert(_running("b", "job_a"))
    store.upsert(_running("c", "job_b"))
    a_ids = {leas.lease_id for leas in store.for_job("job_a")}
    assert a_ids == {"a", "b"}
    assert [leas.lease_id for leas in store.for_job("job_b")] == ["c"]
    assert store.for_job("nope") == []


def test_active_returns_only_running(tmp_path: Path):
    from hermes_cli.worker_lease import complete

    store = WorkerLeaseStore.load(tmp_path)
    store.upsert(_running("a"))
    store.upsert(complete(_running("b"), now=110.0))
    active_ids = {leas.lease_id for leas in store.active()}
    assert active_ids == {"a"}


def test_persistence_across_reload(tmp_path: Path):
    store = WorkerLeaseStore.load(tmp_path)
    store.upsert(_running("a", "job_a"))
    store.upsert(_running("b", "job_b"))

    # A brand-new instance over the same directory sees the same data.
    reloaded = WorkerLeaseStore.load(tmp_path)
    assert reloaded.get("a") == store.get("a")
    assert reloaded.get("b") == store.get("b")
    assert {leas.lease_id for leas in reloaded.all_leases()} == {"a", "b"}
    assert reloaded.load_diagnostics == []


def test_expire_stale_flips_running_past_deadline(tmp_path: Path):
    store = WorkerLeaseStore.load(tmp_path)
    store.upsert(_running("a", now=100.0, ttl=30.0))  # expires 130
    store.upsert(_running("b", now=100.0, ttl=300.0))  # expires 400

    flipped = store.expire_stale(now=200.0)
    assert {leas.lease_id for leas in flipped} == {"a"}
    assert store.get("a").status is LeaseStatus.EXPIRED  # type: ignore[union-attr]
    assert store.get("b").status is LeaseStatus.RUNNING  # type: ignore[union-attr]

    # Idempotent: nothing left stale to flip.
    assert store.expire_stale(now=200.0) == []


def test_expire_stale_persists(tmp_path: Path):
    store = WorkerLeaseStore.load(tmp_path)
    store.upsert(_running("a", now=100.0, ttl=30.0))
    store.expire_stale(now=999.0)

    reloaded = WorkerLeaseStore.load(tmp_path)
    assert reloaded.get("a").status is LeaseStatus.EXPIRED  # type: ignore[union-attr]


def test_tolerant_load_skips_corrupt_lines(tmp_path: Path):
    # Seed a store with one good row, then append garbage by hand.
    store = WorkerLeaseStore.load(tmp_path)
    store.upsert(_running("good"))
    leases_file = tmp_path / "leases.jsonl"
    with open(leases_file, "a", encoding="utf-8") as fh:
        fh.write("this is not json\n")
        fh.write('{"missing":"required-keys"}\n')

    reloaded = WorkerLeaseStore.load(tmp_path)
    assert reloaded.get("good") is not None
    assert len(reloaded.all_leases()) == 1
    assert len(reloaded.load_diagnostics) == 2


# ─── host registry ────────────────────────────────────────────────────


def test_default_local_host_present(tmp_path: Path):
    store = WorkerLeaseStore.load(tmp_path)
    host_ids = {h.host_id for h in store.hosts()}
    assert DEFAULT_HOST_ID in host_ids
    local = store.get_host(DEFAULT_HOST_ID)
    assert local == HostRecord(host_id=DEFAULT_HOST_ID, kind="local")


def test_register_host_persists(tmp_path: Path):
    store = WorkerLeaseStore.load(tmp_path)
    store.register_host("builder-box", kind="remote")
    reloaded = WorkerLeaseStore.load(tmp_path)
    box = reloaded.get_host("builder-box")
    assert box == HostRecord(host_id="builder-box", kind="remote")
    # Default host still present after reload.
    assert reloaded.get_host(DEFAULT_HOST_ID) is not None


def test_register_host_rejects_empty(tmp_path: Path):
    store = WorkerLeaseStore.load(tmp_path)
    with pytest.raises(ValueError):
        store.register_host("   ")


def test_default_store_dir_honors_hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    expected = tmp_path / "orchestration"
    assert default_store_dir() == expected


# ─── parallel-runner integration: recording only ─────────────────────


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
        ["git", "config", "commit.gpgsign", "false"],
    ):
        subprocess.run(cmd, cwd=str(path), check=True, capture_output=True, text=True)
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(path), check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"], cwd=str(path), check=True
    )
    return path


def _py(*lines: str) -> list[str]:
    return [sys.executable, "-c", "\n".join(lines)]


def test_parallel_run_records_completed_lease(repo: Path, tmp_path: Path):
    store = WorkerLeaseStore.load(tmp_path / "store")
    plan = op.ExecutionPlan(
        job_id="job-lease",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_py("print('ok')"),
                timeout_seconds=10,
            )
        ],
    )
    runner = op.ParallelRunner(
        repo, plan, poll_interval=0.05, lease_store=store
    )
    statuses = runner.run()

    # 1) Run outcome is unchanged: the worker completed normally.
    assert statuses["w1"].state is op.WorkerState.COMPLETED
    assert statuses["w1"].return_code == 0

    # 2) A completed lease was recorded and persisted, on the local host.
    leases = store.for_job("job-lease")
    assert len(leases) == 1
    lease = leases[0]
    assert lease.status is LeaseStatus.COMPLETED
    assert lease.host_id == DEFAULT_HOST_ID
    assert lease.worker_id == "w1"

    # 3) Durable: a fresh store over the same dir sees the completed lease.
    reloaded = WorkerLeaseStore.load(tmp_path / "store")
    assert reloaded.get(lease.lease_id).status is LeaseStatus.COMPLETED  # type: ignore[union-attr]


def test_parallel_prompt_only_records_completed_lease(repo: Path, tmp_path: Path):
    store = WorkerLeaseStore.load(tmp_path / "store")
    plan = op.ExecutionPlan(
        job_id="job-prompt",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="researcher",
                mode=op.ExecutionMode.PROMPT_ONLY,
                prompt="Investigate X.",
            )
        ],
    )
    statuses = op.ParallelRunner(repo, plan, lease_store=store).run()
    assert statuses["w1"].state is op.WorkerState.COMPLETED

    leases = store.for_job("job-prompt")
    assert len(leases) == 1
    assert leases[0].status is LeaseStatus.COMPLETED


def test_parallel_failure_records_terminal_lease(repo: Path, tmp_path: Path):
    store = WorkerLeaseStore.load(tmp_path / "store")
    plan = op.ExecutionPlan(
        job_id="job-fail",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_py("import sys", "sys.exit(7)"),
                timeout_seconds=10,
            )
        ],
    )
    statuses = op.ParallelRunner(repo, plan, poll_interval=0.05, lease_store=store).run()

    # Run outcome unchanged.
    assert statuses["w1"].state is op.WorkerState.FAILED
    assert statuses["w1"].return_code == 7

    # Lease recorded and terminal (not left RUNNING).
    leases = store.for_job("job-fail")
    assert len(leases) == 1
    assert leases[0].is_terminal
    assert leases[0].status in (LeaseStatus.CANCELLED, LeaseStatus.EXPIRED)


def test_lease_recording_disabled_does_not_persist(repo: Path, tmp_path: Path):
    store = WorkerLeaseStore.load(tmp_path / "store")
    plan = op.ExecutionPlan(
        job_id="job-off",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_py("print('ok')"),
                timeout_seconds=10,
            )
        ],
    )
    statuses = op.ParallelRunner(
        repo, plan, poll_interval=0.05, lease_store=store, record_leases=False
    ).run()
    # Still completes; nothing recorded.
    assert statuses["w1"].state is op.WorkerState.COMPLETED
    assert store.for_job("job-off") == []


def test_broken_store_does_not_break_run(repo: Path):
    """A store whose upsert always raises must not break the run."""

    class _BrokenStore:
        def upsert(self, lease):  # noqa: ANN001 - test double
            raise RuntimeError("disk on fire")

    plan = op.ExecutionPlan(
        job_id="job-broken",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_py("print('ok')"),
                timeout_seconds=10,
            )
        ],
    )
    runner = op.ParallelRunner(
        repo, plan, poll_interval=0.05, lease_store=_BrokenStore()  # type: ignore[arg-type]
    )
    statuses = runner.run()
    # Run still succeeds despite the store raising on every upsert.
    assert statuses["w1"].state is op.WorkerState.COMPLETED
    assert statuses["w1"].return_code == 0
