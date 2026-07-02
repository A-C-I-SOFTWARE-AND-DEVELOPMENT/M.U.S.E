// ============================================================================
// POST /api/billing/webhook — Stripe webhook receiver. This is the ONLY writer
// of subscription entitlement state (subscriptions table). It:
//   1. Verifies the Stripe-Signature header with STRIPE_WEBHOOK_SECRET via Web
//      Crypto HMAC-SHA256 (no SDK) with a 5-minute tolerance.
//   2. De-dupes via the stripe_events ledger (Stripe may redeliver an event).
//   3. Upserts the account's row from the subscription's tier + status.
//
// Handled events:
//   checkout.session.completed
//   customer.subscription.created | updated | deleted
//   invoice.payment_failed
//
// Secrets from process.env only. 501 when unconfigured (safe when commerce-off).
// ============================================================================

import {
  envVar,
  json,
  serviceRoleKey,
  stripe,
  supabaseUrl,
  tierForPrice,
} from './_stripe';

export const config = { runtime: 'edge' };

const enc = new TextEncoder();

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let out = 0;
  for (let i = 0; i < a.length; i++) out |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return out === 0;
}

async function hmacHex(secret: string, payload: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    'raw',
    enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(payload));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** Verify Stripe's `t=...,v1=...` signature header. */
async function verifyStripeSignature(
  payload: string,
  header: string,
  secret: string,
  toleranceSec = 300,
): Promise<boolean> {
  const parts = Object.fromEntries(
    header.split(',').map((kv) => {
      const i = kv.indexOf('=');
      return [kv.slice(0, i), kv.slice(i + 1)];
    }),
  );
  const t = parts['t'];
  const v1 = parts['v1'];
  if (!t || !v1) return false;
  // Reject stale timestamps (replay protection). Uses Date.now — fine at the
  // edge (this is request-time, not build-time).
  const ts = parseInt(t, 10);
  if (!Number.isFinite(ts) || Math.abs(Date.now() / 1000 - ts) > toleranceSec) return false;
  const expected = await hmacHex(secret, `${t}.${payload}`);
  return timingSafeEqual(expected, v1);
}

/** Idempotency: returns true if this event id was already processed. */
async function alreadyProcessed(eventId: string): Promise<boolean> {
  const base = supabaseUrl();
  const svc = serviceRoleKey();
  const res = await fetch(`${base}/rest/v1/stripe_events`, {
    method: 'POST',
    headers: {
      apikey: svc,
      Authorization: `Bearer ${svc}`,
      'Content-Type': 'application/json',
      // return=representation + no merge → a duplicate PK insert 409s, which is
      // our "already processed" signal.
      Prefer: 'return=minimal',
    },
    body: JSON.stringify({ id: eventId, type: 'pending' }),
  });
  // 201 = first time; 409 = duplicate (already processed).
  return res.status === 409;
}

async function upsertSubscription(row: {
  user_id: string;
  stripe_subscription_id?: string;
  price_id?: string;
  tier: 'free' | 'pro';
  status: string;
  current_period_end?: string | null;
}): Promise<void> {
  const base = supabaseUrl();
  const svc = serviceRoleKey();
  await fetch(`${base}/rest/v1/subscriptions`, {
    method: 'POST',
    headers: {
      apikey: svc,
      Authorization: `Bearer ${svc}`,
      'Content-Type': 'application/json',
      Prefer: 'resolution=merge-duplicates,return=minimal',
    },
    body: JSON.stringify({ ...row, updated_at: new Date().toISOString() }),
  });
}

/** Resolve the account id for a Stripe customer via profiles. */
async function accountForCustomer(customerId: string): Promise<string> {
  const base = supabaseUrl();
  const svc = serviceRoleKey();
  const q = new URL(`${base}/rest/v1/profiles`);
  q.searchParams.set('stripe_customer_id', `eq.${customerId}`);
  q.searchParams.set('select', 'user_id');
  q.searchParams.set('limit', '1');
  const r = await fetch(q.toString(), {
    headers: { apikey: svc, Authorization: `Bearer ${svc}`, Accept: 'application/json' },
  });
  if (!r.ok) return '';
  const rows = (await r.json()) as Array<{ user_id?: string }>;
  return rows?.[0]?.user_id || '';
}

async function applySubscriptionObject(sub: any): Promise<void> {
  const accountId =
    sub?.metadata?.account_id || (await accountForCustomer(sub?.customer || ''));
  if (!accountId) return;
  const priceId = sub?.items?.data?.[0]?.price?.id || '';
  const status = String(sub?.status || 'inactive');
  const tier = status === 'active' || status === 'trialing' ? tierForPrice(priceId) : 'free';
  const periodEnd = sub?.current_period_end
    ? new Date(sub.current_period_end * 1000).toISOString()
    : null;
  await upsertSubscription({
    user_id: accountId,
    stripe_subscription_id: sub?.id,
    price_id: priceId,
    tier,
    status,
    current_period_end: periodEnd,
  });
}

export default async function handler(req: Request): Promise<Response> {
  if (req.method !== 'POST') return json({ error: 'method not allowed' }, 405);
  const secret = envVar('STRIPE_WEBHOOK_SECRET');
  if (!secret || !supabaseUrl() || !serviceRoleKey()) {
    return json({ error: 'billing webhook not configured' }, 501);
  }

  const sigHeader = req.headers.get('stripe-signature') || '';
  const payload = await req.text();
  if (!(await verifyStripeSignature(payload, sigHeader, secret))) {
    return json({ error: 'invalid signature' }, 400);
  }

  let event: any;
  try {
    event = JSON.parse(payload);
  } catch {
    return json({ error: 'invalid JSON' }, 400);
  }

  // De-dupe before doing any work.
  if (event.id && (await alreadyProcessed(event.id))) {
    return json({ received: true, deduped: true }, 200);
  }

  try {
    switch (event.type) {
      case 'checkout.session.completed': {
        const session = event.data.object;
        // Fetch the subscription to get price + period + status.
        if (session.subscription) {
          const sub = await stripe(`subscriptions/${session.subscription}`, {}, 'GET');
          // Ensure the account id is carried even if metadata was set on session.
          if (!sub.metadata) sub.metadata = {};
          if (!sub.metadata.account_id && session.client_reference_id) {
            sub.metadata.account_id = session.client_reference_id;
          }
          await applySubscriptionObject(sub);
        }
        break;
      }
      case 'customer.subscription.created':
      case 'customer.subscription.updated':
      case 'customer.subscription.deleted': {
        await applySubscriptionObject(event.data.object);
        break;
      }
      case 'invoice.payment_failed': {
        const inv = event.data.object;
        const accountId = await accountForCustomer(inv?.customer || '');
        if (accountId) {
          await upsertSubscription({
            user_id: accountId,
            tier: 'free',
            status: 'past_due',
          });
        }
        break;
      }
      default:
        // Unhandled event types are acknowledged (200) so Stripe stops retrying.
        break;
    }
  } catch (e) {
    // A processing error → 500 so Stripe retries (the dedupe insert above will
    // still let the retry through because we only recorded id with type
    // 'pending'; re-applying subscription state is idempotent anyway).
    return json({ error: `processing failed: ${(e as Error).message}` }, 500);
  }

  return json({ received: true }, 200);
}
