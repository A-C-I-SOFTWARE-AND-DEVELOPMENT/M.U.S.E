"""Finance domain adapter — mock Stripe / NetSuite / QuickBooks.

Methods mirror the actions declared in `enterprise.policy._BASE_RULES`
under the "finance" domain. Real-world wiring replaces the in-memory
dicts here with SDK calls; the method signatures and return shapes
should NOT change so the Finance SKILL.md and the orchestrator's
contract keep working.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping

from enterprise.secrets import SecretBundle


@dataclass
class FinanceAdapter:
    """In-memory finance backend.

    Attributes:
        secret: credential the orchestrator handed in.
        ledger: invoice store, keyed by invoice id.
        budgets: budget envelopes keyed by name.
    """

    secret: SecretBundle
    ledger: dict[str, dict[str, Any]] = field(default_factory=dict)
    budgets: dict[str, dict[str, float]] = field(default_factory=dict)

    # ── invoicing ───────────────────────────────────────────────────────

    def invoice_read(self, invoice_id: str) -> dict[str, Any]:
        if invoice_id not in self.ledger:
            return {"status": "not_found", "invoice_id": invoice_id}
        return {"status": "ok", "invoice": self.ledger[invoice_id]}

    def invoice_create(
        self,
        vendor: str,
        amount: float,
        memo: str = "",
        currency: str = "USD",
    ) -> dict[str, Any]:
        if amount <= 0:
            return {"status": "rejected", "reason": "amount must be positive"}
        invoice_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
        self.ledger[invoice_id] = {
            "id": invoice_id,
            "vendor": vendor,
            "amount": amount,
            "currency": currency,
            "memo": memo,
            "state": "draft",
        }
        return {"status": "ok", "invoice_id": invoice_id, "amount": amount}

    def invoice_send(self, invoice_id: str) -> dict[str, Any]:
        if invoice_id not in self.ledger:
            return {"status": "not_found", "invoice_id": invoice_id}
        self.ledger[invoice_id]["state"] = "sent"
        return {"status": "ok", "invoice_id": invoice_id, "state": "sent"}

    # ── payments ────────────────────────────────────────────────────────

    def payment_refund(self, invoice_id: str, amount: float) -> dict[str, Any]:
        if invoice_id not in self.ledger:
            return {"status": "not_found", "invoice_id": invoice_id}
        self.ledger[invoice_id]["state"] = "refunded"
        return {"status": "ok", "invoice_id": invoice_id, "refunded": amount}

    def payment_wire(self, beneficiary: str, amount: float) -> dict[str, Any]:
        # Real Stripe/NetSuite would call out here. Mock just records.
        return {
            "status": "ok",
            "beneficiary": beneficiary,
            "amount": amount,
            "confirmation": f"WIRE-{uuid.uuid4().hex[:6].upper()}",
        }

    # ── budgets + reporting ─────────────────────────────────────────────

    def budget_read(self, name: str) -> dict[str, Any]:
        return self.budgets.get(name, {"name": name, "spent": 0.0, "cap": 0.0})

    def budget_update(self, name: str, cap: float) -> dict[str, Any]:
        b = self.budgets.setdefault(name, {"name": name, "spent": 0.0, "cap": 0.0})
        b["cap"] = cap
        return {"status": "ok", "budget": b}

    def report_generate(self, period: str) -> dict[str, Any]:
        total = sum(inv["amount"] for inv in self.ledger.values())
        sent = sum(1 for inv in self.ledger.values() if inv["state"] == "sent")
        return {
            "status": "ok",
            "period": period,
            "invoice_count": len(self.ledger),
            "invoices_sent": sent,
            "ledger_total": total,
        }

    # ── dispatch ────────────────────────────────────────────────────────

    def call(self, action: str, args: Mapping[str, Any]) -> dict[str, Any]:
        method = action.replace(".", "_")
        fn = getattr(self, method, None)
        if not callable(fn):
            return {"status": "unknown_action", "action": action}
        return fn(**dict(args))


def build(secret: SecretBundle) -> FinanceAdapter:
    return FinanceAdapter(secret=secret)
