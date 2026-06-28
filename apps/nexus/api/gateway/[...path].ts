// ============================================================================
// Edge relay: /api/gateway/<rest...>  ->  the authenticated account's OWN stored
// MUSE gateway HTTPS base, authenticated with that account's per-account bearer
// applied SERVER-SIDE.
//
// Why this exists: a hosted https NEXUS cannot talk to a user's http://localhost
// gateway (mixed content), and we never want the per-account gateway bearer to
// live in the browser. This relay lets a hosted device reach the user's gateway
// (when the user has exposed it over HTTPS) using a binding that is resolved and
// authenticated entirely server-side.
//
// SECURITY — the whole point of this file:
//   • The client NEVER supplies a target URL. The destination base is read from
//     the account's stored `account_gateways.gateway_url` (server-side only).
//     => No SSRF: a caller cannot point the relay at an arbitrary/internal host.
//   • The account is resolved from the caller's Supabase session JWT, verified
//     server-side with the service-role key. The stored bearer is then attached
//     server-side. => No cross-account access: you only ever reach YOUR gateway,
//     and the bearer is never returned to any device in plaintext.
//   • Only GET and POST are forwarded. The path is taken from the URL after
//     `/api/gateway/`; it is constrained to the gateway origin (no absolute
//     URLs, no scheme/host injection, no `..` escape above the gateway root).
//   • The stored base MUST be https (a relay over http would defeat the point
//     and re-introduce mixed-content / interception risk).
//
// Secrets (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) come from process.env only —
// never VITE_-prefixed, never shipped to the browser. When unset, the relay and
// /api/me honestly answer 501 so the client falls back to the direct local path.
//
// Compiles when Supabase / env are unset: process.env is read through a guarded
// ambient declaration, so there is no build-time dependency on any env var.
// ============================================================================

export const config = { runtime: 'edge' };

// Guarded ambient declaration for the server-only secret source. Mirrors
// api/_providers.ts so we never depend on @types/node. Secrets are read here and
// never exposed to the browser; never VITE_-prefixed.
declare const process: { env?: Record<string, string | undefined> } | undefined;

function envVar(name: string): string {
  return (typeof process !== 'undefined' && process.env && process.env[name]) || '';
}

function supabaseUrl(): string {
  return envVar('SUPABASE_URL').replace(/\/$/, '');
}

function serviceRoleKey(): string {
  // Accept either canonical name; both are server-only.
  return envVar('SUPABASE_SERVICE_ROLE_KEY') || envVar('SUPABASE_SERVICE_KEY');
}

/** True when the server has the Supabase wiring needed to run the relay at all. */
export function gatewayRelayConfigured(): boolean {
  return !!(supabaseUrl() && serviceRoleKey());
}

/** Extract a bearer token from an incoming request's Authorization header. */
export function bearerFromRequest(req: Request): string {
  const h = req.headers.get('authorization') || req.headers.get('Authorization') || '';
  const m = /^Bearer\s+(.+)$/i.exec(h.trim());
  return m ? m[1].trim() : '';
}

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

export interface AccountGateway {
  ok: boolean;
  /** 'unauthenticated' (bad/expired JWT) vs 'unbound' (authed, no gateway row). */
  reason?: 'unauthenticated' | 'unbound' | 'unconfigured';
  accountId?: string;
  gatewayUrl?: string;
  /** The per-account gateway bearer. SERVER-SIDE ONLY — never serialize this. */
  gatewayToken?: string;
}

/**
 * Resolve the caller's account and its stored gateway binding, server-side.
 *
 *   1. Verify the caller's Supabase session JWT via the Auth API using the
 *      service-role key -> trusted account id.
 *   2. Read that account's single `account_gateways` row (service-role, so RLS
 *      is bypassed deliberately and the lookup is scoped by user_id == account).
 *
 * Returns ok:false with a reason for every honest failure (never throws to the
 * relay; the relay maps reasons to status codes).
 */
