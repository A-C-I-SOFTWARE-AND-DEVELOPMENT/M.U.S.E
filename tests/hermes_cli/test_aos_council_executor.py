"""Council execution: run each engaged member through an injected runner.

Uses a fake runner so no model is required; also verifies the no-model path
degrades to a deterministic outline (never an error).
"""

from __future__ import annotations

from hermes_cli.jarvis_prime.aos_council import dispatch, execute, executor

REG = {
    "policies": {"default_slack_council_max": 6, "owner_gate_phrase": "Yes, with authorization."},
    "active_council": [
        {"id": "council-director", "role": "Router.", "path": "x.md"},
        {"id": "evidence-architect", "role": "Evidence."},
    ],
    "domain_specialists": [
        {
            "id": "principal-systems-architect",
            "domain": "architecture",
            "when_to_use": "Architecture changes, cross-service design, scaling, data models.",
            "when_not_to_use": "Simple edits.",
            "required_output": "Architecture memo.",
            "verification_method": "Run tests.",
            "owner_gate": "Yes, with authorization.",
        },
    ],
}


def _session():
    return dispatch("Redesign the cross-service architecture for scaling", registry=REG)


def test_execute_runs_each_member_and_synthesizes():
    s = _session()
    calls: list[str] = []

    def runner(prompt: str) -> str:
        calls.append(prompt)
        return "RESP"

    d = execute(s, runner=runner, persona_loader=lambda m: "")
    assert d.executed is True
    assert len(d.results) == len(s.engaged)
    assert all(r.output == "RESP" for r in d.results)
    # one runner call per member + one for the director's synthesis
    assert len(calls) == len(s.engaged) + 1
    assert d.owner_gated is True  # the architect is owner-gated
    assert "AOS council deliberation" in d.render()
    assert d.to_dict()["executed"] is True


def test_execute_without_model_is_deterministic_outline(monkeypatch):
    monkeypatch.setattr(executor, "default_runner", lambda: None)
    d = executor.execute(_session())
    assert d.executed is False
    assert all(r.output.startswith("(would produce") for r in d.results)
    assert "deterministic outline" in d.render()
    # synthesis still names the routed members
    assert "principal-systems-architect" in d.summary


def test_member_run_failure_is_isolated(monkeypatch):
    def boom(_prompt: str) -> str:
        raise RuntimeError("model down")

    d = execute(_session(), runner=boom, persona_loader=lambda m: "")
    assert d.executed is True
    assert all("member run failed" in r.output for r in d.results)
