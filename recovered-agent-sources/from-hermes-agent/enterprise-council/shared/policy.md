# Risk taxonomy & human-in-the-loop matrix

The orchestrator and judge both consult
`enterprise.policy.classify(task)`. The rules live in code (so unit
tests can lock them down) — this document is the human-readable
mirror.

## Risk levels

| Level | Meaning | Autonomy in `default` mode | Audit retention |
|---|---|---|---|
| LOW | Read-only lookups, internal summaries | Always autonomous | 30 days |
| MEDIUM | Mutates a customer record, sends a proposal, files a routine compliance report | Autonomous in `default`, paused in `strict` | 90 days |
| HIGH | Moves money, sends mass comms, executes a contract, terminates employment, exports regulated PII | Always paused for confirmation in `default` and `strict`. Skipped in `yolo` (acknowledged risk). | 7 years (regulated) |

## When the user is asked

`policy.requires_human(task, autonomy=...)`:

  * `default` — only HIGH-risk tasks pause.
  * `strict` — MEDIUM and HIGH pause.
  * `yolo` — nothing pauses. Mirrors Hermes' YOLO mode; operator opts
    in via the council profile.

## Threshold bumps

The base level is bumped one notch when an amount-shaped argument
exceeds a domain threshold:

| (domain, action) | threshold | reason |
|---|---|---|
| finance.invoice.create / .send | $50,000 | Wire-eligible amount. |
| finance.payment.refund | $5,000 | Chargeback risk. |
| sales.discount.apply | 25% off | Revenue impact. |
| sales.proposal.send | $100,000 | Enterprise-sized deal. |

Tag overrides:

  * Any tag starting with `@` forces HIGH.
  * `gdpr`, `regulated`, `irreversible`, `external-mass` bump one
    level. They stack with thresholds.

## Adding a new action

1. Add the (domain, action) row to `enterprise.policy._BASE_RULES`.
2. List the action in the corresponding leaf SKILL.md table.
3. Add a test case to `tests/enterprise/test_policy.py`.
4. Update this document if the new action introduces a new risk
   pattern (mass comms, regulated data, money movement, etc.).
