// ============================================================================
// Entitlement + quota helpers for metered lanes (shared by the gateway relay
// and, later, the billing endpoints).
//
// Reads/writes go through PostgREST with the SERVER-ONLY service-role key
// (process.env, never VITE_-prefixed). Policy:
//   * tier comes from `subscriptions` (webhook-written); absent row => free.
//   * quota is a per-UTC-day event count in `usage_events` per (user, kind).
//   * limits are env-tunable so pricing changes don't need a deploy:
//       AGENT_CHAT_DAILY_FREE (default 20), AGENT_CHAT_DAILY_PRO (default 400)
//   * RELAY_AGENT_REQUIRES_PRO=1 flips the agent lane to paid-only (the
//     "commerce second" switch — default OFF: any signed-in user, quota'd).
//
// Fail-closed on the metered lane: if the quota store is unreachable the
// caller gets a 503-style refusal rather than free unmetered compute.
// ============================================================================

declare const process: { env?: Record<string, string | undefined> } | undefined;

function envVar(name: string): string {
  return (typeof process !== 'undefined' && process.env && process.env[name]) || '';
}

function supabaseUrl(): string {
  return envVar('SUPABASE_URL').replace(/\/$/, '');
}

function serviceRoleKey(): string {
  return envVar('SUPABASE_SERVICE_ROLE_KEY') || envVar('SUPABASE_SERVICE_KEY');
}

function intEnv(name: string, fallback: number): number {
  const n = parseInt(envVar(name), 10);
  return Number.isFinite(n) && n >= 0 ? n : fallback;
}

export interface Entitlement {
  tier: 'free' | 'pro';
  status: string;
  active: boolean;
}

export interface QuotaResult {
  ok: boolean;
  /** Set when ok=false. */
  reason?: 'quota_exceeded' | 'store_unavailable';
  used?: number;
  limit?: number;
}

/** True when the agent lane is configured as paid-only (Phase 5 switch). */
export function agentLaneRequiresPro(): boolean {
  return /^(1|true|yes|on)$/i.test(envVar('RELAY_AGENT_REQUIRES_PRO'));
}

/** Daily agent-chat quota for a tier. */
export function agentChatDailyLimit(tier: 'free' | 'pro'): number {
  return tier === 'pro'
    ? intEnv('AGENT_CHAT_DAILY_PRO', 400)
    : intEnv('AGENT_CHAT_DAILY_FREE', 20);
}

/**
 * Read the account's entitlement. Absent/errored rows resolve to the free
 * tier (never throws) — the quota layer still applies.
 */
export async function getEntitlement(accountId: string): Promise<Entitlement> {
  const base = supabaseUrl();
  const svc = serviceRoleKey();
  const fallback: Entitlement = { tier: 'free', status: 'inactive', active: false };
  if (!base || !svc || !accountId) return fallback;
  try {
    const q = new URL(`${base}/rest/v1/subscriptions`);
    q.searchParams.set('user_id', `eq.${accountId}`);
    q.searchParams.set('select', 'tier,status,current_period_end');
    q.searchParams.set('limit', '1');
    const res = await fetch(q.toString(), {
      headers: { apikey: svc, Authorization: `Bearer ${svc}`, Accept: 'application/json' },
    });
    if (!res.ok) return fallback;
    const rows = (await res.json()) as Array<{
      tier?: string;
      status?: string;
      current_period_end?: string;
    }>;
    const row = Array.isArray(rows) ? rows[0] : undefined;
    if (!row) return fallback;
    const tier = row.tier === 'pro' ? 'pro' : 'free';
    const status = row.status || 'inactive';
    const periodOk =
      !row.current_period_end || new Date(row.current_period_end).getTime() > Date.now();
    const active = (status === 'active' || status === 'trialing') && periodOk;
    return { tier: active ? tier : 'free', status, active };
  } catch {
    return fallback;
  }
}

/**
 * Count-then-insert daily quota check for one metered call.
 *
 * Not transactional — a burst can slightly overshoot the limit, which is
 * acceptable for abuse control (the hard backstop is the per-IP rate limiter
 * in api/_ratelimit.ts). Fails CLOSED when the store is unreachable.
 */
export async function checkAndCountQuota(
  accountId: string,
  kind: string,
  limit: number,
): Promise<QuotaResult> {
  const base = supabaseUrl();
  const svc = serviceRoleKey();
  if (!base || !svc) return { ok: false, reason: 'store_unavailable' };

  const dayStart = new Date();
  dayStart.setUTCHours(0, 0, 0, 0);

  try {
    // Count today's events for this (user, kind) with a HEAD + count header.
    const q = new URL(`${base}/rest/v1/usage_events`);
    q.searchParams.set('user_id', `eq.${accountId}`);
    q.searchParams.set('kind', `eq.${kind}`);
    q.searchParams.set('created_at', `gte.${dayStart.toISOString()}`);
    q.searchParams.set('select', 'id');
    const countRes = await fetch(q.toString(), {
      method: 'HEAD',
      headers: {
        apikey: svc,
        Authorization: `Bearer ${svc}`,
        Prefer: 'count=exact',
      },
    });
    if (!countRes.ok) return { ok: false, reason: 'store_unavailable' };
    const range = countRes.headers.get('content-range') || '';
    const used = parseInt(range.split('/')[1] || '0', 10) || 0;
    if (used >= limit) {
      return { ok: false, reason: 'quota_exceeded', used, limit };
    }

    // Record this call.
    const ins = await fetch(`${base}/rest/v1/usage_events`, {
      method: 'POST',
      headers: {
        apikey: svc,
        Authorization: `Bearer ${svc}`,
        'Content-Type': 'application/json',
        Prefer: 'return=minimal',
      },
      body: JSON.stringify({ user_id: accountId, kind }),
    });
    if (!ins.ok) return { ok: false, reason: 'store_unavailable' };
    return { ok: true, used: used + 1, limit };
  } catch {
    return { ok: false, reason: 'store_unavailable' };
  }
}
