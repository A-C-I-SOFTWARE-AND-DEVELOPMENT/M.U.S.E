# 10 — Feature Flag and Beta Gate Registry

**Status:** Installed 2026-05-17

A single registry for every feature flag, beta gate, env-flag
swap, and procurement-blocked surface. Each entry tracks default
state, customer exposure, owner, verification status, and exit
criteria. This registry is the source of truth for what is
"enabled" vs. "stubbed" today.

## Schema

For every entry:

- **Name** — env var or flag identifier
- **Default state** — what happens when the value is unset
- **Environment behavior** — what each value produces
- **Dependency owner** — vendor or division responsible for the
  value
- **Customer exposure** — visible to whom and how
- **Kill switch** — how to force off in production
- **Verification status** — tested? in CI? manually verified?
- **Exit criteria** — what removes this entry from the registry

## Registry — current HazMat Command flags

### `VITE_BILLING_ENABLED`

- **Default state:** `false`
- **Environment behavior:**
  - unset / `false` — `/api/square/create-subscription` (and any
    future Stripe equivalent) returns 503 "beta"; `/Billing` shows
    pricing cards but the upgrade button is a no-op
  - `true` — billing flow live (still requires the active provider's
    env vars: Square `SQUARE_ACCESS_TOKEN` for Path A or Stripe
    `STRIPE_SECRET_KEY` for Path B per ADR-0002)
- **Dependency owner:** `@echerd27-design`
- **Customer exposure:** visible — "demo mode" banner on
  `/Billing` until flipped
- **Kill switch:** unset `VITE_BILLING_ENABLED` in Vercel env
- **Verification status:** unit-tested; gated 503 documented
  in `tests/api/square/create-subscription.test.js`. Provider-
  abstracted billing flag also exercised in
  `tests/api/_lib/billingProvider.test.js`.
- **Exit criteria:** flip `true` after the active provider's real
  credentials are configured and the corresponding stub
  (`square-payments-real-credentials` for Path A or
  `stripe-via-base44-credentials` for Path B) is closed

### `VITE_BILLING_PROVIDER`

- **Default state:** unset → resolves to `square` (back-compat
  default per ADR-0002).
- **Environment behavior:**
  - unset / empty / `square` — `api/_lib/billingProvider.mjs`
    returns the Square adapter (existing
    `api/_lib/square.mjs` + `api/_lib/squareStub.mjs` surface)
  - `stripe` — returns the Stripe-via-Base44 adapter
    (`api/_lib/stripeAdapter.mjs` +
    `api/_lib/stripeAdapterStub.mjs`)
  - `none` — explicit "no provider"; Billing page falls back to
    the demo banner regardless of `VITE_BILLING_ENABLED`
  - Any other value throws `UnknownBillingProviderError` at
    resolution time (fail-loud on typos)
- **Dependency owner:** Engineering & Architecture Factory (factory
  shape); `@echerd27-design` (env value selection)
- **Customer exposure:** transparent — the abstraction is invisible
  to the operator
- **Kill switch:** unset `VITE_BILLING_PROVIDER` (defaults to
  `square`), or set `VITE_BILLING_ENABLED=false` to force demo
  banner regardless of provider
- **Verification status:** factory + each adapter shape exercised
  in `tests/api/_lib/billingProvider.test.js`; Stripe stub branch
  exercised in `tests/api/_lib/stripeAdapterStub.test.js`
- **Exit criteria:** Square deprecation PR (ADR-0002 Migration
  Path step 4) lands and removes the `square` branch from the
  factory; this entry then collapses to "Stripe-only" mode and the
  flag becomes a no-op (left in place for one further release as a
  rollback hatch, then removed)

### Stripe-via-Base44 envs (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_WEBHOOK_TOLERANCE_SEC`, 6 `STRIPE_PRICE_*`, `VITE_STRIPE_PUBLISHABLE_KEY`)

- **Default state:** unset → `isStripeStubActive()` returns `true`;
  deterministic stub responses for every documented Stripe REST
  endpoint the adapter calls
- **Environment behavior:** `STRIPE_SECRET_KEY` truthy → `stripeFetch`
  hits real `api.stripe.com` with bearer auth (no `Stripe-Version`
  header is sent, so the account default version applies);
  `verifyStripeSignature` enforces real `t=…,v1=…` HMAC against
  `STRIPE_WEBHOOK_SECRET` AND rejects signatures whose `t=` is
  outside the tolerance window (default 300s, overridable via
  `STRIPE_WEBHOOK_TOLERANCE_SEC`). Multiple `v1=` entries in a
  single header are honored to support webhook-secret rotation
  windows.
