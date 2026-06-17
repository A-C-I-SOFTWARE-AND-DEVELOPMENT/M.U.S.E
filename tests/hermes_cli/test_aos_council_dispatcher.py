"""The AOS council runtime routes a request to the real registry.

Most assertions use a small synthetic registry (so they don't couple to the
shipped catalog's exact contents); one test confirms the real
``operating-registry/registry.json`` loads and routes.
"""

from __future__ import annotations

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
