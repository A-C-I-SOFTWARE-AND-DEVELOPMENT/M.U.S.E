import { useEffect, useState } from 'react';
import { museBase } from './config';

// Live connection state. Periodically probes the gateway's open /v1/health route,
// but — crucially — when no gateway is established it AUTO-FALLS-BACK to "online"
// (provider-direct / hosted mode) rather than reporting offline, so the app is
// immediately usable without a gateway. States:
//   • gateway — the MUSE gateway is established and reachable
//   • online  — no gateway, but the internet is up → provider-direct mode (usable)
//   • offline — no network at all
//   • connecting — probing

export type LinkState = 'offline' | 'connecting' | 'gateway' | 'online';

/**
 * Pure resolver (unit-tested). The key rule: a missing/unreachable gateway is NOT
 * "offline" as long as we're on the internet — we automatically go "online" and
 * use provider-direct / hosted capabilities.
 */
export function resolveLinkState(hasGateway: boolean, gatewayOk: boolean, navigatorOnline: boolean): LinkState {
  if (!navigatorOnline) return 'offline';
  if (hasGateway && gatewayOk) return 'gateway';
  return 'online'; // no gateway, or gateway down → auto online
}

function isOnline(): boolean {
  return typeof navigator === 'undefined' || navigator.onLine !== false;
}

let current: LinkState = 'connecting';
const listeners = new Set<(s: LinkState) => void>();
let timer: number | null = null;

async function ping(): Promise<void> {
  const online = isOnline();
  const base = museBase();
  // No gateway configured → go straight to online (no probe needed).
  if (!base) {
    set(resolveLinkState(false, false, online));
    return;
  }
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 4000);
    const res = await fetch(`${base}/v1/health`, { signal: ctrl.signal });
    clearTimeout(t);
    set(resolveLinkState(true, res.ok, online));
  } catch {
    // Gateway unreachable, but if we're on the internet still auto go online.
    set(resolveLinkState(true, false, online));
  }
}

function set(s: LinkState) {
  if (s === current) return;
  current = s;
  listeners.forEach((l) => l(s));
}

export function startHealthMonitor(intervalMs = 15000): void {
  if (timer != null) return;
  void ping();
  timer = window.setInterval(ping, intervalMs);
  window.addEventListener('nexus:config', () => {
    set('connecting');
    void ping();
  });
  window.addEventListener('online', () => void ping());
  window.addEventListener('offline', () => set('offline'));
}

export function useLinkState(): LinkState {
  const [s, setS] = useState<LinkState>(current);
  useEffect(() => {
    listeners.add(setS);
    return () => {
      listeners.delete(setS);
    };
  }, []);
  return s;
}
