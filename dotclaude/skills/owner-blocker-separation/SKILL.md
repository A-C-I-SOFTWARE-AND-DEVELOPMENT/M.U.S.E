---
name: owner-blocker-separation
description: Separate what Claude can fix in code from what the owner must do in external services (Play Console, App Store, Vercel, Supabase, DNS, Stripe, domains, legal). Use at the end of any audit or implementation so the owner has one short to-do list of human-only actions.
---

# Owner-Blocker Separation

## Use when

- Closing an audit, implementation, or launch check.
- Anytime an action requires a human dashboard, credential, or decision.

## Buckets

### Code-side (Claude can fix)

- Source changes, tests, types, lint.
- Build scripts, CI config (if files are in the repo).
- README, in-repo docs, prompts, agent definitions.
- Migrations and seed scripts (Claude writes; owner runs in prod).

### Owner-only (Claude cannot fix)

- **Play Console** — store listing, internal testing track, signing key,
  data safety form, content rating.
- **App Store Connect** — TestFlight, capabilities, export compliance,
  privacy declarations.
- **Vercel / Netlify / Cloudflare** — env vars in the dashboard, domain
  binding, build env, edge config not in repo.
- **Supabase / Firebase** — env-level config, project settings, billing
  tier, RLS policies if applied via dashboard rather than migration.
- **DNS / domain registrar** — records, transfers, renewals.
- **Stripe / billing** — products, prices, webhook endpoints, tax
  settings, payout config.
- **Legal** — privacy policy, terms, DPAs, ToS, cookie banner copy.
- **Identity** — Google / Apple sign-in console config, OAuth client
  registration.
- **Email / support** — DMARC/SPF/DKIM, support inbox routing.
- **Decisions** — pricing, naming, scope, launch date, anything
  irreversible.

## Procedure

1. Walk the audit / implementation report.
2. Place each remaining action in one bucket or the other.
3. For owner-only items, include: where (dashboard URL or path), what,
   why it matters, how the owner verifies done.

## Output

```
## Mission
## Code-side blockers (Claude can fix)
1. <severity> <title> — <file or surface> — <action>
...

## Owner-only blockers (you must do these)
1. <where> — <what> — <why> — <how to verify done>
...

## Sequencing
- Do owner-only items in this order to unblock the most: ...
- Do code-side items in this order: ...

## Single next action
<one sentence>
```

## Hard rules

- Never claim Claude can do something requiring a human dashboard or
  legal authority.
- Never bury an owner-only item inside a code-side action.
- Every owner-only item has a "how to verify done" so the owner knows
  when it's truly off the list.
