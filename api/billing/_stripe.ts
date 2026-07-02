// ============================================================================
// Shared Stripe helpers (dependency-free: Stripe REST over fetch, form-encoded,
// no SDK — matching the repo's Edge-function style). Secrets are read from
// process.env only; never VITE_-prefixed, never sent to the browser.
//
// Nothing here fails the build when Stripe env is unset — callers check
// billingConfigured() and answer 501 honestly, so the site works commerce-off.
// ============================================================================

declare const process: { env?: Record<string, string | undefined> } | undefined;

export function envVar(name: string): string {
  return (typeof process !== 'undefined' && process.env && process.env[name]) || '';
}

export function stripeSecretKey(): string {
  return envVar('STRIPE_SECRET_KEY');
}

export function billingConfigured(): boolean {
  return !!(stripeSecretKey() && envVar('STRIPE_PRICE_PRO_MONTHLY'));
}

export function supabaseUrl(): string {
  return envVar('SUPABASE_URL').replace(/\/$/, '');
}

export function serviceRoleKey(): string {
  return envVar('SUPABASE_SERVICE_ROLE_KEY') || envVar('SUPABASE_SERVICE_KEY');
}

/** Map a Stripe price id back to a tier via env. Unknown → 'free'. */
export function tierForPrice(priceId: string): 'free' | 'pro' {
  const pro = [envVar('STRIPE_PRICE_PRO_MONTHLY'), envVar('STRIPE_PRICE_PRO_YEARLY')].filter(Boolean);
  return pro.includes(priceId) ? 'pro' : 'free';
}

export function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

/** Bearer token from an incoming request's Authorization header. */
export function bearerFromRequest(req: Request): string {
  const h = req.headers.get('authorization') || req.headers.get('Authorization') || '';
  const m = /^Bearer\s+(.+)$/i.exec(h.trim());
  return m ? m[1].trim() : '';
}

/** Verify a Supabase session JWT → account id ('' when invalid/unset). */
export async function verifyAccount(accessToken: string): Promise<string> {
  const base = supabaseUrl();
  const svc = serviceRoleKey();
  if (!base || !svc || !accessToken) return '';
  try {
    const res = await fetch(`${base}/auth/v1/user`, {
      headers: { apikey: svc, Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) return '';
    const body = (await res.json()) as { id?: string; email?: string };
    return body?.id || '';
  } catch {
    return '';
  }
}

/** Call the Stripe REST API form-encoded. Returns parsed JSON (or throws). */
export async function stripe(
  path: string,
  params: Record<string, string> = {},
  method: 'POST' | 'GET' = 'POST',
): Promise<any> {
  const body = new URLSearchParams(params).toString();
  const url = `https://api.stripe.com/v1/${path}${method === 'GET' && body ? `?${body}` : ''}`;
  const res = await fetch(url, {
    method,
    headers: {
      Authorization: `Bearer ${stripeSecretKey()}`,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: method === 'POST' ? body : undefined,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.error?.message || `Stripe ${res.status}`);
  }
  return data;
}

/**
 * Get the account's Stripe customer id from `profiles`, creating a Stripe
 * customer (and persisting the id) on first use. Idempotent per account.
 */
export async function ensureCustomer(accountId: string, email: string): Promise<string> {
  const base = supabaseUrl();
  const svc = serviceRoleKey();

  // Read existing mapping.
  const q = new URL(`${base}/rest/v1/profiles`);
  q.searchParams.set('user_id', `eq.${accountId}`);
  q.searchParams.set('select', 'stripe_customer_id');
  q.searchParams.set('limit', '1');
  const read = await fetch(q.toString(), {
    headers: { apikey: svc, Authorization: `Bearer ${svc}`, Accept: 'application/json' },
  });
  if (read.ok) {
    const rows = (await read.json()) as Array<{ stripe_customer_id?: string }>;
    const existing = rows?.[0]?.stripe_customer_id;
    if (existing) return existing;
  }

  // Create the Stripe customer and persist the mapping (upsert on user_id).
  const customer = await stripe('customers', {
    ...(email ? { email } : {}),
    'metadata[account_id]': accountId,
  });
  await fetch(`${base}/rest/v1/profiles`, {
    method: 'POST',
    headers: {
      apikey: svc,
      Authorization: `Bearer ${svc}`,
      'Content-Type': 'application/json',
      Prefer: 'resolution=merge-duplicates,return=minimal',
    },
    body: JSON.stringify({
      user_id: accountId,
      email: email || null,
      stripe_customer_id: customer.id,
      updated_at: new Date().toISOString(),
    }),
  });
  return customer.id;
}

/** Base origin for success/cancel/return URLs. */
export function siteOrigin(req: Request): string {
  const configured = envVar('SITE_ORIGIN');
  if (configured) return configured.replace(/\/$/, '');
  try {
    return new URL(req.url).origin;
  } catch {
    return 'https://musehq.io';
  }
}
