// ============================================================================
// Edge: server-side session verification — the auth SECURITY BOUNDARY.
//
// POST /api/auth/session   Authorization: Bearer <supabase access token>
//   -> 200 { user: { id, email, role }, verified: true }   (signature + exp OK)
//   -> 401 { error }                                        (missing/invalid/expired)
//   -> 501 { error: 'auth not configured' }                 (no SUPABASE_JWT_SECRET)
//
// Why this exists: the browser holds the user's own access token, but a client
// can claim to be ANY user id. The server MUST NOT trust a client-asserted id.
// We re-derive identity by cryptographically verifying the JWT's HS256
// signature against SUPABASE_JWT_SECRET (server-only; never VITE_-prefixed,
// never sent to the browser) and checking its expiry. The `sub` claim from a
// VERIFIED token is the only trustworthy user id.
//
// Verification uses the Web Crypto API (crypto.subtle) so it runs on the Vercel
// Edge runtime with no Node-only crypto and no jsonwebtoken dependency.
// ============================================================================

export const config = { runtime: 'edge' };

// Server-only secret source. Optional-typed so this compiles without
// @types/node while remaining compatible with it (declaration merging).
declare const process: { env?: Record<string, string | undefined> } | undefined;

function serverSecret(): string {
  return process?.env?.SUPABASE_JWT_SECRET ?? '';
}

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

// ---- base64url helpers ------------------------------------------------------
function b64urlToBytes(s: string): Uint8Array {
  const pad = '='.repeat((4 - (s.length % 4)) % 4);
  const b64 = (s + pad).replace(/-/g, '+').replace(/_/g, '/');
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function b64urlToString(s: string): string {
  return new TextDecoder().decode(b64urlToBytes(s));
}

/** Constant-time-ish comparison of two byte arrays. */
function bytesEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

interface JwtClaims {
  sub?: string;
  email?: string;
  role?: string;
  exp?: number;
  aud?: string | string[];
}

interface VerifyResult {
  ok: boolean;
  claims?: JwtClaims;
  reason?: string;
}

/** Verify an HS256 Supabase JWT against the shared secret. */
async function verifyJwt(token: string, secret: string): Promise<VerifyResult> {
  const parts = token.split('.');
  if (parts.length !== 3) return { ok: false, reason: 'malformed token' };
  const [headerB64, payloadB64, sigB64] = parts;

  let header: { alg?: string; typ?: string };
  let claims: JwtClaims;
  try {
    header = JSON.parse(b64urlToString(headerB64));
    claims = JSON.parse(b64urlToString(payloadB64));
  } catch {
    return { ok: false, reason: 'malformed token' };
  }

  // Supabase signs with HS256. Reject anything else (incl. "none") outright.
  if (header.alg !== 'HS256') return { ok: false, reason: 'unsupported alg' };

  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const expected = new Uint8Array(
    await crypto.subtle.sign('HMAC', key, enc.encode(`${headerB64}.${payloadB64}`)),
  );
  const provided = b64urlToBytes(sigB64);
  if (!bytesEqual(expected, provided)) return { ok: false, reason: 'bad signature' };

  // Expiry (signature is valid, so exp is now trustworthy).
  const now = Math.floor(Date.now() / 1000);
  if (typeof claims.exp === 'number' && claims.exp <= now) {
    return { ok: false, reason: 'token expired' };
  }

  return { ok: true, claims };
}

function bearer(req: Request): string {
  const h = req.headers.get('authorization') || req.headers.get('Authorization') || '';
  const m = /^Bearer\s+(.+)$/i.exec(h.trim());
  return m ? m[1] : '';
}

export default async function handler(req: Request): Promise<Response> {
  if (req.method !== 'POST' && req.method !== 'GET') {
    return json({ error: 'method not allowed' }, 405);
  }

  const secret = serverSecret();
  if (!secret) {
    // Honest "not configured" — degrade gracefully when the env is unset.
    return json({ error: 'auth not configured', verified: false }, 501);
  }

  const token = bearer(req);
  if (!token) {
    return json({ error: 'missing bearer token', verified: false }, 401);
  }

  const result = await verifyJwt(token, secret);
  if (!result.ok || !result.claims?.sub) {
    return json({ error: result.reason || 'invalid token', verified: false }, 401);
  }

  // ONLY the verified `sub` is returned as the user id. We never echo or trust
  // any client-sent id; identity comes from the signature, not the request body.
  return json(
    {
      verified: true,
      user: {
        id: result.claims.sub,
        email: result.claims.email ?? null,
        role: result.claims.role ?? 'authenticated',
      },
    },
    200,
  );
}
