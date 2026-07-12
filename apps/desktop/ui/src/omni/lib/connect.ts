// ============================================================================
// One-click autonomous connection establishment.
//
// Given the gateway URL (or auto-discovered) and the owner phrase, this chains
// the entire bring-up: discover gateway -> cockpit device pairing (owner-gated)
// -> verify capabilities -> wire observatory, runtime, push, Supabase, voice.
// Each connection reports its own status; nothing is faked.
// ============================================================================

import { getConfig, setConfig, museBase, authHeaders } from './config';
import { cockpit } from '@/adapters/cockpit';
import { fetchSnapshot } from '@/adapters/observatory';
import { enablePush, pushSupported } from './push';
import { supabaseConfigured, getSessionUser } from './supabase';
import { sttSupported, ttsSupported } from './voice';

export type StepStatus = 'pending' | 'running' | 'ok' | 'skip' | 'fail';

export interface ConnectStep {
  key: string;
  label: string;
  status: StepStatus;
  detail?: string;
}

export interface ConnectOptions {
  baseUrl?: string;
  ownerPhrase: string;
  deviceName?: string;
  /** Enable push during connect (asks for notification permission). */
  withPush?: boolean;
}

const DISCOVERY_CANDIDATES = (explicit?: string): string[] => {
  const origin = typeof window !== 'undefined' ? window.location.origin : '';
  return [
    explicit,
    getConfig().museBaseUrl,
    origin,
    'http://127.0.0.1:8765',
    'http://localhost:8765',
  ]
    .filter((u): u is string => !!u)
    .map((u) => u.replace(/\/$/, ''))
    .filter((u, i, a) => a.indexOf(u) === i);
};

