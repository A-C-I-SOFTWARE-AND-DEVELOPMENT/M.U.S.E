-- ============================================================================
-- musehq.io billing (migration 0002) — Stripe idempotency ledger.
--
-- The subscriptions + profiles.stripe_customer_id columns already exist
-- (migration 0001). This adds the event ledger the webhook uses to process
-- each Stripe event exactly once (Stripe may redeliver an event, and the
-- webhook is the only writer of subscription state).
-- ============================================================================

create table if not exists public.stripe_events (
  id            text primary key,          -- Stripe event id (evt_...)
  type          text not null,
  processed_at  timestamptz not null default now()
);

alter table public.stripe_events enable row level security;
-- No anon-path policies: only the webhook (service role) reads/writes this.