export async function resolveAccountGateway(accessToken: string): Promise<AccountGateway> {
  if (!gatewayRelayConfigured()) return { ok: false, reason: 'unconfigured' };
  if (!accessToken) return { ok: false, reason: 'unauthenticated' };

  const base = supabaseUrl();
  const svc = serviceRoleKey();

  // 1) Verify the JWT and obtain the account id. The user's own access token is
  //    sent as the bearer; the service-role key is the apikey. A 200 with an id
  //    means the token is valid and identifies the account.
  let accountId = '';
  try {
    const u = await fetch(`${base}/auth/v1/user`, {
      headers: { apikey: svc, Authorization: `Bearer ${accessToken}` },
    });
    if (!u.ok) return { ok: false, reason: 'unauthenticated' };
    const body = (await u.json()) as { id?: string };
    if (!body?.id) return { ok: false, reason: 'unauthenticated' };
    accountId = body.id;
  } catch {
    return { ok: false, reason: 'unauthenticated' };
  }

  // 2) Look up this account's stored gateway binding (service-role read).
  try {
    const q = new URL(`${base}/rest/v1/account_gateways`);
    q.searchParams.set('user_id', `eq.${accountId}`);
    q.searchParams.set('select', 'gateway_url,gateway_token');
    q.searchParams.set('limit', '1');
    const res = await fetch(q.toString(), {
      headers: { apikey: svc, Authorization: `Bearer ${svc}`, Accept: 'application/json' },
    });
    if (!res.ok) return { ok: false, reason: 'unbound', accountId };
    const rows = (await res.json()) as Array<{ gateway_url?: string; gateway_token?: string }>;
    const row = Array.isArray(rows) ? rows[0] : undefined;
    const gatewayUrl = (row?.gateway_url || '').trim().replace(/\/$/, '');
    const gatewayToken = (row?.gateway_token || '').trim();
    if (!gatewayUrl) return { ok: false, reason: 'unbound', accountId };
    // Hard requirement: the stored base must be https (no http relay target).
    if (!/^https:\/\//i.test(gatewayUrl)) return { ok: false, reason: 'unbound', accountId };
    return { ok: true, accountId, gatewayUrl, gatewayToken };
  } catch {
    return { ok: false, reason: 'unbound', accountId };
  }
}

/**
 * Derive the gateway-relative path (+ query) from the incoming relay URL.
 * Everything after `/api/gateway/` becomes the path appended to the stored
 * gateway base. We rebuild from URL parts (no client-supplied absolute URL is
 * ever honored) and refuse any `..` segment so a caller can't climb out of the
 * gateway root.
 */
function gatewayPathFrom(reqUrl: string): { ok: true; path: string } | { ok: false } {
  const u = new URL(reqUrl);
  const marker = '/api/gateway/';
  const i = u.pathname.indexOf(marker);
  if (i === -1) return { ok: false };
  let rest = u.pathname.slice(i + marker.length);
  // Reject path traversal / scheme injection attempts outright.
  if (rest.includes('..') || rest.includes('://')) return { ok: false };
  rest = rest.replace(/^\/+/, '');
  const path = `/${rest}${u.search}`;
  return { ok: true, path };
}

export default async function handler(req: Request): Promise<Response> {
  // Only GET and POST are relayed.
  if (req.method !== 'GET' && req.method !== 'POST') {
    return json({ error: 'method not allowed' }, 405);
  }

  if (!gatewayRelayConfigured()) {
    return json({ error: 'gateway relay not configured' }, 501);
  }

  const accessToken = bearerFromRequest(req);
  if (!accessToken) {
    return json({ error: 'authentication required' }, 401);
  }

  const account = await resolveAccountGateway(accessToken);
  if (!account.ok) {
    if (account.reason === 'unauthenticated') {
      return json({ error: 'authentication required' }, 401);
    }
    if (account.reason === 'unconfigured') {
      return json({ error: 'gateway relay not configured' }, 501);
    }
    return json({ error: 'no gateway connected for this account' }, 409);
  }

  const parsed = gatewayPathFrom(req.url);
  if (!parsed.ok) {
    return json({ error: 'invalid relay path' }, 400);
  }

  // Build the upstream URL from the STORED base only — the client never gets to
  // name the host. The bearer is attached server-side and never echoed back.
  const target = `${account.gatewayUrl}${parsed.path}`;

  const headers: Record<string, string> = { Accept: 'application/json' };
  if (account.gatewayToken) headers.Authorization = `Bearer ${account.gatewayToken}`;

  let body: string | undefined;
  if (req.method === 'POST') {
    const ct = req.headers.get('content-type');
    headers['Content-Type'] = ct || 'application/json';
    try {
      body = await req.text();
    } catch {
      body = undefined;
    }
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body,
      redirect: 'manual', // never auto-follow a redirect off the gateway origin
    });
  } catch (e) {
    return json({ error: `gateway unreachable: ${(e as Error).message}` }, 502);
  }

  // Pass the upstream body through, but strip hop-by-hop / auth-bearing headers
  // and only surface a safe content type. Never leak Set-Cookie or upstream auth.
  const respHeaders: Record<string, string> = {
    'Content-Type': upstream.headers.get('content-type') || 'application/json',
    'Cache-Control': 'no-store',
  };
  return new Response(upstream.body, { status: upstream.status, headers: respHeaders });
}
