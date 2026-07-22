import { useState } from "react";
import { Link } from "react-router-dom";
import { fetchJSON } from "@/lib/api";
import {
  formatRelativeTime,
  normalizeNdStatus,
  useNightdeskOverview,
} from "./useNightdesk";
import type { NightdeskAutomation } from "./useNightdesk";
import "./nightdesk.css";

// ---------------------------------------------------------------------------
// Night Desk — Overview · Scheduled automations card
// data.automations → cron jobs across all profiles, via the shared
// useNightdeskOverview poller. Rows: name, schedule_display → deliver,
// last run (relative), last_status chip, next run, and a working
// pause/resume toggle (POST /api/cron/jobs/{id}/pause|resume → refresh()).
// Paused rows dim. Empty state links to /cron. No fabricated jobs.
// ---------------------------------------------------------------------------

/** Rows shown before the "+N more · /cron" overflow link (mockup density). */
const MAX_ROWS = 5;

/**
 * The hook types cron timestamps as unix seconds (number | null); some cron
 * profiles still serialize ISO-8601 strings. Accept both, return unix secs.
 */
function toEpoch(value: number | string | null | undefined): number | null {
  if (value == null) return null;
  if (typeof value === "number") {
    return Number.isFinite(value) && value > 0 ? value : null;
  }
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? null : ms / 1000;
}

/** Future-relative "in 45m / in 2h / in 3d" — 'due' when the time has passed. */
function formatNextRun(value: number | string | null | undefined): string {
  const ts = toEpoch(value);
  if (!ts) return "—";
  const delta = ts - Date.now() / 1000;
  if (delta <= 0) return "due";
  if (delta < 60) return "soon";
  if (delta < 3600) return `in ${Math.max(1, Math.round(delta / 60))}m`;
  if (delta < 86400) return `in ${Math.round(delta / 3600)}h`;
  return `in ${Math.round(delta / 86400)}d`;
}

function EnabledSwitch({
  job,
  pending,
  onToggle,
}: {
  job: NightdeskAutomation;
  pending: boolean;
  onToggle: (job: NightdeskAutomation) => void;
}) {
  const on = job.enabled;
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={`${on ? "Pause" : "Resume"} automation ${job.name}`}
      title={on ? "pause" : "resume"}
      disabled={pending}
      onClick={() => onToggle(job)}
      className="relative h-[16px] w-[30px] flex-none cursor-pointer rounded-full border transition-colors disabled:cursor-wait disabled:opacity-60"
      style={{
        borderColor: on
          ? "color-mix(in srgb, var(--nd-online) 45%, transparent)"
          : "var(--nd-hairline)",
        background: on
          ? "color-mix(in srgb, var(--nd-online) 18%, transparent)"
          : "var(--nd-panel-2)",
      }}
    >
      <span
        aria-hidden="true"
        className="absolute left-[2px] top-[2px] h-[10px] w-[10px] rounded-full transition-transform duration-150"
        style={{
          transform: on ? "translateX(14px)" : "translateX(0)",
          background: on ? "var(--nd-online)" : "var(--nd-fg-faint)",
        }}
      />
    </button>
  );
}

function AutomationRow({
  job,
  pending,
  onToggle,
}: {
  job: NightdeskAutomation;
  pending: boolean;
  onToggle: (job: NightdeskAutomation) => void;
}) {
  const lastRel = formatRelativeTime(toEpoch(job.last_run_at));
  const nextRel = job.enabled ? `next ${formatNextRun(job.next_run_at)}` : "paused";
  return (
    <li className="flex min-h-[44px] items-center gap-3 border-b border-white/[0.05] py-1.5 last:border-b-0">
      <div
        className={`min-w-0 flex-1 transition-opacity ${job.enabled ? "" : "opacity-40"}`}
      >
        <div className="truncate text-[12px] font-medium text-white/85">
          {job.name || job.id}
        </div>
        <div className="mt-0.5 truncate font-mono text-[10px] text-white/35">
          {job.schedule_display ?? "—"} → {job.deliver ?? "local"} · last {lastRel} ·{" "}
          {nextRel}
        </div>
      </div>
      <span
        className="nd-chip flex-none"
        data-status={normalizeNdStatus(job.last_status)}
      >
        {job.last_status ?? "never"}
      </span>
      <EnabledSwitch job={job} pending={pending} onToggle={onToggle} />
    </li>
  );
}

function SkeletonRows() {
  return (
    <div aria-hidden="true">
      {Array.from({ length: 3 }, (_, i) => (
        <div
          key={i}
          className="flex min-h-[44px] items-center gap-3 border-b border-white/[0.05] last:border-b-0"
        >
          <div className="min-w-0 flex-1">
            <div className="h-2.5 w-1/2 animate-pulse rounded-full bg-white/[0.06]" />
            <div className="mt-1.5 h-2 w-3/4 animate-pulse rounded-full bg-white/[0.04]" />
          </div>
          <div className="h-4 w-12 flex-none animate-pulse rounded-full bg-white/[0.05]" />
        </div>
      ))}
    </div>
  );
}

export default function AutomationsCard() {
  const { data, error, loading, refresh } = useNightdeskOverview();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const jobs = data?.automations;
  const list = jobs ?? [];
  const live = list.filter((j) => j.enabled).length;
  const shown = list.slice(0, MAX_ROWS);
  const overflow = list.length - shown.length;

  const toggle = (job: NightdeskAutomation) => {
    if (pendingId) return;
    setPendingId(job.id);
    setActionError(null);
    const action = job.enabled ? "pause" : "resume";
    fetchJSON(`/api/cron/jobs/${encodeURIComponent(job.id)}/${action}`, {
      method: "POST",
    })
      .then(() => {
        refresh();
      })
      .catch((e: unknown) => {
        setActionError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        setPendingId(null);
      });
  };

  return (
    <section className="nd-panel flex flex-col">
      <header className="nd-panel-head">
        <div className="min-w-0">
          <h2 className="nd-label">Scheduled automations</h2>
          <p className="nd-sub mt-0.5">
            Natural-language cron · delivered anywhere
          </p>
        </div>
        {jobs && (
          <span className="nd-num flex-none text-[11px] text-white/40">
            {live} live · {list.length} total
          </span>
        )}
      </header>

      <div className="nd-panel-body flex-1">
        {loading && !jobs ? (
          <SkeletonRows />
        ) : error && !jobs ? (
          <div className="nd-empty">
            <p>automations unavailable — {error}</p>
            <button type="button" className="nd-button mt-3" onClick={refresh}>
              retry
            </button>
          </div>
        ) : list.length === 0 ? (
          <div className="nd-empty">
            no automations yet — create one with{" "}
            <Link
              to="/cron"
              className="font-mono text-violet-400 transition-colors hover:text-violet-300"
            >
              /cron
            </Link>
          </div>
        ) : (
          <>
            <ul>
              {shown.map((job) => (
                <AutomationRow
                  key={job.id}
                  job={job}
                  pending={pendingId === job.id}
                  onToggle={toggle}
                />
              ))}
            </ul>
            {overflow > 0 && (
              <Link
                to="/cron"
                className="mt-2 block text-center font-mono text-[10px] text-white/30 transition-colors hover:text-white/60"
              >
                +{overflow} more · /cron
              </Link>
            )}
            {actionError && (
              <p className="mt-2 font-mono text-[10px] text-[var(--nd-degraded)]">
                toggle failed — {actionError}
              </p>
            )}
          </>
        )}
      </div>
    </section>
  );
}