- **Dependency owner:** `@echerd27-design` (Stripe Developer
  account + Base44 builder Stripe-integration wiring)
- **Customer exposure:** none until `VITE_BILLING_PROVIDER=stripe`
  is set AND the Stripe-aware route lands in the cutover PR
- **Kill switch:** unset `STRIPE_SECRET_KEY` (stub takes over); or
  flip `VITE_BILLING_PROVIDER=square` to switch providers entirely
- **Verification status:** `tests/api/_lib/stripeAdapterStub.test.js`
  covers every dispatcher branch, the activation toggle, the
  webhook-signature verifier (including stale-timestamp rejection,
  multiple-`v1=` rotation acceptance, non-numeric-`t=` rejection),
  and `tests/api/_lib/billingProvider.test.js` covers the
  real-mode `stripeReady()` discipline that requires every
  `STRIPE_PRICE_*` env to be set before reporting ready
- **Exit criteria:** closes `stripe-via-base44-credentials` stub
  per the owner runbook at
  `docs/readiness/owner-action-packets/stripe-via-base44-procurement.md`

### `MFA_ENFORCEMENT`

- **Default state:** unset → permissive
- **Environment behavior:**
  - unset / `off` — `requireMfa('totp')` passes
  - `on` — 403 with `code=mfa_required` for compliance_officer
    role without an enrolled MFA factor
- **Dependency owner:** Security/Authz Engineer (Engineering
  Factory)
- **Customer exposure:** transparent until enabled
- **Kill switch:** set `MFA_ENFORCEMENT=off`
- **Verification status:** authz middleware unit-tested both
  branches
- **Exit criteria:** `workos-procurement` + `webauthn-platform-
  config` cleared; enrollment UI live; `MFA_ENFORCEMENT=on` in
  production

### `VITE_BASE44_APP_ID` and mode dispatch

- **Default state:** unset → local IndexedDB mode
- **Environment behavior:**
  - unset OR `?demo=true` OR `localStorage.hazmat_force_local==='1'`
    → local
  - set AND (token in URL OR host is `*.base44.*` OR
    `VITE_BASE44_APP_BASE_URL` set) → cloud
- **Dependency owner:** `@echerd27-design` (Base44 + Vercel)
- **Customer exposure:** affects every page boot
- **Kill switch:** set `localStorage.hazmat_force_local='1'` in
  browser
- **Verification status:** dispatcher in `src/api/base44Client.js`;
  tested in `tests/api/base44Client.test.js` (when present)
- **Exit criteria:** `VITE_BASE44_APP_BASE_URL` set on Vercel
  production; cloud mode activates everywhere outside the local
  forces

### `VITE_SENTRY_DSN` + `SENTRY_DSN`

- **Default state:** unset → SDK is a no-op
- **Environment behavior:** when both are set, browser SDK +
  server SDK load lazily; structured logs propagate request-id
- **Dependency owner:** `@echerd27-design` (Sentry account)
- **Customer exposure:** none directly; failure telemetry to
  internal Sentry only
- **Kill switch:** unset both env vars
- **Verification status:** lazy init unit-tested with synthetic
  fallbacks; PII scrubber unit-tested
- **Exit criteria:** Sentry project provisioned; closes
  `sentry-dsn` stub

### `SQUARE_ACCESS_TOKEN` (+ 8 related Square env vars)

- **Default state:** unset → `isStubActive()` returns `true`;
  deterministic stub
- **Environment behavior:** truthy → `squareFetch` hits real
  Square REST API; webhook verification real
- **Dependency owner:** `@echerd27-design` (Square Developer)
- **Customer exposure:** demo banner on `/Billing` disappears
- **Kill switch:** unset `SQUARE_ACCESS_TOKEN`
- **Verification status:** `tests/api/_lib/squareStub.test.js`
  covers every dispatcher branch and the activation toggle
- **Exit criteria:** closes `square-payments-real-credentials`
  stub

### `RFC3161_TSA_URL`

- **Default state:** unset → `rfc3161Stub` returns
  `STUB-TSA`-prefixed Buffer
- **Environment behavior:** set → nightly anchor posts real
  ASN.1 `TimeStampReq` to the chosen TSA
- **Dependency owner:** `@echerd27-design` (TSA selection +
  legal review) + Engineering Factory (PKI swap)
- **Customer exposure:** none until `merkle-root-feed` lands
- **Kill switch:** unset `RFC3161_TSA_URL`
- **Verification status:** stub format unit-tested; real-mode
  swap deferred to vendor selection
- **Exit criteria:** TSA vendor chosen; closes
  `rfc3161-tsa-procurement` stub

### `OPENTIMESTAMPS_CALENDAR_URL`