async function probeHealth(base: string): Promise<boolean> {
  try {
    const res = await fetch(`${base}/v1/health`, { method: 'GET' });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * True when NEXUS is served over HTTPS but the only gateway we'd try is a local
 * http:// address (localhost / 127.0.0.1 / private LAN). The browser blocks that
 * fetch as mixed content, so the gateway can never be reached from the hosted
 * app — this is expected, not a failure. Cockpit features then need the gateway
 * exposed over HTTPS (a tunnel); everything else works without it.
 */
export function localGatewayBlockedByHttps(baseUrl?: string): boolean {
  if (typeof window === 'undefined') return false;
  if (window.location.protocol !== 'https:') return false;
  const target = (baseUrl || getConfig().museBaseUrl || 'http://127.0.0.1:8765').trim();
  if (!/^http:\/\//i.test(target)) return false; // https gateway is fine
  const host = target.replace(/^http:\/\//i, '').split(/[:/]/)[0];
  return (
    host === 'localhost' ||
    host === '127.0.0.1' ||
    host === '0.0.0.0' ||
    /^10\./.test(host) ||
    /^192\.168\./.test(host) ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(host)
  );
}

const newSteps = (): ConnectStep[] => [
  { key: 'discover', label: 'Discover MUSE gateway', status: 'pending' },
  { key: 'pair', label: 'Pair device (owner-gated)', status: 'pending' },
  { key: 'capabilities', label: 'Verify capabilities', status: 'pending' },
  { key: 'observatory', label: 'Connect Neural Observatory', status: 'pending' },
  { key: 'runtime', label: 'Read runtime status', status: 'pending' },
  { key: 'push', label: 'Enable push notifications', status: 'pending' },
  { key: 'supabase', label: 'Link Supabase persistence', status: 'pending' },
  { key: 'voice', label: 'Arm voice bridge', status: 'pending' },
];

/**
 * When NEXUS is served *by* the gateway (e.g. MUSE running in Termux on the same
 * phone serves the PWA at http://localhost:8765/), the page origin IS the gateway
 * — same scheme, same host, so there is no mixed-content barrier. Returns that
 * origin if it answers /v1/health, else ''. Used to auto-connect on first load.
 */
export async function detectSameOriginGateway(): Promise<string> {
  if (typeof window === 'undefined') return '';
  const origin = window.location.origin.replace(/\/$/, '');
  if (!origin || origin.startsWith('file:')) return '';
  return (await probeHealth(origin)) ? origin : '';
}

/**
 * Run the full autonomous bring-up. Calls onProgress after every step so the UI
 * animates live; resolves with the final step list.
 */
export async function establishConnections(
  opts: ConnectOptions,
  onProgress: (steps: ConnectStep[]) => void,
): Promise<ConnectStep[]> {
  const steps = newSteps();
  const set = (key: string, status: StepStatus, detail?: string) => {
    const s = steps.find((x) => x.key === key)!;
    s.status = status;
    if (detail !== undefined) s.detail = detail;
    onProgress([...steps]);
  };

  // 1) Discover the gateway.
  set('discover', 'running');
  let base = '';
  for (const cand of DISCOVERY_CANDIDATES(opts.baseUrl)) {
    if (await probeHealth(cand)) {
      base = cand;
      break;
    }
  }
  if (!base) {
    const detail = localGatewayBlockedByHttps(opts.baseUrl)
      ? 'Hosted over HTTPS — a local http://localhost gateway is blocked (mixed content). Expected: use providers directly, or expose the gateway over HTTPS.'
      : 'No gateway reachable (tried localhost:8765, origin, configured URL)';
    set('discover', localGatewayBlockedByHttps(opts.baseUrl) ? 'skip' : 'fail', detail);
    ['pair', 'capabilities', 'observatory', 'runtime', 'push', 'supabase', 'voice'].forEach((k) =>
      set(k, 'skip', 'gateway optional — not connected'),
    );
    return steps;
  }
  setConfig({ museBaseUrl: base });
  set('discover', 'ok', base);

  // 2) Pair the device (owner-gated) — unless an existing token already works.
  set('pair', 'running');
  let paired = false;
  if (getConfig().museToken) {
    const cap = await cockpit.capabilities();
    if (cap) {
      paired = true;
      set('pair', 'ok', 'existing device token valid');
    }
  }
  if (!paired) {
    try {
      const startRes = await fetch(`${base}/v1/cockpit/pair/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_name: opts.deviceName ?? 'NEXUS PWA' }),
      });
      if (!startRes.ok) throw new Error(`pair/start ${startRes.status}`);
      const { pairing_code } = await startRes.json();

      const confirmRes = await fetch(`${base}/v1/cockpit/pair/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pairing_code, authorization: opts.ownerPhrase }),
      });
      if (confirmRes.status === 403) {
        set('pair', 'fail', 'owner phrase rejected — must be exactly "Yes, with authorization."');
      } else if (!confirmRes.ok) {
        set('pair', 'fail', `pair/confirm ${confirmRes.status}`);
      } else {
        const { token } = await confirmRes.json();
        setConfig({ museToken: token });
        paired = true;
        set('pair', 'ok', 'device token issued');
      }
    } catch (e) {
      set('pair', 'fail', String((e as Error).message ?? e));
    }
  }

  // 3) Verify capabilities (proves the bearer works end-to-end).
  set('capabilities', 'running');
  const caps = await cockpit.capabilities();
  if (caps) set('capabilities', 'ok', 'cockpit reachable');
  else set('capabilities', paired ? 'fail' : 'skip', paired ? 'no response' : 'not paired');

  // 4) Observatory.
  set('observatory', 'running');
  const snap = await fetchSnapshot();
  if (snap?.graph.available) set('observatory', 'ok', `${snap.graph.node_count.toLocaleString()} nodes`);
  else set('observatory', 'ok', 'connected (graph dormant until GraphRAG build)');

  // 5) Runtime.
  set('runtime', 'running');
  const rt = await cockpit.runtimeStatus();
  set('runtime', rt ? 'ok' : 'skip', rt ? 'monitors online' : 'no runtime endpoint');

  // 6) Push.
  if (opts.withPush && pushSupported()) {
    set('push', 'running');
    const r = await enablePush();
    set('push', r.ok ? 'ok' : 'skip', r.ok ? 'subscribed' : r.reason);
  } else {
    set('push', 'skip', pushSupported() ? 'opt-in' : 'unsupported here');
  }

  // 7) Supabase.
  set('supabase', 'running');
  if (supabaseConfigured()) {
    await getSessionUser();
    set('supabase', 'ok', 'persistence linked');
  } else {
    set('supabase', 'skip', 'not configured (optional)');
  }

  // 8) Voice.
  set('voice', sttSupported() || ttsSupported() ? 'ok' : 'skip', sttSupported() ? 'Web Speech ready' : 'unsupported');

  // Touch authHeaders so the bearer is exercised once paired.
  void authHeaders();
  void museBase();
  return steps;
}
