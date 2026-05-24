# Skill — webhook-idempotency-review

## Purpose

Audit webhook handlers (today: Square webhook at
`api/square/webhook.mjs`; future: WorkOS, SCIM events) for
signature verification, idempotency, replay protection, and
dead-letter handling.

## Triggers

- A change to a webhook handler.
- A new webhook integration.
- A reported duplicate-event symptom.

## Required Inputs

- The webhook handler source.
- The signature verification logic
  (`api/_lib/square.mjs::verifySignature`).
- The idempotency store (today: in-process Map for Square stub
  mode; the `shared-rate-limit-store` design intent applies
  similarly).
- The handler's downstream side effects (Base44 row updates,
  audit-chain writes).

## Research Required

- Square Webhooks documentation (signature scheme + replay
  window).
- WorkOS Events documentation (when wired).
- OWASP ASVS L1/L2 — V13 API.
- NIST 800-53 SC-13, SI-10.

## Step-by-Step Method

1. Verify the handler validates the signature **before** parsing
   the body. Reject on signature failure with HTTP 401.
2. Verify replay protection: a duplicate `event_id` within a
   bounded window must not re-execute side effects.
3. Verify idempotency: re-delivering the same event produces
   no duplicate downstream rows or duplicate audit events.
4. Verify the handler does not leak the signing key in error
   responses or logs (PII scrubbing — request-id propagation
   still works).
5. Verify the handler writes to the audit chain on every
   recognized event (`audit_events` row with the right event
   type).
6. Run `npm test -- webhook`.

## Deliverable Format

Webhook Idempotency Memo: per-handler table of (signature OK?,
replay OK?, idempotency OK?, audit OK?, dead-letter strategy).

## Quality Checklist

- [ ] Signature verified pre-parse
- [ ] Replay window enforced
- [ ] Idempotency tested (re-delivery test case)
- [ ] No signing-key leakage
- [ ] Audit event written

## Escalation Triggers

- Duplicate side effect on replay → release freeze under
  `governance/09` trigger 8 (production-path instability).

## Related Agents

- Backend / API Engineer (Engineering Factory)
- Integration Engineer (Engineering Factory)
- Independent QA / V&V Agent (Assurance Office)

## Related Artifacts

- `tests/api/square/webhook.test.js`
