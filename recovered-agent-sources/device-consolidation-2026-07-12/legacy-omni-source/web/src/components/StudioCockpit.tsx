/**
 * StudioCockpit — Pure React cockpit replacing the demo-data iframe.
 *
 * All data is live from Hermes APIs. No demo/fake content.
 * Renders a real-time dashboard: system status, model info,
 * sessions, skills, cron, logs, plugins — everything the user
 * would want at a glance.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  FileText,
  Clock,
  Terminal,
  Package,
  Puzzle,
  Zap,
  CircleDot,
  ChevronRight,
  Cpu,
} from "lucide-react";
import { cn } from "@/lib/utils";

/* ── Types ── */

interface StatusData {
  version: string;
  gateway_running: boolean;
  active_sessions: number;
  config_path: string;
  hermes_home: string;
  gateway_state?: string;
}

interface SessionItem {
  id: string;
  title?: string;
  model?: string;
  message_count?: number;
  created_at?: string;
  source?: string;
}

interface SkillItem {
  name: string;
  description?: string;
  enabled: boolean;
  category?: string | null;
}

interface CronJob {
  id: string;
  name?: string;
  schedule?: string;
  enabled?: boolean;
  next_run?: string;
}

interface ModelInfo {
  model: string;
  provider: string;
  effective_context_length?: number;
}

interface LogData {
  file: string;
  lines: string[];
}

interface PluginItem {
  name: string;
  label: string;
  description?: string;
  icon?: string;
  version?: string;
}

/* ── API helper ── */

const SESSION_TOKEN =
  typeof window !== "undefined"
    ? (window as unknown as Record<string, unknown>).__HERMES_SESSION_TOKEN__ as string
    : "";

