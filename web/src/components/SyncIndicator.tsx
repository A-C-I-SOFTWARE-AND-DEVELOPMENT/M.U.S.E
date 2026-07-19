/**
 * SyncIndicator — small "Last synced Xs ago" pill with a manual refresh button.
 *
 * Shows the freshness of the data on the current page. Designed to be
 * dropped into any page that fetches data from the server, so the user
 * always knows whether what they're looking at is up to date.
 *
 * Usage:
 *   <SyncIndicator
 *     onSync={async () => { await fetchData(); }}
 *     lastSyncedAt={lastFetchedAt}
 *     label="API keys"
 *   />
 */
import { useEffect, useState, useCallback } from "react";
import { Check, RefreshCw, AlertCircle, Loader2 } from "lucide-react";

interface SyncIndicatorProps {
  /** Async function that re-fetches the data; should throw on failure. */
  onSync: () => Promise<void>;
  /** Optional initial value — defaults to the moment of mount. */
  lastSyncedAt?: Date;
  /** What we're syncing — shown in the toast/label. */
  label?: string;
  /** Auto-refresh interval in ms. 0 disables auto-refresh. Default 30000. */
  autoRefreshMs?: number;
  /** Hide the auto-refresh timer (e.g. for sensitive pages). */
  disableAutoRefresh?: boolean;
}

function formatRelative(date: Date, now: Date): string {
  const diff = Math.max(0, Math.round((now.getTime() - date.getTime()) / 1000));
  if (diff < 5) return "just now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export function SyncIndicator({
  onSync,
  lastSyncedAt,
  label = "data",
  autoRefreshMs = 30_000,
  disableAutoRefresh = false,
}: SyncIndicatorProps) {
  const [syncedAt, setSyncedAt] = useState<Date | null>(lastSyncedAt ?? null);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [, setTick] = useState(0);

  // Re-render every 5s so the "Xs ago" text stays current
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 5_000);
    return () => clearInterval(t);
  }, []);

  // Auto-refresh
  useEffect(() => {
    if (disableAutoRefresh || autoRefreshMs <= 0) return;
    const t = setInterval(() => {
      if (!syncing) void doSync(true);
    }, autoRefreshMs);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefreshMs, disableAutoRefresh, syncing]);

  const doSync = useCallback(
    async (silent = false) => {
      if (syncing) return;
      setSyncing(true);
      setError(null);
      try {
        await onSync();
        setSyncedAt(new Date());
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
        if (!silent) console.warn(`[SyncIndicator] failed to sync ${label}:`, msg);
      } finally {
        setSyncing(false);
      }
    },
    [onSync, syncing, label],
  );

  const now = new Date();
  const state: "fresh" | "stale" | "syncing" | "error" = syncing
    ? "syncing"
    : error
      ? "error"
      : !syncedAt
        ? "stale"
        : now.getTime() - syncedAt.getTime() < 60_000
          ? "fresh"
          : "stale";

  return (
    <div className="inline-flex items-center gap-1.5 rounded border border-current/15 bg-white/[0.02] px-2 py-0.5 text-[0.65rem] tracking-[0.05em]">
      {state === "syncing" ? (
        <Loader2 className="h-3 w-3 animate-spin opacity-60" />
      ) : state === "error" ? (
        <AlertCircle className="h-3 w-3 text-red-400" />
      ) : state === "fresh" ? (
        <Check className="h-3 w-3 text-emerald-400" />
      ) : (
        <AlertCircle className="h-3 w-3 text-amber-400" />
      )}
      <span
        className={
          state === "error"
            ? "text-red-300"
            : state === "fresh"
              ? "text-emerald-300/80"
              : "opacity-60"
        }
      >
        {state === "syncing"
          ? `syncing ${label}…`
          : state === "error"
            ? `sync failed · ${error?.slice(0, 30) ?? ""}`
            : syncedAt
              ? `synced ${formatRelative(syncedAt, now)}`
              : `not yet synced`}
      </span>
      <button
        onClick={() => void doSync(false)}
        disabled={syncing}
        title={`Re-fetch ${label} from server`}
        className="ml-1 rounded p-0.5 opacity-50 transition-opacity hover:opacity-100 disabled:opacity-20"
        aria-label={`Refresh ${label}`}
      >
        <RefreshCw className={`h-3 w-3 ${syncing ? "animate-spin" : ""}`} />
      </button>
    </div>
  );
}
