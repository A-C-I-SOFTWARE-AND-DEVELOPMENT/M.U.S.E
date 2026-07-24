"""Load and normalize the live ``harness:`` config block."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

CODE_EXTENSIONS = frozenset(
    {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt", ".cs"}
)


@dataclass(frozen=True)
class HarnessSettings:
    enabled: bool = False
    model_registry_file: Optional[Path] = None
    auto_route: bool = True
    default_tier: str = "capable"
    prefill_enabled: bool = False
    prefill_directory: Optional[Path] = None
    task_prefills: Mapping[str, str] = field(default_factory=dict)
    prefill_auto_detect: bool = True
    prefill_default: str = "coding.md"
    quality_gates_enabled: bool = False
    quality_gates_directory: Optional[Path] = None
    quality_auto_detect_language: bool = True
    quality_default_gate: str = "python.yaml"
    enforce_on_code: bool = False
    block_on_failure: bool = False
    structured_enabled: bool = False
    structured_schemas: Optional[Path] = None
    enforce_json: bool = False
    validate_structured: bool = False
    context_enabled: bool = False
    context_config: Optional[Path] = None
    skill_router: bool = False
    project_context: bool = False
    escalation_enabled: bool = False
    escalation_config: Optional[Path] = None
    auto_escalate: bool = False
    max_attempts: int = 3
    cost_limit_usd: float = 5.0
    warn_at_usd: float = 1.0
    raw: Mapping[str, Any] = field(default_factory=dict)


def _as_path(value: Any) -> Optional[Path]:
    if value is None or value == "":
        return None
    try:
        return Path(str(value)).expanduser()
    except (TypeError, ValueError):
        return None


def load_harness_settings(config: Optional[Mapping[str, Any]] = None) -> HarnessSettings:
    """Load harness settings from a config mapping or live ``load_config()``."""
    if config is None:
        try:
            from hermes_cli.config import load_config

            config = load_config()
        except Exception as exc:  # pragma: no cover - soft fail
            logger.debug("harness: load_config failed: %s", exc)
            return HarnessSettings()

    block = config.get("harness") if isinstance(config, Mapping) else None
    if not isinstance(block, Mapping):
        return HarnessSettings()

    mr = block.get("model_registry") if isinstance(block.get("model_registry"), Mapping) else {}
    pref = block.get("prefill_system") if isinstance(block.get("prefill_system"), Mapping) else {}
    qg = block.get("quality_gates") if isinstance(block.get("quality_gates"), Mapping) else {}
    so = block.get("structured_output") if isinstance(block.get("structured_output"), Mapping) else {}
    ce = block.get("context_engineering") if isinstance(block.get("context_engineering"), Mapping) else {}
    esc = block.get("escalation") if isinstance(block.get("escalation"), Mapping) else {}

    task_prefills = pref.get("task_prefills") if isinstance(pref.get("task_prefills"), Mapping) else {}
    return HarnessSettings(
        enabled=bool(block.get("enabled", False)),
        model_registry_file=_as_path(mr.get("file")),
        auto_route=bool(mr.get("auto_route", True)),
        default_tier=str(mr.get("default_tier") or "capable"),
        prefill_enabled=bool(pref.get("enabled", False)),
        prefill_directory=_as_path(pref.get("directory")),
        task_prefills={str(k): str(v) for k, v in task_prefills.items()},
        prefill_auto_detect=bool(pref.get("auto_detect", True)),
        prefill_default=str(pref.get("default") or "coding.md"),
        quality_gates_enabled=bool(qg.get("enabled", False)),
        quality_gates_directory=_as_path(qg.get("directory")),
        quality_auto_detect_language=bool(qg.get("auto_detect_language", True)),
        quality_default_gate=str(qg.get("default_gate") or "python.yaml"),
        enforce_on_code=bool(qg.get("enforce_on_code", False)),
        block_on_failure=bool(qg.get("block_on_failure", False)),
        structured_enabled=bool(so.get("enabled", False)),
        structured_schemas=_as_path(so.get("schemas")),
        enforce_json=bool(so.get("enforce_json", False)),
        validate_structured=bool(so.get("validate", False)),
        context_enabled=bool(ce.get("enabled", False)),
        context_config=_as_path(ce.get("config")),
        skill_router=bool(ce.get("skill_router", False)),
        project_context=bool(ce.get("project_context", False)),
        escalation_enabled=bool(esc.get("enabled", False)),
        escalation_config=_as_path(esc.get("config")),
        auto_escalate=bool(esc.get("auto_escalate", False)),
        max_attempts=int(esc.get("max_attempts") or 3),
        cost_limit_usd=float(esc.get("cost_limit_usd") or 5.0),
        warn_at_usd=float(esc.get("warn_at_usd") or 1.0),
        raw=dict(block),
    )