async function apiFetch<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(path, {
      headers: { Authorization: `Bearer ${SESSION_TOKEN}` },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

/* ── Main Component ── */

export default function StudioCockpit() {
  const [status, setStatus] = useState<StatusData | null>(null);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [cronJobs, setCronJobs] = useState<CronJob[]>([]);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [plugins, setPlugins] = useState<PluginItem[]>([]);
  const [logs, setLogs] = useState<LogData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [activePanel, setActivePanel] = useState<
    "overview" | "sessions" | "skills" | "logs"
  >("overview");

  const fetchAll = useCallback(async () => {
    try {
      const [s, sess, sk, cron, mi, pl, lg] = await Promise.all([
        apiFetch<StatusData>("/api/status"),
        apiFetch<SessionItem[]>("/api/sessions"),
        apiFetch<SkillItem[]>("/api/skills"),
        apiFetch<CronJob[]>("/api/cron/jobs"),
        apiFetch<ModelInfo>("/api/model/info"),
        apiFetch<PluginItem[]>("/api/dashboard/plugins"),
        apiFetch<LogData>("/api/logs?limit=30"),
      ]);
      setStatus(s);
      setSessions(Array.isArray(sess) ? sess : []);
      setSkills(Array.isArray(sk) ? sk : []);
      setCronJobs(Array.isArray(cron) ? cron : []);
      setModelInfo(mi);
      setPlugins(Array.isArray(pl) ? pl : []);
      setLogs(lg);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30_000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const activeSkills = useMemo(
    () => skills.filter((s) => s.enabled).length,
    [skills],
  );
  const enabledCron = useMemo(
    () => cronJobs.filter((j) => j.enabled).length,
    [cronJobs],
  );
  const recentSessions = useMemo(
    () => sessions.slice(0, 8),
    [sessions],
  );
  const topSkills = useMemo(
    () => skills.filter((s) => s.enabled).slice(0, 10),
    [skills],
  );
  const logLines = useMemo(
    () => (logs?.lines ?? []).slice(-25),
    [logs],
  );

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center bg-[#050507]">
        <div className="flex flex-col items-center gap-4">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-500/20 border-t-cyan-400" />
          <span className="text-xs uppercase tracking-widest text-zinc-600">
            Initializing Studio
          </span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center bg-[#050507]">
        <div className="flex flex-col items-center gap-3 text-center">
          <AlertTriangle className="h-8 w-8 text-amber-400/60" />
          <span className="text-sm text-zinc-400">
            Failed to load studio data
          </span>
          <button
            onClick={fetchAll}
            className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-xs text-zinc-300 hover:bg-white/10"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[#050507] text-zinc-300">
      {/* ── Header ── */}
      <header className="flex shrink-0 items-center justify-between border-b border-white/[0.04] px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold tracking-tight text-zinc-100">
            MUSE Studio
          </span>
          <span className="hidden text-[0.65rem] uppercase tracking-widest text-zinc-600 sm:inline">
            Multi-Use Synaptic Entity
          </span>
        </div>
        <div className="flex items-center gap-3">
          <StatusPill
            live={status?.gateway_running ?? false}
            label={status?.gateway_running ? "Live" : "Stopped"}
          />
          {modelInfo && (
            <div className="hidden items-center gap-1.5 rounded-full border border-white/[0.06] bg-white/[0.02] px-3 py-1 sm:flex">
              <Cpu className="h-3 w-3 text-cyan-400/60" />
              <span className="text-[0.65rem] font-medium text-zinc-400">
                {modelInfo.model?.split("/").pop()}
              </span>
              {modelInfo.effective_context_length && (
                <span className="text-[0.55rem] text-zinc-600">
                  {(modelInfo.effective_context_length / 1000).toFixed(0)}k ctx
                </span>
              )}
            </div>
          )}
          {status?.version && (
            <span className="text-[0.6rem] text-zinc-700">
              v{status.version}
            </span>
          )}
        </div>
      </header>

      {/* ── Panel tabs ── */}
      <div className="flex shrink-0 items-center gap-1 border-b border-white/[0.04] px-4 sm:px-6">
        {(
          [
            ["overview", "Overview"],
            ["sessions", `Sessions (${sessions.length})`],
            ["skills", `Skills (${activeSkills}/${skills.length})`],
            ["logs", "Logs"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setActivePanel(key)}
            className={cn(
              "border-b-2 px-3 py-2.5 text-[0.7rem] font-semibold uppercase tracking-wider transition-colors",
              activePanel === key
                ? "border-cyan-400 text-zinc-100"
                : "border-transparent text-zinc-600 hover:text-zinc-400",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── Scrollable content ── */}
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6">
        {activePanel === "overview" && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            <MetricCard
              label="Active Sessions"
              value={status?.active_sessions ?? 0}
              icon={Activity}
              accent="cyan"
            />
            <MetricCard
              label="Total Sessions"
              value={sessions.length}
              icon={Terminal}
              accent="blue"
            />
            <MetricCard
              label="Skills Active"
              value={`${activeSkills}/${skills.length}`}
              icon={Package}
              accent="emerald"
            />
            <MetricCard
              label="Cron Jobs"
              value={`${enabledCron}/${cronJobs.length}`}
              icon={Clock}
              accent="amber"
            />
            <MetricCard
              label="Plugins"
              value={plugins.length}
              icon={Puzzle}
              accent="violet"
            />
            <MetricCard
              label="Model"
              value={modelInfo?.model?.split("/").pop() ?? "—"}
              icon={Cpu}
              accent="cyan"
            />
            <MetricCard
              label="Gateway"
              value={status?.gateway_running ? "Online" : "Offline"}
              icon={CircleDot}
              accent={status?.gateway_running ? "emerald" : "red"}
            />
            <MetricCard
              label="Context"
              value={
                modelInfo?.effective_context_length
                  ? `${(modelInfo.effective_context_length / 1000).toFixed(0)}k`
                  : "—"
              }
              icon={Zap}
              accent="amber"
            />
          </div>
        )}

        {activePanel === "sessions" && (
          <div className="space-y-1">
            {recentSessions.length === 0 ? (
              <EmptyState
                icon={Terminal}
                message="No sessions yet. Start a chat to begin."
              />
            ) : (
              recentSessions.map((s) => (
                <a
                  key={s.id}
                  href={`/chat?resume=${s.id}`}
                  className="group flex items-center gap-3 rounded-lg border border-transparent bg-white/[0.015] px-3 py-2.5 transition-all hover:border-white/10 hover:bg-white/[0.04]"
                >
                  <Activity className="h-3.5 w-3.5 shrink-0 text-zinc-600" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-xs font-medium text-zinc-300">
                      {s.title || "Untitled Session"}
                    </div>
                    <div className="text-[0.6rem] text-zinc-600">
                      {s.source || "cli"} · {s.message_count ?? 0} msgs
                    </div>
                  </div>
                  {s.model && (
                    <span className="shrink-0 rounded-full bg-white/[0.04] px-2 py-0.5 text-[0.55rem] text-zinc-500">
                      {s.model.split("/").pop()}
                    </span>
                  )}
                  <ChevronRight className="h-3.5 w-3.5 shrink-0 text-zinc-700 transition-colors group-hover:text-zinc-500" />
                </a>
              ))
            )}
          </div>
        )}

        {activePanel === "skills" && (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {topSkills.length === 0 ? (
              <EmptyState
                icon={Package}
                message="No skills installed."
              />
            ) : (
              topSkills.map((sk) => (
                <div
                  key={sk.name}
                  className="rounded-lg border border-white/[0.04] bg-white/[0.015] px-3 py-2.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="truncate text-xs font-medium text-zinc-300">
                      {sk.name}
                    </span>
                    <span
                      className={cn(
                        "h-1.5 w-1.5 rounded-full",
                        sk.enabled ? "bg-emerald-400" : "bg-zinc-700",
                      )}
                    />
                  </div>
                  {sk.description && (
                    <p className="mt-0.5 line-clamp-2 text-[0.6rem] leading-relaxed text-zinc-600">
                      {sk.description}
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {activePanel === "logs" && (
          <div className="overflow-hidden rounded-lg border border-white/[0.04] bg-black/40">
            {logLines.length === 0 ? (
              <EmptyState icon={FileText} message="No logs available." />
            ) : (
              logLines.map((line, i) => (
                <div
                  key={i}
                  className="truncate border-b border-white/[0.02] px-3 py-1.5 font-mono text-[0.62rem] leading-relaxed text-zinc-500 last:border-0"
                >
                  {line.trim().slice(0, 140)}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* ── Footer status ── */}
      <footer className="flex shrink-0 items-center justify-between border-t border-white/[0.04] px-4 py-2 sm:px-6">
        <div className="flex items-center gap-3 text-[0.6rem] text-zinc-700">
          <span className="flex items-center gap-1">
            <CircleDot
              className={cn(
                "h-2.5 w-2.5",
                status?.gateway_running ? "text-emerald-400" : "text-zinc-600",
              )}
            />
            {status?.gateway_state ?? "unknown"}
          </span>
          <span>·</span>
          <span>{status?.active_sessions ?? 0} active</span>
          <span className="hidden sm:inline">·</span>
          <span className="hidden sm:inline">
            {status?.hermes_home ?? ""}
          </span>
        </div>
        <span className="text-[0.55rem] text-zinc-700">
          Auto-refresh 30s
        </span>
      </footer>
    </div>
  );
}

/* ── Sub-components ── */

const ACCENT_MAP: Record<
  string,
  { icon: string; glow: string }
> = {
  cyan: { icon: "text-cyan-400/70", glow: "shadow-cyan-500/5" },
  blue: { icon: "text-blue-400/70", glow: "shadow-blue-500/5" },
  emerald: { icon: "text-emerald-400/70", glow: "shadow-emerald-500/5" },
  amber: { icon: "text-amber-400/70", glow: "shadow-amber-500/5" },
  violet: { icon: "text-violet-400/70", glow: "shadow-violet-500/5" },
  red: { icon: "text-red-400/70", glow: "shadow-red-500/5" },
};

function MetricCard({
  label,
  value,
  icon: Icon,
  accent,
}: {
  label: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
}) {
  const a = ACCENT_MAP[accent] ?? ACCENT_MAP.cyan;
  return (
    <div
      className={cn(
        "flex flex-col gap-2 rounded-xl border border-white/[0.04] bg-white/[0.015] p-3.5 shadow-lg",
        a.glow,
        "transition-all hover:border-white/10 hover:bg-white/[0.03]",
      )}
    >
      <div className="flex items-center gap-2">
        <Icon className={cn("h-3.5 w-3.5", a.icon)} />
        <span className="text-[0.55rem] font-semibold uppercase tracking-widest text-zinc-600">
          {label}
        </span>
      </div>
      <span className="text-xl font-bold tabular-nums text-zinc-200">
        {value}
      </span>
    </div>
  );
}

function StatusPill({ live, label }: { live: boolean; label: string }) {
  return (
    <div
      className={cn(
        "flex items-center gap-1.5 rounded-full border px-2.5 py-1",
        live
          ? "border-emerald-400/20 bg-emerald-500/5"
          : "border-zinc-500/20 bg-zinc-500/5",
      )}
    >
      <CircleDot
        className={cn(
          "h-2.5 w-2.5",
          live ? "text-emerald-400" : "text-zinc-500",
        )}
      />
      <span
        className={cn(
          "text-[0.6rem] font-semibold uppercase tracking-wider",
          live ? "text-emerald-400/80" : "text-zinc-500",
        )}
      >
        {label}
      </span>
    </div>
  );
}

function EmptyState({
  icon: Icon,
  message,
}: {
  icon: React.ComponentType<{ className?: string }>;
  message: string;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-12 text-center">
      <Icon className="h-6 w-6 text-zinc-700" />
      <span className="text-xs text-zinc-600">{message}</span>
    </div>
  );
}
