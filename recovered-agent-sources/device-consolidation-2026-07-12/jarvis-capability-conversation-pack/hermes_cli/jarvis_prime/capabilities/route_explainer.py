"""Render a :class:`RouteDecision` for humans.

The explainer is the surface most users see. It produces the operational
handoff format described in ``skills/jarvis-prime/SKILL.md``:

    Mission:
    Route selected:
    Actions taken:
    Verification:
    Owner gates:
    Result:
    Next step:

The explainer also exposes a :meth:`short` form for mobile voice mode and
a :meth:`as_dict` form for programmatic callers (logging, debugging).
"""

from __future__ import annotations

from typing import Optional

from hermes_cli.jarvis_prime.capabilities.schemas import (
    Intent,
    RiskLevel,
    RouteDecision,
    Surface,
)


class RouteExplainer:
    """Format :class:`RouteDecision` instances for different surfaces."""

    def explain(self, decision: RouteDecision, mission: Optional[str] = None) -> str:
        if decision.defer_heavy_output or decision.surface == Surface.MOBILE_VOICE:
            return self.short(decision, mission)
        return self.long(decision, mission)

    # ------------------------------------------------------------------

    def long(self, decision: RouteDecision, mission: Optional[str] = None) -> str:
        lines = [
            f"Mission: {mission or '(unstated)'}",
            "Route selected:",
            f"  intent: {decision.intent.value}",
            f"  domain: {decision.domain or 'general'}",
            f"  risk: {decision.risk.value}",
            f"  surface: {decision.surface.value}",
            f"  confidence: {decision.confidence:.2f}",
            "Actions taken:",
        ]
        lines.extend(self._render_section("skills", decision.selected_skills))
        lines.extend(self._render_section("council", decision.selected_council))
        lines.extend(self._render_section("specialists", decision.selected_specialists))
        lines.extend(self._render_section("workers", decision.selected_workers))
        lines.extend(self._render_section("memory", decision.selected_memory))
        if decision.persona_influence:
            lines.append(f"  personas (tone only): {', '.join(decision.persona_influence)}")
        if decision.product_role_viewpoints:
            lines.append(
                f"  product roles (viewpoint only): {', '.join(decision.product_role_viewpoints)}"
            )
        lines.append("Verification:")
        lines.append("  required before claiming work done")
        lines.append("Owner gates:")
        lines.append(
            "  required" if decision.owner_gate_required else "  not required for this route"
        )
        lines.append("Result:")
        lines.append(f"  rationale ({len(decision.rationale)} signals):")
        for entry in decision.rationale:
            lines.append(f"    - {entry}")
        lines.append("Next step:")
        lines.append(f"  {self._next_step(decision)}")
        return "\n".join(lines)

    def short(self, decision: RouteDecision, mission: Optional[str] = None) -> str:
        parts = [f"route={decision.intent.value}"]
        if decision.domain:
            parts.append(f"domain={decision.domain}")
        parts.append(f"risk={decision.risk.value}")
        if decision.selected_specialists:
            parts.append("specialists=" + ",".join(decision.selected_specialists))
        if decision.selected_workers:
            parts.append("workers=" + ",".join(decision.selected_workers))
        if decision.selected_council:
            parts.append(f"council={len(decision.selected_council)}")
        if decision.owner_gate_required:
            parts.append("owner-gate")
        if decision.defer_heavy_output:
            parts.append("defer-heavy")
        return " ".join(parts)

    def as_dict(self, decision: RouteDecision) -> dict:
        return {
            "intent": decision.intent.value,
            "domain": decision.domain,
            "risk": decision.risk.value,
            "surface": decision.surface.value,
            "selected_skills": list(decision.selected_skills),
            "selected_council": list(decision.selected_council),
            "selected_specialists": list(decision.selected_specialists),
            "selected_workers": list(decision.selected_workers),
            "selected_memory": list(decision.selected_memory),
            "persona_influence": list(decision.persona_influence),
            "product_role_viewpoints": list(decision.product_role_viewpoints),
            "owner_gate_required": decision.owner_gate_required,
            "defer_heavy_output": decision.defer_heavy_output,
            "rationale": list(decision.rationale),
            "confidence": decision.confidence,
        }

    # ------------------------------------------------------------------

    @staticmethod
    def _render_section(label: str, items: list[str]) -> list[str]:
        if not items:
            return [f"  {label}: (none)"]
        return [f"  {label}: {', '.join(items)}"]

    @staticmethod
    def _next_step(decision: RouteDecision) -> str:
        if decision.intent == Intent.CASUAL:
            return "respond directly; no agents activated"
        if decision.defer_heavy_output:
            return "capture intent now, expand in focused mode"
        if decision.owner_gate_required:
            return "request owner authorization before executing"
        if decision.selected_workers:
            return "hand off to selected worker(s) with evidence packet"
        if decision.selected_specialists:
            return "request specialist review before next move"
        if decision.selected_council:
            return "convene council for multi-perspective judgment"
        if decision.risk == RiskLevel.LOW:
            return "respond directly"
        return "respond and verify before claiming done"


__all__ = ["RouteExplainer"]
