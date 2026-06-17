import type { ActivityEvent } from './types';

// Unified activity stream. Connects to the M.U.S.E. event stream (SSE) when a
// base URL is configured; otherwise yields nothing (honest empty state).
// Antigravity / AI Studio have no event API, so their rows are user-driven.

type Listener = (e: ActivityEvent) => void;

export class ActivityStream {
  private listeners = new Set<Listener>();
  private source: EventSource | null = null;

  start() {
    const base = import.meta.env.VITE_MUSE_BASE_URL ?? '';
    if (!base || this.source) return;
    try {
      this.source = new EventSource(`${base}/api/events`);
      this.source.onmessage = (ev) => {
        try {
          const parsed = JSON.parse(ev.data) as ActivityEvent;
          this.emit(parsed);
        } catch {
          /* ignore malformed frames */
        }
      };
      this.source.onerror = () => {
        this.source?.close();
        this.source = null;
      };
    } catch {
      this.source = null;
    }
  }

  stop() {
    this.source?.close();
    this.source = null;
  }

  on(fn: Listener) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private emit(e: ActivityEvent) {
    this.listeners.forEach((l) => l(e));
  }
}

export const activityStream = new ActivityStream();
