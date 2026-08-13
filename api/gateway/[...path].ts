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
const MAX_RELAY_BODY_BYTES = 256 * 1024;
const RELAY_TIMEOUT_MS = 30_000;

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

type RelayRoute = { method: 'GET' | 'POST'; pattern: RegExp };

// Owner-session policy preserves the hosted cockpit controls already exposed.
// Secret/export and DELETE surfaces are intentionally absent.
export const OWNER_RELAY_ROUTES: readonly RelayRoute[] = [
  { method: 'GET', pattern: /^\/v1\/health$/ },
  { method: 'POST', pattern: /^\/v1\/cockpit\/pair\/(?:start|confirm)$/ },
  { method: 'POST', pattern: /^\/v1\/cockpit\/service-tokens$/ },
  {
    method: 'GET',
    pattern:
      /^\/v1\/cockpit\/(?:runtime\/(?:status|workers)|diagnostics|axiom|models(?:\/local|\/catalog)?|model-routes|events|trace|audit|capabilities|ledger|jobs(?:\/lanes)?|approvals|channels|schedules|autonomy(?:\/decisions)?|proposals|learning|skills|templates|navigation|second-brain\/status|forge\/leaderboard|federation\/status|council\/dispatch|sessions|seats)$/,
  },
  {
    method: 'GET',
    pattern:
      /^\/v1\/cockpit\/(?:audit\/[^/]+\/proof|ledger\/[^/]+\/[^/]+|jobs\/[^/]+(?:\/(?:ledger|diff|files-changed|validation|tree|file|publish\/preview))?)$/,
  },
  {
    method: 'POST',
    pattern:
      /^\/v1\/cockpit\/(?:model-routes\/override|emergency-stop|jobs|orchestrate|coding\/(?:audit|plan|execute)|research|autonomy)$/,
  },
  {
    method: 'POST',
    pattern:
      /^\/v1\/cockpit\/(?:jobs\/[^/]+\/(?:run|cancel|pause|resume|rerun|approve|validate|revalidate|override|publish)|approvals\/[^/]+|ledger\/[^/]+\/[^/]+\/rollback)$/,
  },
  { method: 'GET', pattern: /^\/v1\/cockpit\/jobs\/stream$/ },
  { method: 'GET', pattern: /^\/v1\/cockpit\/events\/stream$/ },
  { method: 'GET', pattern: /^\/v1\/observatory\/(?:snapshot|metrics|layout|recommendations|stream|actions)$/ },
  { method: 'POST', pattern: /^\/v1\/observatory\/recommendations\/[^/]+\/stage$/ },
  { method: 'POST', pattern: /^\/v1\/agent\/(?:chat|approvals|stop)$/ },
];

// Buzz service-token policy is intentionally narrower and mirrors the local
// cockpit's scope policy. A route absent here cannot be reached through relay.
export const SERVICE_RELAY_ROUTES: readonly RelayRoute[] = [
  { method: 'GET', pattern: /^\/v1\/health$/ },
  { method: 'GET', pattern: /^\/v1\/cockpit\/runtime\/(?:status|workers)$/ },
  { method: 'GET', pattern: /^\/v1\/cockpit\/capabilities$/ },
  { method: 'GET', pattern: /^\/v1\/cockpit\/models\/catalog$/ },
  { method: 'GET', pattern: /^\/v1\/cockpit\/model-routes$/ },
  { method: 'POST', pattern: /^\/v1\/cockpit\/model-routes\/override$/ },
  { method: 'GET', pattern: /^\/v1\/cockpit\/(?:schedules|seats)$/ },
  { method: 'GET', pattern: /^\/v1\/cockpit\/jobs(?:\/lanes|\/stream)?$/ },
  { method: 'POST', pattern: /^\/v1\/cockpit\/jobs$/ },
  {
    method: 'GET',
    pattern:
      /^\/v1\/cockpit\/jobs\/[^/]+(?:\/(?:ledger|diff|files-changed|validation|tree|file))?$/,
  },
  {
    method: 'POST',
    pattern:
      /^\/v1\/cockpit\/jobs\/[^/]+\/(?:run|cancel|pause|resume|rerun|validate|revalidate)$/,
  },
  { method: 'GET', pattern: /^\/v1\/cockpit\/approvals$/ },
  { method: 'POST', pattern: /^\/v1\/cockpit\/approvals\/[^/]+$/ },
  { method: 'POST', pattern: /^\/v1\/cockpit\/emergency-stop$/ },
  { method: 'POST', pattern: /^\/v1\/agent\/stop$/ },
];

