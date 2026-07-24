"""Tests for the Muse harness runtime (EVAL / capability uplift layers)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli.harness.config import HarnessSettings, load_harness_settings
from hermes_cli.harness.escalation import decide_escalation, pick_fallback_provider
from hermes_cli.harness.prefills import detect_task_type, load_task_prefill, merge_prefills
from hermes_cli.harness.quality_gates import run_quality_gates
from hermes_cli.harness.runtime import HarnessRuntime
from hermes_cli.harness.doctor import check_harness_runtime_wired


HERMES_HOME = Path(r"C:\Users\Echer\AppData\Local\hermes")


def _live_harness_config() -> dict:
    return {
        "harness": {
            "version": 1,
            "enabled": True,
            "model_registry": {
                "file": str(HERMES_HOME / "model_registry.yaml"),
                "auto_route": True,
                "default_tier": "capable",
            },
            "prefill_system": {
                "enabled": True,
                "directory": str(HERMES_HOME / "prefills"),
                "task_prefills": {
                    "coding": "coding.md",
                    "debugging": "debugging.md",
                    "research": "research.md",
                },
                "auto_detect": True,
                "default": "coding.md",
            },
            "quality_gates": {
                "enabled": True,
                "directory": str(HERMES_HOME / "quality_gates"),
                "auto_detect_language": True,
                "default_gate": "python.yaml",
                "enforce_on_code": True,
                "block_on_failure": True,
            },
            "structured_output": {
                "enabled": True,
                "schemas": str(HERMES_HOME / "structured_schemas.yaml"),
                "enforce_json": True,
                "validate": True,
            },
            "context_engineering": {
                "enabled": True,
                "config": str(HERMES_HOME / "context_engineering.yaml"),
                "skill_router": True,
                "project_context": True,
            },
            "escalation": {
                "enabled": True,
                "config": str(HERMES_HOME / "escalation_engine.yaml"),
                "auto_escalate": True,
                "max_attempts": 3,
                "cost_limit_usd": 5.0,
                "warn_at_usd": 1.0,
            },
        }
    }


def test_load_harness_settings_from_dict():
    settings = load_harness_settings(_live_harness_config())
    assert settings.enabled is True
    assert settings.enforce_on_code is True
    assert settings.cost_limit_usd == 5.0


def test_detect_task_type_coding_and_debug():
    settings = load_harness_settings(_live_harness_config())
    assert detect_task_type("please implement a python feature", settings) == "coding"
    assert detect_task_type("debug this traceback exception", settings) == "debugging"


def test_load_task_prefill_coding(tmp_path: Path):
    settings = load_harness_settings(_live_harness_config())
    if not (HERMES_HOME / "prefills" / "coding.md").is_file():
        pytest.skip("live prefills not present")
    msgs = load_task_prefill(settings, prompt="implement a typescript component")
    assert msgs
    assert msgs[0]["role"] == "system"
    assert "harness:" in msgs[0]["content"]


def test_merge_prefills_orders_harness_first():
    base = [{"role": "user", "content": "hi"}]
    harness = [{"role": "system", "content": "harness"}]
    merged = merge_prefills(base, harness)
    assert merged[0]["content"] == "harness"
    assert merged[1]["content"] == "hi"


def test_quality_gate_blocks_invalid_python(tmp_path: Path):
    settings = load_harness_settings(_live_harness_config())
    if not (HERMES_HOME / "quality_gates" / "python.yaml").is_file():
        pytest.skip("live quality_gates not present")
    bad = tmp_path / "bad_syntax.py"
    bad.write_text("def broken(\n", encoding="utf-8")
    result = run_quality_gates(settings, bad, max_autofix_rounds=1)
    assert result.ok is False
    assert result.blocking_failures()


def test_quality_gate_passes_valid_python(tmp_path: Path):
    settings = load_harness_settings(_live_harness_config())
    if not (HERMES_HOME / "quality_gates" / "python.yaml").is_file():
        pytest.skip("live quality_gates not present")
    good = tmp_path / "ok_mod.py"
    good.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    result = run_quality_gates(settings, good, max_autofix_rounds=1)
    # syntax + import_check must pass; optional tools may skip
    assert result.ok is True


def test_condition_matches_file_ends_with():
    from hermes_cli.harness.quality_gates import _condition_matches

    ts = Path("component.tsx")
    assert _condition_matches("file ends with .ts or .tsx", ts) is True
    assert _condition_matches("file ends with .js or .jsx or .mjs or .cjs", ts) is False
    assert _condition_matches("", ts) is True
    assert _condition_matches(None, ts) is True


def test_typescript_skips_node_check_syntax(tmp_path: Path):
    """Regression: node --check must not blocker-fail .ts writes."""
    from hermes_cli.harness.config import HarnessSettings
    from hermes_cli.harness.quality_gates import run_quality_gates

    gates_dir = tmp_path / "gates"
    gates_dir.mkdir()
    (gates_dir / "javascript.yaml").write_text(
        """
