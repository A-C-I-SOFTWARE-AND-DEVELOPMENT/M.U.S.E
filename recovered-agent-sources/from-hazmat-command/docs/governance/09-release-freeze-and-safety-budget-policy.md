# 09 — Release Freeze and Safety Budget Policy

**Status:** Installed 2026-05-17

A release freeze automatically halts G3 (Owner Publish) per
`PUBLISH.md` when a critical condition is detected. The Risk
Controller (Executive Command, `docs/agents/01`) is the freeze
caller; the owner is the only one who can override.

## Freeze triggers (any one halts G3)

| # | Trigger | Detection |
|---|---|---|
| 1 | Confirmed tenant-isolation defect on any of the 8 RLS-protected tables | Cross-tenant fuzz failure (`tests/supabase/cross-tenant-fuzz.test.js`) or in-production cross-tenant read |
| 2 | Confirmed privilege-escalation defect in `api/_lib/authz.mjs` or `src/lib/rbac.js` | New authz test failure; manual finding |
| 3 | False-compliant output from any §172.202/.504/.602/.704 or DVIR builder | Compliance Engine test failure; manual finding |
| 4 | Unresolved secret exposure (gitleaks failing on working tree or main) | `secrets-scan` CI job failure; `scripts/check-secrets.mjs` failure |
| 5 | Pilot-demo golden-path break identified by the Pilot Readiness Judge (`docs/agents/05`) | Judge's report |
| 6 | Non-reproducible build (implicit env-var assumption) | Build failure with no documented new env var; or successful local build that fails on Vercel preview |
| 7 | Legal / compliance overclaim on a public surface | Claims substantiation review failure per `governance/11` |
| 8 | Fatal production-path instability (Sentry-detected new error class after G3) | Sentry alert (once `VITE_SENTRY_DSN` is set) or owner-reported |
| 9 | An open P0 in `docs/inventory/blockers-final.md` that affects the demo path | Cross-reference at G4 |

## Pilot-week 24h freeze

In the 24 hours before any scheduled pilot demo, no governance-doc
changes or content commits land on the demo branch except for
security-relevant safety updates explicitly approved by the owner.
This is restated in `PUBLISH.md` "Pilot-week freeze (24-hour rule)".

## Safety budget

The AEO does not enforce a numeric error budget today (no live
Sentry telemetry until `sentry-dsn` is wired). Once Sentry lands,
the SRE / Reliability Agent (`docs/agents/05`) defines per-surface
budgets — initial proposal:

| Surface | Proposed budget | Source |
|---|---|---|
| Auth (sign-in, callback) | 99.9% | derived from acceptable user-facing friction |
| OCR pipeline | 99% | OCR is best-effort by design |
| Regulator-facing builders | 99.95% | regulator-facing PDF integrity is RC3 |
| Audit chain integrity | 100% (no budget) | tamper-evidence is non-negotiable |
| `/Billing` | 99.9% | revenue-adjacent |

Budgets are advisory until Sentry is live and ratified by the owner.

## Release-freeze procedure

1. Risk Controller declares the freeze in the next session-active
   message and writes a Freeze Note under `docs/research/retros/`.
2. The Freeze Note states: trigger, affected surface, expected
   resolution path, rollback commands if already published.
3. No new G3 publish work proceeds until the trigger is resolved.
4. RC0/RC1/RC2 work that is **unrelated** to the freeze trigger
   may continue at the owner's discretion — explicitly noted in
   the Freeze Note.
5. Freeze lifts when the Postmortem / Lessons Agent
   (`docs/agents/09`) records a closure note linked from the
   Freeze Note.

## Pilot-safe change principles (restated for ease)

For any change committed in the week leading up to a pilot demo:

1. Default to documentation, templates, skills, workflows; avoid
   runtime / product-code changes unless the change directly
   unblocks the demo.
2. Default to additive schema, additive doc sections, additive
   flag-registry entries.
3. Default to RC0/RC1.
4. Preserve the existing CI gate's green status (currently 727/727
   vitest).

## Anti-patterns

- Calling a freeze for cosmetic test churn — freezes are reserved
  for the 9 triggers above.
- Overriding a freeze "because the demo is tomorrow" — the demo
  itself is the strongest reason to honor the freeze.
- Letting a freeze sit indefinitely. Every freeze has a target
  resolution path documented in the Freeze Note.
