"""HR domain adapter — mock Workday / Greenhouse / BambooHR."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping

from enterprise.secrets import SecretBundle


@dataclass
class HRAdapter:
    secret: SecretBundle
    candidates: dict[str, dict[str, Any]] = field(default_factory=dict)
    offers: dict[str, dict[str, Any]] = field(default_factory=dict)
    policies: dict[str, str] = field(
        default_factory=lambda: {
            "remote-work": "Hybrid: minimum 2 days/week in-office unless approved exception.",
            "pto": "Unlimited PTO subject to manager approval and team coverage.",
            "wfh-stipend": "$1,200 / year for home office equipment, reimbursed on receipt.",
        }
    )

    # ── policy + recruiting ─────────────────────────────────────────────

    def policy_lookup(self, key: str) -> dict[str, Any]:
        if key in self.policies:
            return {"status": "ok", "key": key, "value": self.policies[key]}
        return {"status": "not_found", "key": key}

    def candidate_screen(
        self,
        name: str,
        resume_text: str,
        role: str,
        required_skills: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        # Trivial keyword score — replace with real ATS scoring in prod.
        text = resume_text.lower()
        present = [s for s in required_skills if s.lower() in text]
        missing = [s for s in required_skills if s.lower() not in text]
        score = round(100 * len(present) / max(len(required_skills), 1), 1)
        cid = f"CAND-{uuid.uuid4().hex[:8].upper()}"
        self.candidates[cid] = {
            "id": cid,
            "name": name,
            "role": role,
            "score": score,
            "skills_present": present,
            "skills_missing": missing,
        }
        return {
            "status": "ok",
            "candidate_id": cid,
            "score": score,
            "skills_present": present,
            "skills_missing": missing,
            "recommendation": "interview" if score >= 60 else "decline",
        }

    # ── offers + lifecycle ──────────────────────────────────────────────

    def offer_create(
        self,
        candidate_id: str,
        salary: float,
        currency: str = "USD",
        start_date: str = "",
    ) -> dict[str, Any]:
        if candidate_id not in self.candidates:
            return {"status": "not_found", "candidate_id": candidate_id}
        offer_id = f"OFF-{uuid.uuid4().hex[:8].upper()}"
        self.offers[offer_id] = {
            "id": offer_id,
            "candidate_id": candidate_id,
            "salary": salary,
            "currency": currency,
            "start_date": start_date,
            "state": "draft",
        }
        return {"status": "ok", "offer_id": offer_id}

    def offer_send(self, offer_id: str) -> dict[str, Any]:
        if offer_id not in self.offers:
            return {"status": "not_found", "offer_id": offer_id}
        self.offers[offer_id]["state"] = "sent"
        return {"status": "ok", "offer_id": offer_id, "state": "sent"}

    def employee_terminate(self, employee_id: str, reason: str) -> dict[str, Any]:
        # In a real system this would write to Workday + payroll + sso revoke.
        return {
            "status": "ok",
            "employee_id": employee_id,
            "reason": reason,
            "termination_id": f"TERM-{uuid.uuid4().hex[:6].upper()}",
        }

    def pii_export(self, employee_id: str, fields: tuple[str, ...]) -> dict[str, Any]:
        # Mock: just returns the field names that would be exported. Real
        # implementation would write a GDPR-style packet to secure storage.
        return {
            "status": "ok",
            "employee_id": employee_id,
            "fields_requested": list(fields),
            "destination": "secure-vault://gdpr-export/" + employee_id,
        }

    def call(self, action: str, args: Mapping[str, Any]) -> dict[str, Any]:
        method = action.replace(".", "_")
        fn = getattr(self, method, None)
        if not callable(fn):
            return {"status": "unknown_action", "action": action}
        return fn(**dict(args))


def build(secret: SecretBundle) -> HRAdapter:
    return HRAdapter(secret=secret)
