"""Contract checks for complete per-attempt API outcome telemetry."""

import ast
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[2] / "agent" / "conversation_loop.py"


def _module():
    return ast.parse(SOURCE.read_text(encoding="utf-8"))


def _post_api_calls():
    return [
        node
        for node in ast.walk(_module())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_emit_post_api_request"
    ]


def _except_handler(exception_name: str):
    for node in ast.walk(_module()):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if isinstance(node.type, ast.Name) and node.type.id == exception_name:
            return node
    raise AssertionError(f"missing {exception_name} handler")


def test_post_api_hook_reports_success_and_failure_outcomes():
    calls = _post_api_calls()
    outcomes = {
        next(
            (keyword.value.value for keyword in call.keywords
             if keyword.arg == "api_success" and isinstance(keyword.value, ast.Constant)),
            None,
        )
        for call in calls
    }
    assert outcomes == {True, False}


def test_every_post_api_outcome_includes_attempt_identity_and_latency():
    required = {"session_id", "model", "provider", "api_call_count", "api_duration", "api_success"}
    for call in _post_api_calls():
        assert required <= {keyword.arg for keyword in call.keywords}


def test_interrupted_api_outcome_handles_an_unstarted_attempt_timer():
    """An interrupt before transport start must remain observable, not crash."""
    handler = _except_handler("InterruptedError")
    duration_assignments = [
        node for node in ast.walk(handler)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "api_elapsed" for target in node.targets)
    ]
    assert duration_assignments
    assert any(
        isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == "api_start_time"
        and any(isinstance(op, ast.IsNot) for op in node.ops)
        for node in ast.walk(duration_assignments[0].value)
    )
