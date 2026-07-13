"""Regression guard for per-attempt API latency telemetry.

A retry loop must measure each provider attempt independently.  Carrying an
initial timestamp across retries inflates the latency reported to post-api hooks
and makes benchmark/provider-routing data misleading.
"""

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / "agent" / "conversation_loop.py"


def _is_api_retry_loop(node: ast.While) -> bool:
    return (
        isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "retry_count"
        and len(node.test.ops) == 1
        and isinstance(node.test.ops[0], ast.Lt)
        and len(node.test.comparators) == 1
        and isinstance(node.test.comparators[0], ast.Name)
        and node.test.comparators[0].id == "max_retries"
    )


def test_api_duration_timer_starts_inside_each_retry_attempt():
    module = ast.parse(SOURCE.read_text(encoding="utf-8"))
    retry_loop = next(node for node in ast.walk(module) if isinstance(node, ast.While) and _is_api_retry_loop(node))

    timer_lines = [
        node.lineno
        for node in ast.walk(retry_loop)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "api_start_time" for target in node.targets)
    ]
    api_call_lines = [
        node.lineno
        for node in ast.walk(retry_loop)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"_interruptible_streaming_api_call", "_interruptible_api_call"}
    ]

    assert timer_lines
    assert api_call_lines
    assert min(timer_lines) < min(api_call_lines)
