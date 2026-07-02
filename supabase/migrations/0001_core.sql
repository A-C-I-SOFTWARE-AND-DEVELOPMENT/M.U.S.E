-- ============================================================================
-- musehq.io hosted-product core schema (migration 0001)
--
-- Backs the Vercel Edge functions that power the public cockpit:
--   * api/me.ts + api/gateway/[...path].ts  -> account_gateways
--   * api/gateway-binding.ts                -> account_gateways (upsert/delete)
--   * api/_entitlements.ts                  -> subscriptions + usage_events
--   * apps/nexus push notifications         -> push_subscriptions
--
-- Security model: every table carries RLS. Users can read (and where sensible,
-- write) ONLY their own rows via the anon-key PostgREST path. The Edge
-- functions use the service-role key (bypasses RLS) for verified server-side
-- reads/writes — most importantly `account_gateways.gateway_token`, which must
-- never be readable through the anon path at all (the browser transits it
-- exactly once at bind time, over HTTPS, to api/gateway-binding.ts).
--
-- `subscriptions` and `usage_events` are written EXCLUSIVELY by the service
-- role (Stripe webhook / relay quota accounting); users get read-only
-- visibility into their own rows.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- profiles: one row per auth user (created lazily by the billing layer).
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
  user_id            uuid primary key references auth.users (id) on delete cascade,
  email              text,
  display_name       text,
  stripe_customer_id text unique,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

alter table public.profiles enable row level security;

drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own" on public.profiles
  for select using (auth.uid() = user_id);

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own" on public.profiles
  for update using (auth.uid() = user_id)
  with check (auth.uid() = user_id and stripe_customer_id is not distinct from stripe_customer_id);

-- Inserts/deletes and stripe_customer_id writes happen via the service role.

-- ---------------------------------------------------------------------------
-- account_gateways: the account's own MUSE gateway binding (relay target).
-- gateway_token is the per-account gateway bearer — service-role access only;
-- NO select policy exists for the anon path on purpose.
-- ---------------------------------------------------------------------------
create table if not exists public.account_gateways (
  user_id       uuid primary key references auth.users (id) on delete cascade,
  gateway_url   text not null check (gateway_url like 'https://%'),
  gateway_token text not null,
  updated_at    timestamptz not null default now()
);

alter table public.account_gateways enable row level security;
-- No anon-path policies at all: reads AND writes go through the Edge functions
-- (service role) so the bearer never becomes anon-readable. api/me.ts returns
-- only non-sensitive fields.

-- ---------------------------------------------------------------------------
-- subscriptions: entitlement state, written by the Stripe webhook only.
-- ---------------------------------------------------------------------------
create table if not exists public.subscriptions (
  user_id                uuid primary key references auth.users (id) on delete cascade,
  stripe_subscription_id text unique,
  price_id               text,
  tier                   text not null default 'free' check (tier in ('free', 'pro')),
  status                 text not null default 'inactive'
                         check (status in ('active', 'trialing', 'past_due', 'canceled', 'inactive')),
  current_period_end     timestamptz,
  updated_at             timestamptz not null default now()
);

alter table public.subscriptions enable row level security;

drop policy if exists "subscriptions_select_own" on public.subscriptions;
create policy "subscriptions_select_own" on public.subscriptions
  for select using (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- usage_events: quota accounting for metered lanes (agent chat via the relay).
-- Service-role writes only; users may read their own history.
-- ---------------------------------------------------------------------------
create table if not exists public.usage_events (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references auth.users (id) on delete cascade,
  kind       text not null,
  created_at timestamptz not null default now()
);

create index if not exists usage_events_user_recent
  on public.usage_events (user_id, kind, created_at desc);

alter table public.usage_events enable row level security;

drop policy if exists "usage_events_select_own" on public.usage_events;
create policy "usage_events_select_own" on public.usage_events
  for select using (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- push_subscriptions: web-push endpoints registered by the NEXUS PWA.
-- Users manage their own rows directly (anon path with RLS).
-- ---------------------------------------------------------------------------
create table if not exists public.push_subscriptions (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references auth.users (id) on delete cascade,
  endpoint   text not null unique,
  p256dh     text,
  auth       text,
  created_at timestamptz not null default now()
);

alter table public.push_subscriptions enable row level security;

drop policy if exists "push_subscriptions_all_own" on public.push_subscriptions;
create policy "push_subscriptions_all_own" on public.push_subscriptions
  for all using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
