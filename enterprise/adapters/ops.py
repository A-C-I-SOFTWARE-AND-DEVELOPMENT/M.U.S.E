"""Operations domain adapter — mock SAP / SlackOps / ComplianceDB."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping

from enterprise.secrets import SecretBundle


@dataclass
class OperationsAdapter:
    secret: SecretBundle
    shipments: dict[str, dict[str, Any]] = field(default_factory=dict)
    compliance_checks: dict[str, dict[str, Any]] = field(default_factory=dict)

    # ── logistics ───────────────────────────────────────────────────────

    def logistics_plan(
        self,
        origin: str,
        destination: str,
        weight_kg: float,
        priority: str = "standard",
    ) -> dict[str, Any]:
        # Trivial planner: pick a carrier by priority + weight.
        if priority == "express" or weight_kg < 5:
            carrier, eta_days = "FastCo", 1
        elif weight_kg < 50:
            carrier, eta_days = "GroundCo", 3
        else:
            carrier, eta_days = "FreightCo", 7
        shipment_id = f"SHP-{uuid.uuid4().hex[:8].upper()}"
        self.shipments[shipment_id] = {
            "id": shipment_id,
            "origin": origin,
            "destination": destination,
            "weight_kg": weight_kg,
            "priority": priority,
            "carrier": carrier,
            "eta_days": eta_days,
            "state": "planned",
        }
        return {
            "status": "ok",
            "shipment_id": shipment_id,
            "carrier": carrier,
            "eta_days": eta_days,
        }

    def logistics_execute(self, shipment_id: str) -> dict[str, Any]:
        if shipment_id not in self.shipments:
            return {"status": "not_found", "shipment_id": shipment_id}
        self.shipments[shipment_id]["state"] = "dispatched"
        return {"status": "ok", "shipment_id": shipment_id, "state": "dispatched"}

    # ── compliance ──────────────────────────────────────────────────────

    def compliance_check(
        self,
        region: str,
        category: str,
        evidence: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        # In real life this consults a rule engine. The mock returns
        # deterministic findings so the Judge can validate them.
        findings: list[str] = []
        if region.upper() == "EU" and "dpa" not in [e.lower() for e in evidence]:
            findings.append("Missing DPA evidence for EU region.")
        if category == "financial" and "soc2" not in [e.lower() for e in evidence]:
            findings.append("SOC 2 attestation not referenced.")
        cid = f"CMP-{uuid.uuid4().hex[:8].upper()}"
        verdict = "pass" if not findings else "issues"
        self.compliance_checks[cid] = {
            "id": cid,
            "region": region,
            "category": category,
            "evidence": list(evidence),
            "verdict": verdict,
            "findings": findings,
        }
        return {
            "status": "ok",
            "compliance_id": cid,
            "verdict": verdict,
            "findings": findings,
        }

    def compliance_file(self, compliance_id: str) -> dict[str, Any]:
        if compliance_id not in self.compliance_checks:
            return {"status": "not_found", "compliance_id": compliance_id}
        self.compliance_checks[compliance_id]["state"] = "filed"
        return {"status": "ok", "compliance_id": compliance_id, "state": "filed"}

    def incident_declare(self, summary: str, severity: str) -> dict[str, Any]:
        return {
            "status": "ok",
            "incident_id": f"INC-{uuid.uuid4().hex[:6].upper()}",
            "summary": summary,
            "severity": severity,
        }

    def call(self, action: str, args: Mapping[str, Any]) -> dict[str, Any]:
        method = action.replace(".", "_")
        fn = getattr(self, method, None)
        if not callable(fn):
            return {"status": "unknown_action", "action": action}
        return fn(**dict(args))


def build(secret: SecretBundle) -> OperationsAdapter:
    return OperationsAdapter(secret=secret)
