"""Tests for specialized grain-agents and the dynamic domain claim backstop."""

from __future__ import annotations

from pathlib import Path

import pytest

from muse_cli.swarm.grain import FileDomain, Grain
from muse_cli.swarm.specialist import (
    DomainClaimError,
    build_grain_agent_spec,
    claim_grain,
    release_grain,
)


def _grain(gid="g01", globs=("src/api/**",), **kw):
    return Grain(grain_id=gid, intent=kw.pop("intent", "do api work"),
                 domain=FileDomain(globs=globs), **kw)


def test_spec_carries_specialized_capabilities():
    g = _grain(model_lane="codex", iteration_budget=33, token_budget=1234,
               toolset_hint=("coding",))
    spec = build_grain_agent_spec(g, goal="the goal", blackboard_namespace="swarm/j")
    assert spec.grain_id == "g01"
    assert spec.model_lane == "codex"
    assert spec.iteration_budget == 33
    assert spec.token_budget == 1234
    assert spec.toolsets == ("coding",)
    # Dedicated memory namespace — grains never cross-write memory.
    assert spec.memory_namespace == "swarm/grain/g01"
    # System prompt names the domain and the isolation contract.
    assert "src/api/**" in spec.system_prompt
    assert "isolated git" in spec.system_prompt


def test_spec_surfaces_owner_gate_in_prompt():
    g = _grain(owner_gated_actions=("production_deploy",))
    spec = build_grain_agent_spec(g, goal="x", blackboard_namespace="swarm/j")
    assert "OWNER-GATED" in spec.system_prompt
    assert "Yes, with authorization." in spec.system_prompt


def test_spec_uses_token_juice_compiler(monkeypatch):
    captured = {}

    class FakeCompiled:
        used_tokens = 42
        dropped = ["something"]

        def render(self):
            return "RENDERED CONTEXT"

    class FakeCompiler:
        def compile(self, mission, budget, **kwargs):
            captured["mission"] = mission
            captured["budget"] = budget
            captured["namespaces"] = list(kwargs.get("memory_namespaces") or [])
            return FakeCompiled()

    g = _grain()
    spec = build_grain_agent_spec(
        g, goal="x", blackboard_namespace="swarm/j", compiler=FakeCompiler()
    )
    assert spec.context == "RENDERED CONTEXT"
    assert spec.used_tokens == 42
    assert spec.dropped_context == ("something",)
    assert captured["mission"] == g.intent
    assert captured["budget"] == g.token_budget
    # Scoped to the grain's private namespace + the shared blackboard.
    assert captured["namespaces"] == ["swarm/grain/g01", "swarm/j"]


# ── dynamic domain claim (runtime non-overlap backstop) ─────────────────────


def test_claim_then_overlapping_claim_rejected(tmp_path: Path):
    a = _grain("a", ("src/api/**",))
    b = _grain("b", ("src/api/routes.py",))  # overlaps a
    claim_grain(tmp_path, "job-1", a, lease_store=_NoStore())
    with pytest.raises(DomainClaimError):
        claim_grain(tmp_path, "job-1", b, lease_store=_NoStore())


def test_disjoint_claims_coexist(tmp_path: Path):
    a = _grain("a", ("src/api/**",))
    b = _grain("b", ("src/web/**",))
    claim_grain(tmp_path, "job-1", a, lease_store=_NoStore())
    claim_grain(tmp_path, "job-1", b, lease_store=_NoStore())  # must not raise


def test_release_frees_the_domain(tmp_path: Path):
    a = _grain("a", ("src/api/**",))
    overlapping = _grain("b", ("src/api/**",))
    claim_grain(tmp_path, "job-1", a, lease_store=_NoStore())
    assert release_grain(tmp_path, "job-1", "a") is True
    # Now the overlapping domain is free to claim.
    claim_grain(tmp_path, "job-1", overlapping, lease_store=_NoStore())
    assert release_grain(tmp_path, "job-1", "missing") is False


class _NoStore:
    """A lease store stub so claim_grain doesn't touch the real HERMES_HOME."""

    def upsert(self, lease):
        return lease
