---
name: enterprise-sales
description: "Sales leaf: lead tracking, proposal drafting + sending, contract execution, discounting."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [enterprise, sales, leads, proposals, contracts]
    related_skills: [enterprise-orchestrator, enterprise-judge]
---

# Sales leaf

Drives leads through to executed contracts. Drafting and updates are
autonomous; contract execution and large discounts escalate.

## Available services

| Service | Used for |
|---|---|
| `salesforce` | CRM, opportunities |
| `hubspot` | Marketing pipeline + lead capture |
| `docusign` | Contract execution |
| `kb` | Read-only product KB (shared with CS) |

## Sub-skills (actions)

| Action | Args | Risk |
|---|---|---|
| `lead.read` | `lead_id` | LOW |
| `lead.update` | `lead_id, stage, notes` | MEDIUM |
| `proposal.draft` | `lead_id, product, amount, currency` | LOW |
| `proposal.send` | `proposal_id` | MEDIUM (HIGH if amount > $100k) |
| `contract.execute` | `proposal_id, counterparty` | HIGH |
| `discount.apply` | `proposal_id, discount, reason` | MEDIUM (HIGH if discount > 25%) |

## Credentials

`fetch_secret("salesforce", caller_role="sales", scope="opportunity.write")`
for CRM writes. Use `docusign` only when a `contract.execute` task is
explicitly dispatched.

## Structured output

Proposal draft:
```json
{"status": "ok", "proposal_id": "PROP-XXXX", "amount": 50000}
```

Contract execution:
```json
{
  "status": "ok",
  "proposal_id": "PROP-XXXX",
  "counterparty": "ACME Corp",
  "envelope_id": "ENV-XXXX"
}
```

End with `VALIDATE:`. Anything that mutates a contract or applies a
discount > 25% must include a `JURY:` block.

## Hard prohibitions

* Never apply a discount > 100% (negative price). The adapter rejects
  these; do not retry with a different number.
* Never execute a contract if the proposal `state` is not `"sent"`.
* Never overwrite a closed-won lead's stage without an explicit
  `force-overwrite` tag.
