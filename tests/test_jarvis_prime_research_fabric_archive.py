"""Tests for the persistent diversity archive (Plane 3)."""

from __future__ import annotations

import random

from hermes_cli.jarvis_prime.research_fabric.archive.store import ArchiveStore, new_member
from hermes_cli.jarvis_prime.research_fabric.selfplay.evolve import evolve
from hermes_cli.jarvis_prime.research_fabric.selfplay.tasks import (
    DEMO_BASELINE_CODE,
    DEMO_EVOLVE_TASK,
    demo_variant_proposer,
)


def _member(parent_id=None, composite=1.0, note=""):
    return new_member(
        parent_id=parent_id,
        config={"x": 1},
        composite=composite,
        domain_scores={"correctness": composite},
        note=note,
    )


def test_archive_persists_and_reloads(tmp_path) -> None:
    path = tmp_path / "archive.jsonl"
    store = ArchiveStore(path=path)
    m = store.add(_member(note="first"))
    store.add(_member(parent_id=m.member_id, note="second"))
    reloaded = ArchiveStore(path=path)
    assert len(reloaded.members()) == 2
    notes = {x.note for x in reloaded.members()}
    assert notes == {"first", "second"}


def test_sample_parent_empty_is_none(tmp_path) -> None:
    store = ArchiveStore(path=tmp_path / "a.jsonl")
    assert store.sample_parent(rng=random.Random(0)) is None


def test_sample_parent_is_deterministic_with_seed(tmp_path) -> None:
    store = ArchiveStore(path=tmp_path / "a.jsonl")
    root = store.add(_member(note="root"))
    store.add(_member(parent_id=root.member_id, note="child"))
    a = store.sample_parent(rng=random.Random(7))
    b = store.sample_parent(rng=random.Random(7))
    assert a is not None and b is not None
    assert a.member_id == b.member_id


def test_evolve_records_lineage(tmp_path) -> None:
    store = ArchiveStore(path=tmp_path / "a.jsonl")
    result = evolve(
        DEMO_EVOLVE_TASK, DEMO_BASELINE_CODE, demo_variant_proposer, archive=store
    )
    assert result.improved is True
    members = store.members()
    # Baseline + at least one evolved member.
    assert len(members) >= 2
    baseline = [m for m in members if m.parent_id is None]
    evolved = [m for m in members if m.parent_id is not None]
    assert len(baseline) == 1
    assert evolved, "evolved member should chain to the baseline"
    assert evolved[0].parent_id == baseline[0].member_id


def test_evolve_without_archive_still_works() -> None:
    # The archive is optional; evolve must not require it.
    result = evolve(DEMO_EVOLVE_TASK, DEMO_BASELINE_CODE, demo_variant_proposer)
    assert result.improved is True
