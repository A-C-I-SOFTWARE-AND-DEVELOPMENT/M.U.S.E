// ============================================================================
// Edge-safe, dependency-free rate limiting for the public chat endpoint.
//
// The public /api/chat spends the server-held provider key with no auth, so it
// needs a meter or a single abuser can burn the key. Two fixed windows per
// client IP: a per-minute burst limit (CHAT_RATE_RPM, default 20) and a daily
// cap (CHAT_RATE_DAILY, default 500).
//
// Backend, chosen at runtime with zero config:
//   * If UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN are set, counters
//     live in Upstash Redis (REST, via fetch — no SDK) so the limit is GLOBAL
//     across every Edge region/isolate.
//   * Otherwise an in-memory fixed-window counter per isolate — best-effort
//     (resets on cold start, not shared across regions), but still throttles a
//     single hot isolate. Documented as such; add Upstash for a hard limit.
//
// No secrets are logged; the IP is used only as a counter key.
// ============================================================================

declare const process: { env?: Record<string, string | undefined> } | undefined;

function env(name: string): string {
  return (typeof process !== 'undefined' && process.env && process.env[name]) || '';
}

function envInt(name: string, dflt: number): number {
  const v = parseInt(env(name), 10);
  return Number.isFinite(v) && v > 0 ? v : dflt;
}

export interface RateVerdict {
  ok: boolean;
  /** Seconds until the client may retry (0 when ok). */
  retryAfter: number;
  /** Which window tripped, for the response/diagnostics. */
  scope?: 'minute' | 'day';
}

/**
 * Client IP for rate-limit keying, from the PLATFORM-TRUSTED source only.
 *
 * The prior implementation used the leftmost X-Forwarded-For entry, which the
 * client can prepend — so an abuser sending `X-Forwarded-For: <random>` got a
 * fresh per-IP bucket every request and fully bypassed the meter on the
 * key-spending public endpoint. On Vercel, `x-real-ip` is set by the platform to
 * the actual client address and is NOT client-controllable, so we prefer it.
 * We only fall back to X-Forwarded-For and then take the RIGHTMOST hop (appended
 * by the trusted edge), never the spoofable leftmost value.
 */
export function clientIp(req: Request): string {
  const realIp = (req.headers.get('x-real-ip') || '').trim();
  if (realIp) return realIp;
  // x-vercel-forwarded-for is also platform-controlled on Vercel.
  for (const header of ['x-vercel-forwarded-for', 'x-forwarded-for']) {
    const parts = (req.headers.get(header) || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    if (parts.length) return parts[parts.length - 1];
  }
  return 'unknown';
}

// ---- in-memory fixed-window counters (per isolate) -------------------------

interface Window {
  count: number;
  resetAt: number;
}

const store = globalThis as unknown as {
  __chatRL?: { min: Map<string, Window>; day: Map<string, Window> };
};

function mem() {
  if (!store.__chatRL) store.__chatRL = { min: new Map(), day: new Map() };
  return store.__chatRL;
}

function prune(map: Map<string, Window>, now: number): void {
  if (map.size < 5000) return; // bound memory only when it actually grows
  for (const [k, w] of map) if (now >= w.resetAt) map.delete(k);
}

function hitWindow(
  map: Map<string, Window>,
  ip: string,
  limit: number,
  windowMs: number,
  now: number,
): RateVerdict {
  let w = map.get(ip);
  if (!w || now >= w.resetAt) {
    w = { count: 0, resetAt: now + windowMs };
    map.set(ip, w);
  }
  w.count += 1;
  if (w.count > limit) return { ok: false, retryAfter: Math.max(1, Math.ceil((w.resetAt - now) / 1000)) };
  return { ok: true, retryAfter: 0 };
}

function memVerdict(ip: string, rpm: number, daily: number, now: number): RateVerdict {
  const m = mem();
  prune(m.min, now);
  prune(m.day, now);
  const day = hitWindow(m.day, ip, daily, 86_400_000, now);
  if (!day.ok) return { ...day, scope: 'day' };
  const minute = hitWindow(m.min, ip, rpm, 60_000, now);
  if (!minute.ok) return { ...minute, scope: 'minute' };
  return { ok: true, retryAfter: 0 };
}

// ---- Upstash Redis REST (global, optional) ---------------------------------

async function upstashVerdict(
  base: string,
  token: string,
  ip: string,
  rpm: number,
  daily: number,
): Promise<RateVerdict> {
  const res = await fetch(`${base.replace(/\/$/, '')}/pipeline`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify([
      ['INCR', `chatrl:m:${ip}`],
      ['EXPIRE', `chatrl:m:${ip}`, '60', 'NX'],
      ['INCR', `chatrl:d:${ip}`],
      ['EXPIRE', `chatrl:d:${ip}`, '86400', 'NX'],
    ]),
  });
  if (!res.ok) throw new Error(`upstash ${res.status}`);
  const data = (await res.json()) as Array<{ result?: number }>;
  const minCount = data[0]?.result ?? 0;
  const dayCount = data[2]?.result ?? 0;
  if (dayCount > daily) return { ok: false, retryAfter: 86_400, scope: 'day' };
  if (minCount > rpm) return { ok: false, retryAfter: 60, scope: 'minute' };
  return { ok: true, retryAfter: 0 };
}

/**
 * Apply the per-IP rate limit. Uses Upstash when configured (global, hard
 * limit), else an in-memory per-isolate counter (best-effort). Never throws —
 * an Upstash hiccup falls back to in-memory so chat keeps working.
 */
export async function rateLimit(req: Request): Promise<RateVerdict> {
  const rpm = envInt('CHAT_RATE_RPM', 20);
  const daily = envInt('CHAT_RATE_DAILY', 500);
  const ip = clientIp(req);

  const base = env('UPSTASH_REDIS_REST_URL');
  const token = env('UPSTASH_REDIS_REST_TOKEN');
  if (base && token) {
    try {
      return await upstashVerdict(base, token, ip, rpm, daily);
    } catch {
      /* fall through to in-memory on any Upstash error */
    }
  }
  return memVerdict(ip, rpm, daily, Date.now());
}
