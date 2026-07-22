import { useCallback, useEffect, useState } from "react";
import { fetchJSON } from "@/lib/api";

/* ------------------------------------------------------------------ */
/* Night Desk shared data hook.                                        */
/*                                                                     */
/* Contract (ND-SHELL — the whole page imports against this):          */
/*   useNightdeskOverview(pollMs?) -> { data, error, loading, refresh }*/
/*                                                                     */
/* Module-level pub/sub: N subscribers share ONE poller against        */
/* GET /api/nightdesk/overview. The effective cadence is the FASTEST   */
/* pollMs among live subscribers; the poller stops when the last       */
/* subscriber unmounts. refresh() forces an immediate refetch for all  */
/* subscribers (used e.g. after EmergencyStop fires).                  */
/*                                                                     */
/* NO MOCK DATA: every interface below mirrors the live backend        */
/* (hermes_cli/web_nightdesk_api.py). Absent sources surface as null / */
/* [] / { available: false } — never fabricated values.                */
/* ------------------------------------------------------------------ */

/* ── Typed interfaces mirroring hermes_cli/web_nightdesk_api.py ────── */

export interface KpisAutonomy {
  level: string;
  emergency_stopped: boolean;
  set_by?: string | null;
  updated_at?: string | null;
}

export interface FallbackChainEntry {
  provider: string;
  model: string;
  base_url: string;
}

export interface NightdeskKpis {
  tokens_today: number;
  turns_today: number;
  sessions_today?: number;
  cost_today_usd: number;
  /** true when cost_today_usd is the estimated figure (actual unmetered). */
  cost_estimated: boolean;
  cost_actual_usd?: number;
  graph_nodes: number | null;
  graph_edges: number | null;
  graph_density?: unknown;
  active_model: string | null;
  active_provider: string | null;
  fallback_chain: FallbackChainEntry[];
  autonomy: KpisAutonomy | null;
  as_of?: number;
}

export interface CouncilMember {
  id: string;
  role: string;
  owner_gated: boolean;
  kind?: string;
}

export interface NightdeskCouncil {
  total: number;
  members: CouncilMember[];
  /** false when the council registry is unavailable on the backend. */
  available?: boolean;
}

export interface NightdeskAutomation {
  id: string;
  name: string;
  schedule_display: string | null;
  deliver: string | null;
  enabled: boolean;
  state: string | null;
  last_run_at: number | null;
  last_status: string | null;
  next_run_at: number | null;
  profile?: string | null;
}

export interface NightdeskLedgerEntry {
  id: string;
  title: string;
  session: string;
  /** unix seconds */
  ts: number;
}

export interface ExecutionBackend {
  name: string;
  label: string;
  status: string;
  detail: string | null;
  active: boolean;
}

export interface MessagingPlatform {
  id: string;
  name: string;
  /** backend-mapped: online | standby | degraded | offline */
  status: string;
  error_message: string | null;
  enabled?: boolean;
  configured?: boolean;
  raw_state?: string | null;
  error_code?: string | null;
}

export interface CliTuiBackend {
  id: string;
  name: string;
  status: string;
  detail: string | null;
  dashboard_up?: boolean;
  tui_gateway_ws_served?: boolean;
}

export interface NightdeskBackends {
  execution: ExecutionBackend[];
  active_execution_backend: string | null;
  messaging: MessagingPlatform[];
  cli_tui: CliTuiBackend | null;
}

export interface NightdeskAxion {
  identity_excerpt: string | null;
  wired: boolean;
  available?: boolean;
}

export interface OverviewData {
  kpis: NightdeskKpis;
  council: NightdeskCouncil;
  automations: NightdeskAutomation[];
  ledger: NightdeskLedgerEntry[];
  backends: NightdeskBackends;
  axion: NightdeskAxion;
  generated_at?: number;
}

/** POST /api/nightdesk/emergency-stop response shape. */
export interface EmergencyStopResult {
  cleared_actions: string[];
  branch_leases_cleared: number;
  tick_disabled: boolean;
  cancelled_jobs: string[];
  cancelled_count: number;
  autonomy_level: string | null;
  skipped_effects: string[];
  errors: string[];
  halted_at?: string;
  ledger_record_hash?: string;
}

/* ── Module-level store + pub/sub ──────────────────────────────────── */

interface NightdeskSnapshot {
  data: OverviewData | null;
  error: string | null;
  loading: boolean;
}

let snapshot: NightdeskSnapshot = { data: null, error: null, loading: true };

