"""Escalation engine — honor escalation_engine.yaml cost limits and strategies."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence

from hermes_cli.harness.config import HarnessSettings

logger = logging.getLogger(__name__)


@dataclass
class EscalationDecision:
    action: str
    strategy: str
    reason: str
    cost_limit_usd: float
    warn_at_usd: float
    within_budget: bool = True
    next_hint: str = ""


def _load_yaml(path: Path) -> Mapping[str, Any]:
    try:
        import yaml
    except ImportError:
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("escalation: failed to read %s: %s", path, exc)
        return {}
    return data if isinstance(data, Mapping) else {}


def decide_escalation(
    settings: HarnessSettings,
    *,
    trigger: str = "quality_gate_fail",
    attempt: int = 1,
    estimated_cost_usd: float = 0.0,
) -> EscalationDecision:
    """Pick an escalation strategy without calling models (decision-only)."""
    cost_limit = float(settings.cost_limit_usd)
    warn_at = float(settings.warn_at_usd)
    strategy_name = "next_in_chain"
    reason = trigger

    if not settings.enabled or not settings.escalation_enabled:
        return EscalationDecision(
            action="noop",
            strategy="none",
            reason="escalation disabled",
            cost_limit_usd=cost_limit,
            warn_at_usd=warn_at,
            within_budget=True,
        )

    cfg_path = settings.escalation_config
    data: Mapping[str, Any] = {}
    if cfg_path and cfg_path.is_file():
        data = _load_yaml(cfg_path)

    cost_controls = data.get("cost_controls") if isinstance(data.get("cost_controls"), Mapping) else {}
    # Harness config wins over YAML when both set — allows raising budgets without
    # editing the engine file mid-flight, and prevents stale $0.10 YAML from
    # silently killing frontier escalation.
    if cost_controls:
        file_limit = float(cost_controls.get("max_escalation_cost", cost_limit))
        file_warn = float(cost_controls.get("warn_at_cost", warn_at))
        cost_limit = max(cost_limit, file_limit) if cost_limit else file_limit
        # Prefer explicit harness.escalation.cost_limit_usd when present
        cost_limit = float(settings.cost_limit_usd or cost_limit)
        warn_at = float(settings.warn_at_usd or file_warn)

    triggers = data.get("triggers") if isinstance(data.get("triggers"), Mapping) else {}
    trig = triggers.get(trigger) if isinstance(triggers.get(trigger), Mapping) else {}
    max_iterations = int(trig.get("max_iterations") or settings.max_attempts or 3)
    escalate_to = str(trig.get("escalate_to") or "next_in_chain")

    if attempt > max_iterations:
        return EscalationDecision(
            action="stop",
            strategy="exhausted",
            reason=f"attempt {attempt} > max_iterations {max_iterations}",
            cost_limit_usd=cost_limit,
            warn_at_usd=warn_at,
            within_budget=estimated_cost_usd <= cost_limit,
        )

    if estimated_cost_usd > cost_limit:
        return EscalationDecision(
            action="stop",
            strategy="budget",
            reason=f"estimated_cost {estimated_cost_usd} exceeds limit {cost_limit}",
            cost_limit_usd=cost_limit,
            warn_at_usd=warn_at,
            within_budget=False,
        )

    strategies = data.get("strategies") if isinstance(data.get("strategies"), Mapping) else {}
    strat = strategies.get(escalate_to) if isinstance(strategies.get(escalate_to), Mapping) else {}
    action = str(strat.get("action") or "select_next_model")
    strategy_name = escalate_to

    # After repeated failures, jump to frontier strategy if defined
    if attempt >= max_iterations and "frontier" in strategies:
        strategy_name = "frontier"
        frontier = strategies.get("frontier") if isinstance(strategies.get("frontier"), Mapping) else {}
        action = str(frontier.get("action") or "select_frontier_model")
        reason = f"{trigger} -> frontier after {attempt} attempts"

    return EscalationDecision(
        action=action,
        strategy=strategy_name,
        reason=reason,
        cost_limit_usd=cost_limit,
        warn_at_usd=warn_at,
        within_budget=True,
        next_hint=action,
    )


def pick_fallback_provider(
    fallback_providers: Sequence[Mapping[str, Any]],
    *,
    skip_providers: Optional[Sequence[str]] = None,
) -> Optional[Mapping[str, Any]]:
    """Return the first usable fallback entry, skipping dead/local bridges."""
    skip = {s.lower() for s in (skip_providers or ("kimi-bridge",))}
    for entry in fallback_providers:
        if not isinstance(entry, Mapping):
            continue
        provider = str(entry.get("provider") or "").lower()
        base = str(entry.get("base_url") or "")
        if provider in skip:
            continue
        if "127.0.0.1:8001" in base or "localhost:8001" in base:
            continue
        return entry
    return None
