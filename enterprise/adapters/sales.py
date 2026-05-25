"""Sales domain adapter — mock Salesforce / HubSpot / DocuSign."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping

from enterprise.secrets import SecretBundle


@dataclass
class SalesAdapter:
    secret: SecretBundle
    leads: dict[str, dict[str, Any]] = field(default_factory=dict)
    proposals: dict[str, dict[str, Any]] = field(default_factory=dict)

    # ── lead pipeline ───────────────────────────────────────────────────

    def lead_read(self, lead_id: str) -> dict[str, Any]:
        if lead_id not in self.leads:
            return {"status": "not_found", "lead_id": lead_id}
        return {"status": "ok", "lead": self.leads[lead_id]}

    def lead_update(self, lead_id: str, stage: str, notes: str = "") -> dict[str, Any]:
        lead = self.leads.setdefault(
            lead_id, {"id": lead_id, "stage": "new", "notes": []}
        )
        lead["stage"] = stage
        if notes:
            lead.setdefault("notes", []).append(notes)
        return {"status": "ok", "lead_id": lead_id, "stage": stage}

    # ── proposals + contracts ───────────────────────────────────────────

    def proposal_draft(
        self,
        lead_id: str,
        product: str,
        amount: float,
        currency: str = "USD",
    ) -> dict[str, Any]:
        pid = f"PROP-{uuid.uuid4().hex[:8].upper()}"
        self.proposals[pid] = {
            "id": pid,
            "lead_id": lead_id,
            "product": product,
            "amount": amount,
            "currency": currency,
            "state": "draft",
        }
        return {"status": "ok", "proposal_id": pid, "amount": amount}

    def proposal_send(self, proposal_id: str) -> dict[str, Any]:
        if proposal_id not in self.proposals:
            return {"status": "not_found", "proposal_id": proposal_id}
        self.proposals[proposal_id]["state"] = "sent"
        return {"status": "ok", "proposal_id": proposal_id, "state": "sent"}

    def contract_execute(self, proposal_id: str, counterparty: str) -> dict[str, Any]:
        if proposal_id not in self.proposals:
            return {"status": "not_found", "proposal_id": proposal_id}
        self.proposals[proposal_id]["state"] = "executed"
        return {
            "status": "ok",
            "proposal_id": proposal_id,
            "counterparty": counterparty,
            "envelope_id": f"ENV-{uuid.uuid4().hex[:6].upper()}",
        }

    def discount_apply(
        self, proposal_id: str, discount: float, reason: str = ""
    ) -> dict[str, Any]:
        if not (0 < discount <= 1):
            return {"status": "rejected", "reason": "discount must be in (0,1]"}
        if proposal_id not in self.proposals:
            return {"status": "not_found", "proposal_id": proposal_id}
        original = self.proposals[proposal_id]["amount"]
        self.proposals[proposal_id]["amount"] = round(original * (1 - discount), 2)
        self.proposals[proposal_id]["discount_applied"] = discount
        self.proposals[proposal_id]["discount_reason"] = reason
        return {
            "status": "ok",
            "proposal_id": proposal_id,
            "discount": discount,
            "new_amount": self.proposals[proposal_id]["amount"],
        }

    def call(self, action: str, args: Mapping[str, Any]) -> dict[str, Any]:
        method = action.replace(".", "_")
        fn = getattr(self, method, None)
        if not callable(fn):
            return {"status": "unknown_action", "action": action}
        return fn(**dict(args))


def build(secret: SecretBundle) -> SalesAdapter:
    return SalesAdapter(secret=secret)