/** listener -> requested poll cadence (ms) */
const listeners = new Map<() => void, number>();
let timer: number | null = null;
let inFlight = false;

function emit(): void {
  for (const listener of listeners.keys()) listener();
}

function setSnapshot(patch: Partial<NightdeskSnapshot>): void {
  snapshot = { ...snapshot, ...patch };
  emit();
}

function fastestPollMs(): number {
  let min = Infinity;
  for (const ms of listeners.values()) min = Math.min(min, ms);
  return Number.isFinite(min) ? min : 0;
}

async function fetchNow(): Promise<void> {
  if (inFlight || listeners.size === 0) return;
  inFlight = true;
  try {
    const data = await fetchJSON<OverviewData>("/api/nightdesk/overview");
    setSnapshot({ data, error: null, loading: false });
  } catch (err) {
    setSnapshot({
      error: err instanceof Error ? err.message : String(err),
      loading: false,
    });
  } finally {
    inFlight = false;
  }
}

function restartPoller(): void {
  if (timer !== null) {
    window.clearInterval(timer);
    timer = null;
  }
  const ms = fastestPollMs();
  if (listeners.size > 0 && ms > 0) {
    timer = window.setInterval(() => {
      void fetchNow();
    }, ms);
  }
}

function subscribe(pollMs: number, listener: () => void): () => void {
  const wasEmpty = listeners.size === 0;
  const prevFastest = fastestPollMs();
  listeners.set(listener, pollMs);

  if (wasEmpty || pollMs < prevFastest) restartPoller();
  // Cold start: nothing fetched yet — kick immediately (the inFlight guard
  // dedupes the burst when several page components mount in one pass).
  if (snapshot.data === null && !inFlight) void fetchNow();

  return () => {
    const leavingMs = listeners.get(listener);
    listeners.delete(listener);
    if (listeners.size === 0) {
      restartPoller(); // stops the timer
    } else if (leavingMs !== undefined && leavingMs <= fastestPollMs()) {
      restartPoller(); // fastest subscriber left — relax the cadence
    }
  };
}

/* ── Public hook (contract) ────────────────────────────────────────── */

export function useNightdeskOverview(pollMs = 30000): {
  data: OverviewData | null;
  error: string | null;
  loading: boolean;
  refresh: () => void;
} {
  const [local, setLocal] = useState<NightdeskSnapshot>(snapshot);

  useEffect(() => {
    const listener = () => setLocal({ ...snapshot });
    const unsubscribe = subscribe(pollMs, listener);
    // Sync any state change that landed between render and effect.
    setLocal({ ...snapshot });
    return unsubscribe;
  }, [pollMs]);

  const refresh = useCallback(() => {
    void fetchNow();
  }, []);

  return {
    data: local.data,
    error: local.error,
    loading: local.loading,
    refresh,
  };
}

/* ── Shared formatting helpers (used across Night Desk components) ─── */

/** "just now" / "4m ago" / "2h ago" / "3d ago" from unix seconds. */
export function formatRelativeTime(ts: number | null | undefined): string {
  if (!ts || !Number.isFinite(ts) || ts <= 0) return "—";
  const delta = Date.now() / 1000 - ts;
  if (delta < 45) return "just now";
  if (delta < 3600) return `${Math.max(1, Math.round(delta / 60))}m ago`;
  if (delta < 86400) return `${Math.round(delta / 3600)}h ago`;
  return `${Math.round(delta / 86400)}d ago`;
}

/** Night Desk status scale — normalizes arbitrary backend status strings. */
export type NdStatus = "online" | "standby" | "degraded" | "offline" | "emergency";

export function normalizeNdStatus(raw: string | null | undefined): NdStatus {
  const s = (raw ?? "").trim().toLowerCase();
  if (
    s === "online" ||
    s === "active" ||
    s === "connected" ||
    s === "ok" ||
    s === "ready" ||
    s === "healthy" ||
    s === "running"
  ) {
    return "online";
  }
  if (
    s === "standby" ||
    s === "pending" ||
    s === "pending_restart" ||
    s === "connecting" ||
    s === "retrying" ||
    s === "paused" ||
    s === "idle"
  ) {
    return "standby";
  }
  if (
    s === "degraded" ||
    s === "error" ||
    s === "failed" ||
    s === "fatal" ||
    s === "startup_failed" ||
    s === "timeout" ||
    s === "unavailable"
  ) {
    return "degraded";
  }
  if (s === "emergency" || s === "stopped" || s === "emergency_stopped") {
    return "emergency";
  }
  return "offline";
}
