"""The AOS council runtime routes a request to the real registry.

Most assertions use a small synthetic registry (so they don't couple to the
shipped catalog's exact contents); one test confirms the real
``operating-registry/registry.json`` loads and routes.
"""

from __future__ import annotations

import pytest  # ty: ignore[unresolved-import]

from hermes_cli.jarvis_prime.aos_council import dispatch, load_registry, roster

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


def test_dispatch_engages_matching_specialist_and_flags_owner_gate():
    s = dispatch("Redesign the cross-service architecture for scaling", registry=REG)
    ids = [m.id for m in s.specialists]
    assert "principal-systems-architect" in ids
    assert "commercial-strategist" not in ids
    assert len(s.council) == 2
    assert s.owner_gated is True  # the architect is owner-gated


def test_dispatch_excludes_copy_only_edits():
    s = dispatch("fix a copy-only typo", registry=REG)
    assert s.specialists == []
    assert s.owner_gated is False


def test_dispatch_caps_active_council():
    assert len(dispatch("anything", registry=REG, max_council=1).council) == 1


def test_to_dict_and_render():
    s = dispatch("pricing and business model positioning", registry=REG)
    d = s.to_dict()
    assert d["engaged_count"] == len(s.council) + len(s.specialists)
    assert "commercial-strategist" in [m["id"] for m in d["specialists"]]
    assert d["owner_gate_phrase"] == "Yes, with authorization."
    assert "AOS council session" in s.render()


def test_roster_normalizes_sections():
    r = roster(registry=REG)
    assert [m.id for m in r["active_council"]] == ["council-director", "evidence-architect"]
    assert len(r["domain_specialists"]) == 2


def test_real_registry_loads_and_routes():
    reg = load_registry()
    r = roster(reg)
    assert len(r["active_council"]) >= 5
    assert len(r["domain_specialists"]) >= 5
    s = dispatch("architecture change and scaling of services", registry=reg)
    assert any(m.id == "principal-systems-architect" for m in s.specialists)


# ---------------------------------------------------------------------------
# Effort-class council cap — default-OFF opt-in (wires effort_class.cap_council_size)
# ---------------------------------------------------------------------------
#
# A wider synthetic registry so an E2 cap (max 3) actually trims: 4 active
# council members + several specialists that all match the request. Council
# order encodes priority (highest-priority core member first).
_CAP_REG = {
    "policies": {
        "default_slack_council_max": 6,
        "owner_gate_phrase": "Yes, with authorization.",
    },
    "active_council": [
        {"id": "council-director", "role": "Router (core)."},
        {"id": "evidence-architect", "role": "Evidence (core)."},
        {"id": "delivery-scope-controller", "role": "Scope."},
        {"id": "contrarian-reviewer", "role": "Critique."},
    ],
    "domain_specialists": [
        {
            "id": "arch-specialist",
            "domain": "architecture",
            # 3 matching keywords → highest relevance.
            "when_to_use": "architecture scaling deployment services design",
            "when_not_to_use": "",
            "required_output": "Architecture memo.",
        },
        {
            "id": "scaling-specialist",
            "domain": "scaling",
            # 2 matching keywords → mid relevance.
            "when_to_use": "scaling deployment throughput",
            "when_not_to_use": "",
            "required_output": "Scaling memo.",
        },
        {
            "id": "deploy-specialist",
            "domain": "deployment",
            # 1 matching keyword → lowest relevance (most marginal).
            "when_to_use": "deployment rollout",
            "when_not_to_use": "",
            "required_output": "Deploy memo.",
        },
    ],
}

_CAP_REQUEST = "architecture scaling deployment plan"


def _enable_cap_via_registry(reg: dict) -> dict:
    out = dict(reg)
    out["policies"] = {**reg["policies"], "effort_cap": {"enabled": True}}
    return out


def test_effort_cap_off_by_default_does_not_touch_council(monkeypatch):
    # No env, no policy flag → cap must NOT be applied. The council/specialists
    # are exactly the uncapped routing outcome even though effort_class is passed.
    monkeypatch.delenv("MUSE_EFFORT_CAP", raising=False)
    baseline = dispatch(_CAP_REQUEST, registry=_CAP_REG)
    with_class = dispatch(_CAP_REQUEST, registry=_CAP_REG, effort_class="E2")
    assert [m.id for m in with_class.council] == [m.id for m in baseline.council]
    assert [m.id for m in with_class.specialists] == [m.id for m in baseline.specialists]
    # 4 council + 3 matching specialists, all present — nothing trimmed.
    assert len(with_class.council) == 4
    assert len(with_class.specialists) == 3


def test_effort_cap_off_ignores_cap_primitive(monkeypatch):
    # Even if cap_council_size WOULD return a smaller number, with the flag off
    # its result must be ignored: patching it to a crashing stub proves it is
    # never consulted on the default path.
    monkeypatch.delenv("MUSE_EFFORT_CAP", raising=False)

    import hermes_cli.jarvis_prime.effort_class as ec

    def _boom(*_a, **_k):  # pragma: no cover - must never be called when off
        raise AssertionError("cap_council_size consulted while flag is OFF")

    monkeypatch.setattr(ec, "cap_council_size", _boom)
    s = dispatch(_CAP_REQUEST, registry=_CAP_REG, effort_class="E2")
    assert len(s.council) == 4  # untouched, no crash