- **Default state:** unset → `openTimestampsStub` returns
  `STUB-OTS`-prefixed Buffer
- **Environment behavior:** set → daily upgrade job calls
  `OpenTimestamps.upgrade(proof)`
- **Dependency owner:** `@echerd27-design` (legal/bundle review
  for `javascript-opentimestamps`) + Engineering Factory
- **Customer exposure:** none until external verifier consumes
  the proof
- **Kill switch:** unset `OPENTIMESTAMPS_CALENDAR_URL`
- **Verification status:** stub format unit-tested
- **Exit criteria:** closes `opentimestamps-calendar` stub

### `SOR_<DOMAIN>_BACKEND` and `SOR_<DOMAIN>_SHADOW_WRITE`

- **Default state:** unset → in-memory / Base44 fallback per
  domain
- **Environment behavior:**
  - `supabase` → adapter targets Supabase (throws cleanly until
    `supabase-project-provisioned`)
  - `legacy` → in-memory / Base44 fallback
  - `SOR_<DOMAIN>_SHADOW_WRITE=on` → wiring planned in
    `sor-shadow-write-wiring` stub
- **Dependency owner:** `@echerd27-design` (Supabase) +
  Data/SoR Migration Engineer
- **Customer exposure:** transparent at the application surface;
  data persistence quality depends on the cut
- **Kill switch:** unset the domain's `SOR_<DOMAIN>_BACKEND`
- **Verification status:** resolver browser-safe; cutover runbook
  + checklist live
- **Exit criteria:** per-domain — each closes its corresponding
  `supabase-*` entry; meta-blocker
  `supabase-project-provisioned` clears the whole class

### WorkOS configuration (`WORKOS_API_KEY`, `WORKOS_CLIENT_ID`,
`WORKOS_JWKS_URL`, `WORKOS_REDIRECT_URI`, `WORKOS_STUB_SECRET`)

- **Default state:** unset → HS256 stub path
- **Environment behavior:** real → SSO flow + JWKS verification
- **Dependency owner:** `@echerd27-design` (WorkOS SOW) +
  Security/Authz Engineer
- **Customer exposure:** SSO start screen URL changes; tenant
  IdP admin behavior unlocks
- **Kill switch:** unset `WORKOS_API_KEY`
- **Verification status:** start → callback → verify flow tested
  in stub mode; RS256 JWKS verifier unit-tested with synthetic
  RSA keys
- **Exit criteria:** closes `workos-procurement` stub; enables
  closure of `mfa-enforcement` and the supabase IdP / SCIM entries

### `S3 Object Lock` (no single env var; bucket + IAM + KMS)

- **Default state:** not provisioned → HMAC signature on export
  bundle; no WORM destination
- **Environment behavior:** once provisioned, nightly anchor PUTs
  `merkle-roots/<tenant>/<day>.json` + `.tst` + `.ots` files
- **Dependency owner:** `@echerd27-design`
- **Customer exposure:** improves third-party audit defensibility
- **Kill switch:** rotate IAM role; revoke `s3:PutObject`
- **Verification status:** Ed25519/HSM-backed signature swap
  unit-tested when implemented
- **Exit criteria:** closes `s3-object-lock` stub

### `certified-translator-engagement` (no env var — content gate)

- **Default state:** `src/i18n/fr.json` marked
  "draft-not-certified" via `$schema-comment`
- **Environment behavior:** renderer accepts `locale: 'fr'`;
  runtime gate refusing regulator-facing PDFs in FR is the
  R4-Q+1 follow-up
- **Dependency owner:** `@echerd27-design` (CTTIC/OTTIAQ/ATIO
  SOW)
- **Customer exposure:** Canadian regulator-facing FR PDFs are
  not certified
- **Kill switch:** `src/i18n/fr.cert-log.md` reports
  `certified: false`
- **Verification status:** `npm run i18n:check` enforces
  structural integrity; cert-log enforcement is the open follow-
  up
- **Exit criteria:** signed translator certification statement
  filed; cert-log marks every regulator-document section
  `certified: true`; runtime gate lands

## How to add an entry

When a new env-flag-driven feature lands, the Engineering Factory
agent that ships it must add an entry here in the same PR. If the
PR omits a registry entry, the Risk Controller (Executive Command)
holds the PR.

## Anti-patterns

- A feature flag with no kill switch.
- A feature flag whose exit criteria is "never".
- A feature flag that promises a capability the underlying stub
  cannot deliver.
- Conflating a feature flag (operator behavior toggle) with a
  procurement-blocked stub (`SKIPPED.md` entry). Many entries
  above are both — that's intentional, but the schemas of
  `SKIPPED.md` and this registry stay separate.
