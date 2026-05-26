"""CustomerService domain adapter — mock Zendesk / Intercom / KB."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping

from enterprise.secrets import SecretBundle


@dataclass
class CustomerServiceAdapter:
    secret: SecretBundle
    tickets: dict[str, dict[str, Any]] = field(default_factory=dict)
    kb_articles: dict[str, str] = field(
        default_factory=lambda: {
            "password-reset": "Send the user the /reset endpoint and require new MFA.",
            "billing-charge": "Refunds under $50 are auto-approved; over $50 needs Finance.",
            "refund-policy": "30-day window from invoice date; pro-rated for annual plans.",
            "outage-status": "Direct customers to status.example.com for live incidents.",
        }
    )

    # ── ticket triage ───────────────────────────────────────────────────

    def ticket_classify(self, subject: str, body: str) -> dict[str, Any]:
        text = f"{subject}\n{body}".lower()
        if any(w in text for w in ("refund", "charge", "billing")):
            category, severity = "billing", "medium"
        elif any(w in text for w in ("password", "login", "mfa")):
            category, severity = "auth", "low"
        elif any(w in text for w in ("down", "outage", "500", "error")):
            category, severity = "outage", "high"
        else:
            category, severity = "general", "low"
        tid = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        self.tickets[tid] = {
            "id": tid,
            "subject": subject,
            "body": body,
            "category": category,
            "severity": severity,
            "state": "open",
        }
        return {
            "status": "ok",
            "ticket_id": tid,
            "category": category,
            "severity": severity,
        }

    def kb_retrieve(self, query: str, top_k: int = 3) -> dict[str, Any]:
        q = query.lower()
        scored = []
        for key, body in self.kb_articles.items():
            score = sum(1 for tok in q.split() if tok in key or tok in body.lower())
            if score:
                scored.append((score, key, body))
        scored.sort(reverse=True)
        hits = [
            {"key": key, "snippet": body[:120]}
            for _, key, body in scored[: max(top_k, 0)]
        ]
        return {"status": "ok", "query": query, "hits": hits}

    def ticket_reply(self, ticket_id: str, body: str) -> dict[str, Any]:
        if ticket_id not in self.tickets:
            return {"status": "not_found", "ticket_id": ticket_id}
        self.tickets[ticket_id]["state"] = "responded"
        return {"status": "ok", "ticket_id": ticket_id, "reply_length": len(body)}

    def ticket_escalate(self, ticket_id: str, to_team: str) -> dict[str, Any]:
        if ticket_id not in self.tickets:
            return {"status": "not_found", "ticket_id": ticket_id}
        self.tickets[ticket_id]["state"] = f"escalated:{to_team}"
        return {"status": "ok", "ticket_id": ticket_id, "team": to_team}

    def mass_email(self, segment: str, subject: str, body: str) -> dict[str, Any]:
        # Real implementation would queue via a transactional email provider.
        return {
            "status": "ok",
            "segment": segment,
            "subject": subject,
            "approx_recipients": {
                "customers": 12_500,
                "trial": 3_200,
                "churned": 580,
            }.get(segment, 0),
            "preview": body[:120],
        }

    def call(self, action: str, args: Mapping[str, Any]) -> dict[str, Any]:
        method = action.replace(".", "_")
        fn = getattr(self, method, None)
        if not callable(fn):
            return {"status": "unknown_action", "action": action}
        return fn(**dict(args))


def build(secret: SecretBundle) -> CustomerServiceAdapter:
    return CustomerServiceAdapter(secret=secret)