def test_effort_cap_on_e2_bounds_and_preserves_priority(monkeypatch):
    monkeypatch.delenv("MUSE_EFFORT_CAP", raising=False)
    reg = _enable_cap_via_registry(_CAP_REG)
    s = dispatch(_CAP_REQUEST, registry=reg, effort_class="E2")
    # E2 ceiling is 3 total engaged members.
    assert len(s.engaged) == 3
    # Highest-priority core council members are preserved (council kept first).
    assert [m.id for m in s.council] == [
        "council-director",
        "evidence-architect",
        "delivery-scope-controller",
    ]
    # All specialists were the most-marginal → dropped first.
    assert s.specialists == []


def test_effort_cap_on_e3_allows_larger_council(monkeypatch):
    monkeypatch.delenv("MUSE_EFFORT_CAP", raising=False)
    reg = _enable_cap_via_registry(_CAP_REG)
    s = dispatch(_CAP_REQUEST, registry=reg, effort_class="E3")
    # E3 ceiling is 7 ≥ the 4+3=7 engaged members → nothing trimmed.
    assert len(s.engaged) == 7
    assert len(s.council) == 4
    assert [m.id for m in s.specialists] == [
        "arch-specialist",
        "scaling-specialist",
        "deploy-specialist",
    ]


def test_effort_cap_on_drops_marginal_specialists_before_council(monkeypatch):
    # 2 council + 5 matching specialists, E2 (max 3). Drop order: the most-marginal
    # (lowest-relevance) specialists are trimmed first, from the tail; the council
    # is preserved whole. Only the single highest-relevance specialist survives.
    monkeypatch.delenv("MUSE_EFFORT_CAP", raising=False)
    reg = _enable_cap_via_registry(
        {
            "policies": {"default_slack_council_max": 6},
            "active_council": [
                {"id": "council-director", "role": "core"},
                {"id": "evidence-architect", "role": "core"},
            ],
            "domain_specialists": [
                {"id": "s3", "domain": "d", "when_to_use": "alpha bravo charlie"},
                {"id": "s2", "domain": "d", "when_to_use": "alpha bravo delta"},
                {"id": "s1", "domain": "d", "when_to_use": "alpha echo foxtrot"},
                {"id": "s0", "domain": "d", "when_to_use": "alpha golf hotel"},
                {"id": "sx", "domain": "d", "when_to_use": "alpha india juliet"},
            ],
        }
    )
    s = dispatch("alpha bravo charlie", registry=reg, effort_class="E2")
    # E2 ceiling 3 = 2 council + 1 top specialist.
    assert len(s.engaged) == 3
    assert [m.id for m in s.council] == ["council-director", "evidence-architect"]
    # Top-relevance specialist retained; the four most-marginal dropped.
    assert [m.id for m in s.specialists] == ["s3"]


def test_effort_cap_on_never_drops_council_below_floor(monkeypatch):
    # E0 ceiling is 0, but the floor guarantees at least one core member survives
    # when a council is engaged — the cap must never zero out the council.
    monkeypatch.delenv("MUSE_EFFORT_CAP", raising=False)
    reg = _enable_cap_via_registry(_CAP_REG)
    s = dispatch(_CAP_REQUEST, registry=reg, effort_class="E0")
    assert len(s.council) >= 1
    assert s.council[0].id == "council-director"  # highest-priority core preserved
    assert s.specialists == []  # all marginal specialists dropped


def test_effort_cap_on_e1_bounds_to_single_core_member(monkeypatch):
    monkeypatch.delenv("MUSE_EFFORT_CAP", raising=False)
    reg = _enable_cap_via_registry(_CAP_REG)
    s = dispatch(_CAP_REQUEST, registry=reg, effort_class="E1")
    # E1 ceiling is 1 → single highest-priority core member.
    assert len(s.engaged) == 1
    assert s.council[0].id == "council-director"


def test_effort_cap_on_env_flag_also_enables(monkeypatch):
    monkeypatch.setenv("MUSE_EFFORT_CAP", "1")
    s = dispatch(_CAP_REQUEST, registry=_CAP_REG, effort_class="E2")
    assert len(s.engaged) == 3


def test_effort_cap_on_error_falls_open_to_uncapped(monkeypatch):
    # If cap_council_size raises, the dispatcher must fail open (uncapped), never
    # crash the routing outcome.
    monkeypatch.delenv("MUSE_EFFORT_CAP", raising=False)
    reg = _enable_cap_via_registry(_CAP_REG)

    import hermes_cli.jarvis_prime.effort_class as ec

    def _boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(ec, "cap_council_size", _boom)
    s = dispatch(_CAP_REQUEST, registry=reg, effort_class="E2")
    # Uncapped fallback: full council + specialists, no exception.
    assert len(s.council) == 4
    assert len(s.specialists) == 3


def test_effort_cap_on_unknown_class_is_ignored(monkeypatch):
    monkeypatch.delenv("MUSE_EFFORT_CAP", raising=False)
    reg = _enable_cap_via_registry(_CAP_REG)
    s = dispatch(_CAP_REQUEST, registry=reg, effort_class="E9")  # not a real class
    assert len(s.council) == 4
    assert len(s.specialists) == 3


def test_effort_cap_on_none_class_is_noop(monkeypatch):
    monkeypatch.delenv("MUSE_EFFORT_CAP", raising=False)
    reg = _enable_cap_via_registry(_CAP_REG)
    s = dispatch(_CAP_REQUEST, registry=reg, effort_class=None)
    assert len(s.council) == 4
    assert len(s.specialists) == 3
