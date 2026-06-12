"""Tests for the grain non-overlap kernel — the collision-freedom guarantee."""

from __future__ import annotations

import pytest

from muse_cli.swarm.grain import (
    FileDomain,
    Grain,
    OverlapError,
    SwarmPlan,
    globs_overlap,
)


# ── glob intersection (conservative: never a false "disjoint") ──────────────


@pytest.mark.parametrize(
    "a,b",
    [
        ("src/api/**", "src/api/**"),          # identical
        ("src/api/**", "src/api/routes.py"),   # ** absorbs the file
        ("src/**", "src/api/routes.py"),       # ** absorbs deeper
        ("src/*.py", "src/api.py"),            # single-segment wildcard
        ("**", "anything/at/all.py"),          # top-level globstar
        ("a/**/z.py", "a/b/c/z.py"),           # middle globstar
    ],
)
def test_overlapping_globs_detected(a, b):
    assert globs_overlap(a, b) is True


@pytest.mark.parametrize(
    "a,b",
    [
        ("src/api/routes.py", "src/web/routes.py"),  # different literal dir
        ("src/api/**", "src/web/**"),                 # disjoint subtrees
        ("docs/**", "src/**"),                        # different roots
        ("a/b/c.py", "a/b/d.py"),                     # sibling files
    ],
)
def test_disjoint_globs_proven(a, b):
    assert globs_overlap(a, b) is False


def test_file_domain_disjoint_and_pairs():
    a = FileDomain(globs=("src/api/**",))
    b = FileDomain(globs=("src/web/**",))
    c = FileDomain(globs=("src/api/routes.py",))
    assert a.disjoint(b) is True
    assert a.disjoint(c) is False
    assert a.overlapping_pairs(c) == [("src/api/**", "src/api/routes.py")]


def test_file_domain_requires_globs():
    with pytest.raises(ValueError):
        FileDomain(globs=())


# ── Grain ───────────────────────────────────────────────────────────────────


def test_grain_namespace_and_validation():
    g = Grain(grain_id="g01", intent="do a thing", domain=FileDomain(globs=("src/**",)))
    assert g.memory_namespace == "swarm/grain/g01"
    assert g.owner_gated is False
    with pytest.raises(ValueError):
        Grain(grain_id="", intent="x", domain=FileDomain(globs=("a",)))
    with pytest.raises(ValueError):
        Grain(grain_id="g", intent="  ", domain=FileDomain(globs=("a",)))


def test_grain_owner_gated_flag():
    g = Grain(
        grain_id="g",
        intent="deploy",
        domain=FileDomain(globs=("infra/**",)),
        owner_gated_actions=("production_deploy",),
    )
    assert g.owner_gated is True


# ── SwarmPlan.prove_disjoint — the headline guarantee ───────────────────────


def _g(gid, globs):
    return Grain(grain_id=gid, intent=f"work {gid}", domain=FileDomain(globs=globs))


def test_plan_proves_disjoint_when_domains_separate():
    plan = SwarmPlan(
        job_id="job-1",
        goal="build two separate areas",
        grains=(_g("api", ("src/api/**",)), _g("web", ("src/web/**",))),
    )
    plan.prove_disjoint()  # must not raise
    assert plan.is_trivial is False
    assert plan.blackboard_namespace == "swarm/job-1"


def test_plan_rejects_overlapping_domains():
    plan = SwarmPlan(
        job_id="job-2",
        goal="two grains fighting over the same files",
        grains=(_g("a", ("src/api/**",)), _g("b", ("src/api/routes.py",))),
    )
    with pytest.raises(OverlapError) as exc:
        plan.prove_disjoint()
    assert ("a", "b", "src/api/**", "src/api/routes.py") in exc.value.pairs


def test_trivial_plan_flag():
    plan = SwarmPlan(job_id="j", goal="one thing", grains=(_g("only", ("src/**",)),))
    assert plan.is_trivial is True


def test_plan_rejects_duplicate_grain_ids():
    with pytest.raises(ValueError):
        SwarmPlan(
            job_id="j",
            goal="dup",
            grains=(_g("same", ("a/**",)), _g("same", ("b/**",))),
        )
