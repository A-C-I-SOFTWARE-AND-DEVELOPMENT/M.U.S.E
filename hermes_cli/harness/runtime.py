"""Harness runtime facade used by CLI and file tools."""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from hermes_cli.harness.config import CODE_EXTENSIONS, HarnessSettings, load_harness_settings
from hermes_cli.harness.escalation import EscalationDecision, decide_escalation
from hermes_cli.harness.prefills import load_task_prefill, merge_prefills
from hermes_cli.harness.quality_gates import (
    GateRunResult,
    format_gate_tool_error,
    run_quality_gates,
)
from hermes_cli.harness.skill_router import route_skills, skill_hint_message
from hermes_cli.harness.structured import StructuredResult, validate_json_payload

logger = logging.getLogger(__name__)

_tls = threading.local()


@dataclass
class SessionHarnessState:
    task_type: str = "coding"
    skills: List[str] = field(default_factory=list)
    stage: str = "none"
    last_gate: Optional[GateRunResult] = None
    last_escalation: Optional[EscalationDecision] = None


class HarnessRuntime:
    def __init__(self, settings: Optional[HarnessSettings] = None) -> None:
        self.settings = settings or load_harness_settings()
        self.state = SessionHarnessState()

    def reload(self, config: Optional[dict] = None) -> None:
        self.settings = load_harness_settings(config)

    @property
    def enabled(self) -> bool:
        return bool(self.settings.enabled)

    def on_session_start(
        self,
        prompt: str = "",
        base_prefills: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Return merged prefill messages (harness + base) for a new turn/session."""
        if not self.settings.enabled:
            self.state.stage = "none"
            return list(base_prefills or [])

        harness_msgs = load_task_prefill(self.settings, prompt=prompt)
        skills = route_skills(self.settings, prompt=prompt)
        self.state.skills = list(skills)
        hint = skill_hint_message(skills)
        if hint:
            harness_msgs = list(harness_msgs) + [hint]
        if harness_msgs:
            self.state.stage = "prefill"
            if harness_msgs and harness_msgs[0].get("_harness_task"):
                self.state.task_type = str(harness_msgs[0]["_harness_task"])
        merged = merge_prefills(base_prefills or [], harness_msgs)
        return merged

    def after_code_write(self, path: str | Path) -> Optional[str]:
        """
        Run quality gates after a successful write/patch.

        Returns an error string when the write should be reported as failed to
        the model (content may already be on disk), else None.
        """
        if not self.settings.enabled:
            return None
        if not self.settings.quality_gates_enabled or not self.settings.enforce_on_code:
            return None
        p = Path(path)
        if p.suffix.lower() not in CODE_EXTENSIONS:
            return None

        self.state.stage = "gate"
        result = run_quality_gates(
            self.settings,
            p,
            max_autofix_rounds=max(1, int(self.settings.max_attempts or 3)),
        )
        self.state.last_gate = result
        if result.ok:
            self.persist_telemetry()
            return None
        if result.should_escalate and self.settings.escalation_enabled:
            decision = decide_escalation(
                self.settings,
                trigger="quality_gate_fail",
                attempt=1,
            )
            self.state.last_escalation = decision
            self.state.stage = "escalate"
        self.persist_telemetry()
        if not self.settings.block_on_failure:
            logger.warning("harness gate soft-fail %s: %s", path, result.summary)
            return None
        return format_gate_tool_error(result, str(path))

    def on_gate_fail(self, attempt: int = 1) -> EscalationDecision:
        self.state.stage = "escalate"
        decision = decide_escalation(
            self.settings,
            trigger="quality_gate_fail",
            attempt=attempt,
        )
        self.state.last_escalation = decision
        return decision

    def validate_structured(
        self, text: str, schema_name: Optional[str] = None
    ) -> StructuredResult:
        return validate_json_payload(self.settings, text, schema_name=schema_name)

    def telemetry(self) -> Dict[str, Any]:
        return {
            "harness_enabled": self.settings.enabled,
            "harness_stage": self.state.stage,
            "harness_task": self.state.task_type,
            "harness_skills": list(self.state.skills),
            "harness_gate_ok": None if self.state.last_gate is None else self.state.last_gate.ok,
            "harness_escalate": (
                None
                if self.state.last_escalation is None
                else self.state.last_escalation.strategy
            ),
        }

    def persist_telemetry(
        self,
        session_id: Optional[str] = None,
        *,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> None:
        """Write harness_stage (+ optional model) into the session DB when possible."""
        sid = session_id or os.environ.get("HERMES_SESSION_ID") or ""
        if not sid:
            return
        try:
            from hermes_state import SessionDB

            db = SessionDB()
            db.merge_session_model_config(sid, self.telemetry())
            if model:
                db.set_session_model(sid, model, provider=provider)
        except Exception as exc:
            logger.debug("harness persist_telemetry skipped: %s", exc)


_runtime_lock = threading.Lock()
_runtime: Optional[HarnessRuntime] = None


def get_runtime(reload: bool = False) -> HarnessRuntime:
    global _runtime
    with _runtime_lock:
        if _runtime is None or reload:
            _runtime = HarnessRuntime()
        return _runtime
