import type { ActivityEvent } from './types';
import { museBase } from './config';

// Unified activity stream. Connects to the live M.U.S.E. cockpit event stream
// (SSE) when a gateway is configured; otherwise yields nothing (honest empty
// state). Antigravity / AI Studio have no event API, so their rows are
// user-driven.

type Listener = (e: ActivityEvent) => void;

export class ActivityStream {
  private listeners = new Set<Listener>();
  private sources: EventSource[] = [];

  start() {
    const base = museBase();
    if (!base || this.sources.length) return;
    // Cockpit control-plane events + the legacy /api/events lane.
    for (const path of ['/v1/cockpit/events/stream', '/api/events']) {
      try {
        const es = new EventSource(`${base}${path}`);
        es.onmessage = (ev) => {
          try {
            this.emit(this.normalize(JSON.parse(ev.data)));
          } catch {
            /* ignore malformed frames */
          }
        };
        es.onerror = () => {
          es.close();
          this.sources = this.sources.filter((s) => s !== es);
        };
        this.sources.push(es);
      } catch {
        /* skip a lane that fails to open */
      }
    }
  }

  /** Coerce cockpit event shapes into the unified ActivityEvent. */
  private normalize(raw: any): ActivityEvent {
    const kindMap: Record<string, ActivityEvent['kind']> = {
      'job.started': 'run-started',
      'job.completed': 'run-completed',
      'job.failed': 'error',
      error: 'error',
      'pr.opened': 'pr-opened',
      'needs-auth': 'needs-auth',
    };
    return {
      id: raw.id ?? `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      surface: 'muse',
      agentId: raw.agent_id ?? raw.job_id,
      kind: kindMap[raw.type ?? raw.kind] ?? (raw.kind ?? 'idle'),
      message: raw.message ?? raw.detail ?? raw.type ?? 'event',
      timestamp: raw.ts ? Date.parse(raw.ts) || Date.now() : Date.now(),
    };
  }

  stop() {
    this.sources.forEach((s) => s.close());
    this.sources = [];
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