version: 1
language: javascript
gates:
  - name: syntax
    command: "node --check {file}"
    severity: blocker
    condition: "file ends with .js or .jsx or .mjs or .cjs"
  - name: type_check
    command: "npx tsc --noEmit --pretty false"
    severity: critical
    skip_if_missing: true
    condition: "file ends with .ts or .tsx"
""",
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text('{"name":"t"}', encoding="utf-8")
    ts_file = tmp_path / "hello.ts"
    ts_file.write_text("const x: number = 1;\n", encoding="utf-8")
    settings = HarnessSettings(
        enabled=True,
        quality_gates_enabled=True,
        quality_gates_directory=gates_dir,
        quality_auto_detect_language=True,
        quality_default_gate="javascript.yaml",
        enforce_on_code=True,
        block_on_failure=True,
    )
    result = run_quality_gates(settings, ts_file, max_autofix_rounds=1)
    by_name = {s.name: s for s in result.steps}
    assert by_name["syntax"].skipped is True
    assert by_name["syntax"].ok is True
    # type_check may skip or fail depending on local tsc — must not be a silent node SyntaxError
    assert "Missing initializer in const declaration" not in (by_name["syntax"].output or "")


def test_escalation_respects_raised_budget():
    settings = load_harness_settings(_live_harness_config())
    # $0.50 used to kill under old $0.10 limit; must be within $5 budget
    decision = decide_escalation(
        settings,
        trigger="quality_gate_fail",
        attempt=1,
        estimated_cost_usd=0.50,
    )
    assert decision.within_budget is True
    assert decision.action != "noop"
    assert decision.cost_limit_usd >= 5.0


def test_escalation_stops_when_over_budget():
    settings = load_harness_settings(_live_harness_config())
    decision = decide_escalation(
        settings,
        trigger="quality_gate_fail",
        attempt=1,
        estimated_cost_usd=99.0,
    )
    assert decision.within_budget is False
    assert decision.strategy == "budget"


def test_pick_fallback_skips_kimi_bridge():
    chain = [
        {"provider": "kimi-bridge", "model": "x", "base_url": "http://127.0.0.1:8001/v1"},
        {"provider": "nvidia-all", "model": "nvidia/nemotron-3-super-120b-a12b"},
    ]
    picked = pick_fallback_provider(chain)
    assert picked is not None
    assert picked["provider"] == "nvidia-all"


def test_runtime_session_start_and_gate(tmp_path: Path):
    settings = load_harness_settings(_live_harness_config())
    rt = HarnessRuntime(settings)
    msgs = rt.on_session_start(prompt="fix a bug in the stack trace")
    assert msgs
    assert rt.state.stage in {"prefill", "none"} or rt.telemetry()["harness_enabled"]

    bad = tmp_path / "broken.py"
    bad.write_text("def (\n", encoding="utf-8")
    err = rt.after_code_write(bad)
    assert err is not None
    assert "quality gate FAILED" in err
    assert rt.telemetry()["harness_stage"] in {"gate", "escalate"}


def test_doctor_harness_runtime_wired():
    name, status, detail, hard = check_harness_runtime_wired()
    assert name == "harness_runtime_wired"
    assert status in {"pass", "warn"}
    assert hard is True or status == "warn"


def test_dump_counts_top_level_mcp_servers():
    from hermes_cli.dump import _count_mcp_servers

    assert _count_mcp_servers({"mcp_servers": {"a": {"enabled": True}, "b": {"enabled": False}}}) == 1
    assert _count_mcp_servers({"mcp": {"servers": {"legacy": {}}}}) == 1
    assert _count_mcp_servers({}) == 0


def test_detect_debug_prefers_debugging_over_coding():
    settings = load_harness_settings(_live_harness_config())
    assert detect_task_type("please fix this bug and implement a patch", settings) == "debugging"


def test_harness_proof_bar_and_web_doctor_checks():
    from hermes_cli.harness.doctor import (
        check_harness_proof_bar,
        check_harness_web_degraded,
    )

    name, status, detail, hard = check_harness_proof_bar()
    assert name == "harness_proof_bar"
    assert status in {"pass", "warn"}
    assert hard is False
    assert "cron" in detail.lower() or "proof" in detail.lower() or "missing" in detail.lower()

    name2, status2, detail2, hard2 = check_harness_web_degraded()
    assert name2 == "harness_web_research_path"
    assert status2 in {"pass", "warn"}
    assert hard2 is False
    assert "fetch" in detail2.lower() or "search" in detail2.lower() or "key" in detail2.lower()
