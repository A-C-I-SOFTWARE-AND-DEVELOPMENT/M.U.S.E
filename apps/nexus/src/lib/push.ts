// Web Push subscription helper (PWA-native notifications).
// VAPID public key is injected at build time; subscriptions are persisted to
// Supabase so the M.U.S.E. backend can target this device for:
//   - long-running agent completion
//   - agent errors
//   - owner-gated authorization prompts
// See ADAPTERS.md for the expected /api/push/subscribe shape.

import { persistPushSubscription } from './supabase';

const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY ?? '';
const MUSE_BASE = import.meta.env.VITE_MUSE_BASE_URL ?? '';

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(b64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export function pushSupported(): boolean {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
}

export async function enablePush(): Promise<{ ok: boolean; reason?: string }> {
  if (!pushSupported()) return { ok: false, reason: 'Push not supported on this device' };
  if (!VAPID_PUBLIC_KEY) return { ok: false, reason: 'VITE_VAPID_PUBLIC_KEY not set' };

  const permission = await Notification.requestPermission();
  if (permission !== 'granted') return { ok: false, reason: 'Permission denied' };

  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY) as BufferSource,
  });

  if (MUSE_BASE) {
    await fetch(`${MUSE_BASE}/api/push/subscribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(sub),
    });
  }
  // Persist to Supabase too (optional; no-ops when Supabase is unconfigured).
  await persistPushSubscription(sub.toJSON());
  return { ok: true };
}

export async function pushEnabled(): Promise<boolean> {
  if (!pushSupported()) return false;
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    return !!sub;
  } catch {
    return false;
  }
}