export function relayRouteAllowed(
  routes: readonly RelayRoute[],
  method: string,
  pathname: string,
): boolean {
  return routes.some((route) => route.method === method && route.pattern.test(pathname));
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
function gatewayPathFrom(
  reqUrl: string,
): { ok: true; path: string; pathname: string } | { ok: false } {
  const u = new URL(reqUrl);
  const marker = '/api/gateway/';
  const i = u.pathname.indexOf(marker);
  if (i === -1) return { ok: false };
  const rest = u.pathname.slice(i + marker.length).replace(/^\/+/, '');
  const clean: string[] = [];
  for (const encoded of rest.split('/')) {
    let segment = '';
    try {
      segment = decodeURIComponent(encoded);
    } catch {
      return { ok: false };
    }
    if (
      !segment ||
      segment === '.' ||
      segment === '..' ||
      segment.includes('/') ||
      segment.includes('\\') ||
      segment.includes('\0') ||
      segment.includes('://')
    ) {
      return { ok: false };
    }
    clean.push(encodeURIComponent(segment));
  }
  const pathname = `/${clean.join('/')}`;
  return { ok: true, pathname, path: `${pathname}${u.search}` };
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

  const serviceAuthorization = (
    req.headers.get('x-muse-service-authorization') || ''
  ).trim();
  const serviceMatch = /^Bearer\s+(muse_svc_[A-Za-z0-9_-]+)$/i.exec(
    serviceAuthorization,
  );
  if (serviceAuthorization && !serviceMatch) {
    return json({ error: 'invalid service authorization' }, 401);
  }
  const serviceToken = serviceMatch?.[1] || '';
  const routePolicy = serviceToken ? SERVICE_RELAY_ROUTES : OWNER_RELAY_ROUTES;
  if (!relayRouteAllowed(routePolicy, req.method, parsed.pathname)) {
    return json({ error: 'route not available' }, 404);
  }
  const requestId = (req.headers.get('x-muse-request-id') || '').trim();
  if (serviceToken && req.method === 'POST' && !requestId) {
    return json({ error: 'request id required' }, 400);
  }

  // Metered lane: full-agent chat (and its companions) carry entitlement +
  // per-day quota. Other cockpit/observatory paths only require the session +
  // binding above — the user is reaching their own gateway's read surface.
  if (/^\/v1\/agent\//i.test(parsed.path)) {
    const { agentChatDailyLimit, agentLaneRequiresPro, checkAndCountQuota, getEntitlement } =
      await import('../_entitlements');
    const ent = await getEntitlement(account.accountId || '');
    if (agentLaneRequiresPro() && !ent.active) {
      return json(
        { error: 'the full-agent lane requires an active subscription', tier: ent.tier },
        402,
      );
    }
    // Only the chat turn itself consumes quota; approvals/stop must always
    // get through so a blocked or runaway run can be resolved.
    if (/^\/v1\/agent\/chat\b/i.test(parsed.path)) {
      const limit = agentChatDailyLimit(ent.tier);
      const quota = await checkAndCountQuota(account.accountId || '', 'agent_chat', limit);
      if (!quota.ok) {
        if (quota.reason === 'quota_exceeded') {
          return json(
            {
              error: `daily agent-chat limit reached (${quota.used}/${quota.limit})`,
              tier: ent.tier,
              limit: quota.limit,
            },
            429,
          );
        }
        return json({ error: 'quota accounting unavailable — try again shortly' }, 503);
      }
    }
  }

  // Build the upstream URL from the STORED base only — the client never gets to
  // name the host. The bearer is attached server-side and never echoed back.
  const target = `${account.gatewayUrl}${parsed.path}`;

  const headers: Record<string, string> = { Accept: 'application/json' };
  if (serviceToken) {
    headers.Authorization = `Bearer ${serviceToken}`;
  } else if (account.gatewayToken) {
    headers.Authorization = `Bearer ${account.gatewayToken}`;
  }
  if (requestId) headers['X-Muse-Request-Id'] = requestId;
  const relayToken = envVar('MUSE_GATEWAY_RELAY_TOKEN');
  if (relayToken) {
    headers['X-Muse-Relay-Authorization'] = `Bearer ${relayToken}`;
  }

  let body: string | undefined;
  if (req.method === 'POST') {
    const ct = req.headers.get('content-type');
    headers['Content-Type'] = ct || 'application/json';
    try {
      body = await req.text();
      if (new TextEncoder().encode(body).byteLength > MAX_RELAY_BODY_BYTES) {
        return json({ error: 'request body too large' }, 413);
      }
    } catch {
      body = undefined;
    }
  }

  let upstream: Response;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), RELAY_TIMEOUT_MS);
  try {
    upstream = await fetch(target, {
      method: req.method,
      headers,
      body,
      redirect: 'manual', // never auto-follow a redirect off the gateway origin
      signal: controller.signal,
    });
  } catch {
    return json({ error: 'gateway unreachable' }, 502);
  } finally {
    clearTimeout(timeout);
  }

  // Pass the upstream body through, but strip hop-by-hop / auth-bearing headers
  // and only surface a safe content type. Never leak Set-Cookie or upstream auth.
  const respHeaders: Record<string, string> = {
    'Content-Type': upstream.headers.get('content-type') || 'application/json',
    'Cache-Control': 'no-store',
  };
  return new Response(upstream.body, { status: upstream.status, headers: respHeaders });
}
