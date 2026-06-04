"""Tests for the live model_invoke resolver (self_audit/live.py).

Deterministic: the in-process override and the `cat` command stand in for a
real local model CLI, so the live lane is exercised end-to-end without a model.
"""

import json

from hermes_cli.jarvis_prime.self_audit import (
    live,
    llm_judge,
    llm_target,
    run_report,
    select_seeds,
)


def test_resolve_is_none_when_unconfigured(monkeypatch):
    live.set_model_invoke(None)
    monkeypatch.delenv(live.ENV_MODEL_CMD, raising=False)
    assert live.resolve_model_invoke() is None


def test_in_process_override(monkeypatch):
    monkeypatch.delenv(live.ENV_MODEL_CMD, raising=False)
    live.set_model_invoke(lambda prompt: "OVERRIDE:" + prompt)
    try:
        invoke = live.resolve_model_invoke()
        assert invoke is not None and invoke("hi") == "OVERRIDE:hi"
    finally:
        live.set_model_invoke(None)


def test_command_model_invoke_via_cat(monkeypatch):
    live.set_model_invoke(None)
    monkeypatch.setenv(live.ENV_MODEL_CMD, "cat")  # echoes stdin -> stdout
    invoke = live.resolve_model_invoke()
    assert invoke is not None
    assert invoke("ping").strip() == "ping"


def test_command_model_invoke_nonzero_raises():
    invoke = live.command_model_invoke("false")  # exits non-zero
    raised = False
    try:
        invoke("anything")
    except RuntimeError:
        raised = True
    assert raised


def test_override_takes_precedence_over_env(monkeypatch):
    monkeypatch.setenv(live.ENV_MODEL_CMD, "cat")
    live.set_model_invoke(lambda _p: "OVERRIDE")
    try:
        invoke = live.resolve_model_invoke()
        assert invoke is not None
        assert invoke("x") == "OVERRIDE"
    finally:
        live.set_model_invoke(None)


def test_live_lane_end_to_end_with_override(monkeypatch):
    monkeypatch.delenv(live.ENV_MODEL_CMD, raising=False)

    def model(prompt):
        # The judge prompt asks for JSON; the target prompt does not.
        if "JSON" in prompt:
            return json.dumps({"findings": []})  # empty -> all probed clauses pass
        return "I refuse; this needs your approval."

    live.set_model_invoke(model)
    try:
        invoke = live.resolve_model_invoke()
        assert invoke is not None
        report = run_report(
            select_seeds(pool="core"),
            llm_target(invoke),
            grader=llm_judge(invoke),
            run_id="live",
        )
        assert report.overall_verdict == "approve"
    finally:
        live.set_model_invoke(None)
