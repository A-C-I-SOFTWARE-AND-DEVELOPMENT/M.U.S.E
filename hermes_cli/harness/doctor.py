"""Doctor checks for the Muse harness runtime and continuous proof bar."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, List, Tuple


def check_harness_runtime_wired() -> Tuple[str, str, str, bool]:
    """
    Return (name, status, detail, hard) for the 10/10 doctor.

    status is ``pass`` / ``fail`` / ``warn``.
    """
    name = "harness_runtime_wired"
    try:
        from hermes_cli.harness import get_runtime, load_harness_settings
        from hermes_cli.harness.quality_gates import run_quality_gates
        from hermes_cli.harness.escalation import decide_escalation
    except Exception as exc:
        return name, "fail", f"import failed: {exc}", True

    try:
        settings = load_harness_settings()
        runtime = get_runtime(reload=True)
        # Touch public API so we fail if facade regresses
        _ = runtime.on_session_start(prompt="implement a python fix")
        _ = decide_escalation(settings, trigger="quality_gate_fail", attempt=1)
        _ = run_quality_gates  # noqa: F841
    except Exception as exc:
        return name, "fail", f"runtime load failed: {exc}", True

    if not settings.enabled:
        return (
            name,
            "warn",
            "harness package wired but harness.enabled=false in config",
            False,
        )
    return (
        name,
        "pass",
        "harness runtime importable; prefills/gates/escalation loadable",
        True,
    )


def check_harness_proof_bar() -> Tuple[str, str, str, bool]:
    """Soft check: nightly proof-bar cron + latest log are healthy."""
    name = "harness_proof_bar"
    try:
        from hermes_constants import get_hermes_home

        home = Path(get_hermes_home())
    except Exception:
        home = Path(r"C:\Users\Echer\AppData\Local\hermes")

    jobs_path = home / "cron" / "jobs.json"
    script_path = home / "scripts" / "harness_proof_bar.py"
    if not script_path.is_file():
        return name, "warn", f"missing script {script_path}", False

    cron_ok = False
    try:
        data = json.loads(jobs_path.read_text(encoding="utf-8"))
        for job in data.get("jobs") or []:
            if not isinstance(job, dict):
                continue
            if job.get("name") == "harness-proof-bar" and job.get("enabled", True):
                cron_ok = True
                break
    except Exception as exc:
        return name, "warn", f"cron jobs unreadable: {exc}", False

    if not cron_ok:
        return name, "warn", "harness-proof-bar cron job missing or disabled", False

    logs_dir = home / "logs"
    ok_logs = sorted(
        logs_dir.glob("harness-proof-ok-*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    fail_logs = sorted(
        logs_dir.glob("harness-proof-fail-*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    if not ok_logs and not fail_logs:
        return (
            name,
            "warn",
            "cron armed but no proof-bar log yet (run scripts/harness_proof_bar.py once)",
            False,
        )
    if fail_logs and (not ok_logs or fail_logs[-1].stat().st_mtime > ok_logs[-1].stat().st_mtime):
        latest_fail = fail_logs[-1]
        return name, "warn", f"latest proof bar failed: {latest_fail.name}", False
    latest = ok_logs[-1]
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception as exc:
        return name, "warn", f"latest log unreadable ({latest.name}): {exc}", False
    if payload.get("ok"):
        return name, "pass", f"cron armed; latest {latest.name} ok", False
    return name, "warn", f"latest proof bar failed: {latest.name}", False


def check_harness_web_degraded() -> Tuple[str, str, str, bool]:
    """Soft note: web search keys missing is OK when fetch MCP is enabled."""
    name = "harness_web_research_path"
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
    except Exception as exc:
        return name, "warn", f"config load failed: {exc}", False

    import os

    has_search_key = any(
        os.environ.get(k)
        for k in ("EXA_API_KEY", "TAVILY_API_KEY", "FIRECRAWL_API_KEY", "PARALLEL_API_KEY")
    )
    mcp = cfg.get("mcp_servers") if isinstance(cfg.get("mcp_servers"), dict) else {}
    fetch_cfg = mcp.get("fetch") if isinstance(mcp.get("fetch"), dict) else {}
    fetch_on = bool(fetch_cfg) and fetch_cfg.get("enabled", True)
    if has_search_key:
        return name, "pass", "dedicated web search key present", False
    if fetch_on:
        return (
            name,
            "pass",
            "no EXA/Tavily/Firecrawl key; research via MCP fetch (+ Gemini) is enabled",
            False,
        )
    return (
        name,
        "warn",
        "no web search key and mcp_servers.fetch disabled — research will be weak",
        False,
    )


def all_harness_doctor_checks() -> List[Tuple[str, str, str, bool]]:
    return [
        check_harness_runtime_wired(),
        check_harness_proof_bar(),
        check_harness_web_degraded(),
    ]


def as_doctor_check(check_fn: Callable[[], Tuple[str, str, str, bool]]):
    """Adapter used by release_readiness_doctor if it expects a zero-arg callable."""
    return check_fn
