import { useEffect, useState } from 'react';
import { museBase } from './config';

// Live gateway health. Periodically probes the open /v1/health route so the UI
// reflects real reachability (and stream consumers can react to reconnects).

export type LinkState = 'offline' | 'connecting' | 'online';

let current: LinkState = 'offline';
const listeners = new Set<(s: LinkState) => void>();
let timer: number | null = null;

async function ping(): Promise<void> {
  const base = museBase();
  if (!base) {
    set('offline');
    return;
  }
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 4000);
    const res = await fetch(`${base}/v1/health`, { signal: ctrl.signal });
    clearTimeout(t);
    set(res.ok ? 'online' : 'offline');
  } catch {
    set('offline');
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
