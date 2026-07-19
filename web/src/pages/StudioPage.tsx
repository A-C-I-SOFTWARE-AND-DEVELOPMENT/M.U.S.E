import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  Package,
  RefreshCw,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import type { CronJob, SkillInfo } from "@/lib/api";
import { cn } from "@/lib/utils";
import { usePageHeader } from "@/contexts/usePageHeader";

interface SystemStat {
  label: string;
  value: string | number;
  icon: typeof Activity;
  accent?: string;
}

/**
 * Display metadata for known creative skills, keyed by skill name.
 * The authoritative skill list comes from `api.getSkills()` — this map only
 * supplies emoji/tag decoration. (Previously a flat array with duplicate
 * entries for `claude-design` and `baoyu-article-illustrator`; the Map
 * dedupes by construction.)
 */
const CREATIVE_SKILL_META = new Map<string, { emoji: string; tag: string }>(
  [
    { name: "comfyui",                   emoji: "🎨", tag: "image/video/audio" },
    { name: "baoyu-article-illustrator", emoji: "🖼️", tag: "article images"   },
    { name: "baoyu-comic",               emoji: "📖", tag: "knowledge comics" },
    { name: "baoyu-infographic",         emoji: "📊", tag: "infographics"     },
    { name: "excalidraw",                emoji: "✏️", tag: "diagrams"         },
    { name: "claude-design",             emoji: "🎭", tag: "html artifacts"   },
    { name: "architecture-diagram",      emoji: "🏗️", tag: "infra diagrams"   },
    { name: "manim-video",               emoji: "🎬", tag: "math animations"  },
    { name: "ascii-video",               emoji: "🟢", tag: "ascii movies"     },
    { name: "ascii-art",                 emoji: "🔡", tag: "ascii art"        },
    { name: "pixel-art",                 emoji: "👾", tag: "pixel sprites"    },
    { name: "p5js",                      emoji: "✨", tag: "gen art"          },
    { name: "ideation",                  emoji: "💡", tag: "creative prompts" },
    { name: "design-md",                 emoji: "📐", tag: "design tokens"    },
    { name: "popular-web-designs",       emoji: "🌐", tag: "web layouts"      },
    { name: "songsee",                   emoji: "🎵", tag: "audio analysis"   },
    { name: "heartmula",                 emoji: "🎤", tag: "music gen"        },
    { name: "songwriting-and-ai-music",  emoji: "🎼", tag: "songwriting"      },
    { name: "tts",                       emoji: "🗣️", tag: "voice synthesis"  },
  ].map((s) => [s.name, { emoji: s.emoji, tag: s.tag }]),
);

function scheduleDisplay(job: CronJob): string {
  return (
    job.schedule_display ||
    job.schedule?.display ||
    job.schedule?.expr ||
    "—"
  );
}

export default function StudioPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<SystemStat[]>([]);
  const [cronJobs, setCronJobs] = useState<CronJob[]>([]);
  const [model, setModel] = useState<{ id: string; provider?: string } | null>(
    null,
  );
  const [sessionCount, setSessionCount] = useState(0);
  const [creativeSkills, setCreativeSkills] = useState<SkillInfo[]>([]);
  const [creativeFilter, setCreativeFilter] = useState("");
  const { setTitle, setAfterTitle, setEnd } = usePageHeader();

  const fetchData = useCallback(async () => {
    setError(null);
    try {
      const [statusRes, sessionsRes, cronRes, modelRes, skillsRes] =
        await Promise.allSettled([
          api.getStatus(),
          api.getSessions(1, 0),
          api.getCronJobs(),
          api.getModelInfo(),
          api.getSkills(),
        ]);

      const newStats: SystemStat[] = [];

      if (statusRes.status === "fulfilled") {
        const s = statusRes.value as unknown as Record<string, unknown>;
        newStats.push({
          label: "Status",
          value: s.running ? "Operational" : "Idle",
          icon: CheckCircle2,
          accent: s.running ? "text-[var(--ok)]" : "text-[var(--warn)]",
        });
      }

      if (sessionsRes.status === "fulfilled") {
        const total = (sessionsRes.value as { total?: number })?.total ?? 0;
        setSessionCount(total);
        newStats.push({
          label: "Sessions",
          value: total,
          icon: Database,
          accent: "text-[var(--info)]",
        });
      }

      if (cronRes.status === "fulfilled") {
        // FIX: api.getCronJobs() returns a plain CronJob[] array, NOT
        // `{ jobs }` — the old code read `.jobs` off the array and always
        // rendered an empty panel.
        const jobs = Array.isArray(cronRes.value) ? cronRes.value : [];
        setCronJobs(jobs);
        const active = jobs.filter((j) => j.enabled).length;
        newStats.push({
          label: "Active cron",
          value: `${active}/${jobs.length}`,
          icon: Clock,
          accent: "text-[var(--accent)]",
        });
      }

      if (modelRes.status === "fulfilled") {
        const info = modelRes.value;
        setModel({ id: info.model ?? "unknown", provider: info.provider });
        newStats.push({
          label: "Provider",
          value: info.provider ?? "unknown",
          icon: Cpu,
          accent: "text-[var(--info)]",
        });
      }

      if (skillsRes.status === "fulfilled") {
        const allSkills = Array.isArray(skillsRes.value) ? skillsRes.value : [];
        // Creative skills: real data from the skills API, decorated with the
        // (deduped) hardcoded metadata map. Some creative skills are filed
        // under other categories (media, mlops…), hence the name check.
        const creative = allSkills.filter(
          (s) => s.category === "creative" || CREATIVE_SKILL_META.has(s.name),
        );
        setCreativeSkills(creative);
        newStats.push({
          label: "Skills",
          value: allSkills.length,
          icon: Package,
          accent: "text-[var(--warn)]",
        });
      }

      if (newStats.length === 0) {
        setError("Failed to load studio data");
      }
      setStats(newStats);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load studio data");
    } finally {
      setLoading(false);
    }
  }, []);

  // Lets the header refresh button call the latest fetchData.
  const fetchDataRef = useRef(fetchData);
  fetchDataRef.current = fetchData;

  // Sentence-case header + one-line description + refresh action (design 2.3).
  useLayoutEffect(() => {
    setTitle("Studio");
    setAfterTitle(
      <span className="whitespace-nowrap text-xs text-[var(--fg-faint)]">
        Mission control — status, skills, models, and scheduled jobs at a glance.
      </span>,
    );
    setEnd(
      <button
        type="button"
        onClick={() => void fetchDataRef.current()}
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg-elev)] px-2.5 py-1 text-xs text-[var(--fg-dim)] transition-colors hover:bg-[var(--bg-mute)] hover:text-[var(--fg)]"
      >
        <RefreshCw className="h-3 w-3" />
        Refresh
      </button>,
    );
    return () => {
      setTitle(null);
      setAfterTitle(null);
      setEnd(null);
    };
  }, [setTitle, setAfterTitle, setEnd]);

  useEffect(() => {
    void fetchData();
    const interval = setInterval(() => void fetchData(), 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const filter = creativeFilter.toLowerCase().trim();
  const visibleSkills = creativeSkills
    .filter(
      (s) =>
        !filter ||
        s.name.includes(filter) ||
        s.description.toLowerCase().includes(filter),
    )
    .slice(0, 24);

  return (
    <div className="muse-studio flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* Inline error banner with retry (design 2.3) */}
      {error && (
        <div className="mb-3 flex shrink-0 items-center gap-2 rounded-xl border border-[var(--err)]/30 bg-[var(--err)]/5 px-3 py-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-[var(--err)]" />
          <span className="flex-1 text-xs text-[var(--err)]">{error}</span>
          <button
            type="button"
            onClick={() => void fetchData()}
            className="rounded-md border border-[var(--err)]/40 px-2 py-0.5 text-xs text-[var(--err)] transition-colors hover:bg-[var(--err)]/10"
          >
            Retry
          </button>
        </div>
      )}

      {/* Stats grid */}
      <div className="grid shrink-0 grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {loading && stats.length === 0
          ? Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="flex animate-pulse flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-elev)] p-3"
              >
                <div className="h-4 w-4 rounded bg-[var(--bg-mute)]" />
                <div className="h-6 w-16 rounded bg-[var(--bg-mute)]" />
                <div className="h-3 w-12 rounded bg-[var(--bg-mute)]" />
              </div>
            ))
          : stats.map((stat) => {
              const Icon = stat.icon;
              return (
                <div
                  key={stat.label}
                  className="flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-elev)] p-3 transition-colors hover:border-[var(--accent-dim)]"
                >
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0",
                      stat.accent ?? "text-[var(--fg-dim)]",
                    )}
                  />
                  <span className="text-xl leading-none font-semibold text-[var(--fg)]">
                    {stat.value}
                  </span>
                  <span className="text-xs text-[var(--fg-faint)]">
                    {stat.label}
                  </span>
                </div>
              );
            })}
      </div>

      {/* Creative tools panel */}
      <div className="mt-4 flex min-h-0 shrink-0 flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-elev)]">
        <div className="flex shrink-0 items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
          <div className="flex items-center gap-2">
            <Zap className="h-3.5 w-3.5 text-[var(--accent)]" />
            <span className="text-xs font-medium text-[var(--fg-dim)]">
              Creative tools
            </span>
            <span className="text-xs text-[var(--fg-faint)]">
              {creativeSkills.length} available ·{" "}
              {creativeSkills.filter((s) => s.enabled).length} enabled
            </span>
          </div>
          <input
            type="text"
            placeholder="Filter…"
            value={creativeFilter}
            onChange={(e) => setCreativeFilter(e.target.value)}
            className="w-36 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-xs text-[var(--fg)] placeholder:text-[var(--fg-faint)] focus:border-[var(--accent-dim)] focus:outline-hidden"
          />
        </div>

        <div className="flex flex-wrap gap-1.5 p-2.5">
          {loading && creativeSkills.length === 0 ? (
            Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="h-6 w-24 animate-pulse rounded bg-[var(--bg-mute)]"
              />
            ))
          ) : visibleSkills.length === 0 ? (
            <span className="px-2 py-2 text-xs text-[var(--fg-faint)]">
              No creative skills match — browse all installed skills on the
              Skills page.
            </span>
          ) : (
            visibleSkills.map((s) => {
              const meta = CREATIVE_SKILL_META.get(s.name);
              return (
                // NOTE: these used to link to `/chat?prefill=…`, but ChatPage
                // never reads `prefill` — the links were dead. Wiring prefill
                // would require edits to App.tsx/ChatPage (outside this
                // agent's ownership), so the chips now route to the Skills
                // page instead (design 2.3 StudioPage directive).
                <a
                  key={s.name}
                  href="/skills"
                  title={s.description}
                  className="group flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-xs transition-colors hover:border-[var(--accent-dim)] hover:bg-[var(--bg-mute)]"
                >
                  <span className="opacity-70">{meta?.emoji ?? "🛠️"}</span>
                  <span className="font-medium text-[var(--fg-dim)] group-hover:text-[var(--fg)]">
                    {s.name}
                  </span>
                  {meta?.tag && (
                    <span className="text-[0.65rem] text-[var(--fg-faint)]">
                      · {meta.tag}
                    </span>
                  )}
                  {!s.enabled && (
                    <span className="ml-1 rounded bg-[var(--bg-mute)] px-1 py-0.5 text-[0.6rem] text-[var(--fg-faint)]">
                      off
                    </span>
                  )}
                </a>
              );
            })
          )}
        </div>

        <div className="flex shrink-0 items-center justify-between border-t border-[var(--border)] px-3 py-1.5">
          <span className="text-[0.65rem] text-[var(--fg-faint)]">
            Invoke any skill by typing its name in Chat
          </span>
          <a
            href="/skills"
            className="text-[0.65rem] text-[var(--fg-dim)] transition-colors hover:text-[var(--accent)]"
          >
            All skills →
          </a>
        </div>
      </div>

      {/* Detail panels */}
      <div className="mt-4 grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-hidden lg:grid-cols-2">
        {/* Model panel */}
        <div className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-elev)]">
          <div className="flex shrink-0 items-center gap-2 border-b border-[var(--border)] px-3 py-2">
            <Cpu className="h-3.5 w-3.5 text-[var(--fg-dim)]" />
            <span className="text-xs font-medium text-[var(--fg-dim)]">
              Active model
            </span>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-2">
            {loading && !model ? (
              <div className="flex animate-pulse items-center gap-2 px-2 py-1.5">
                <div className="h-3 w-3 rounded bg-[var(--bg-mute)]" />
                <div className="h-3 w-40 rounded bg-[var(--bg-mute)]" />
              </div>
            ) : !model ? (
              <p className="px-2 py-4 text-center text-xs text-[var(--fg-faint)]">
                No model configured
              </p>
            ) : (
              <div className="flex items-center justify-between rounded-lg px-2 py-1.5 transition-colors hover:bg-[var(--bg-mute)]">
                <div className="flex items-center gap-2">
                  <Zap className="h-3 w-3 text-[var(--info)]" />
                  <span className="font-mono text-xs text-[var(--fg)]">
                    {model.id}
                  </span>
                </div>
                {model.provider && (
                  <span className="text-xs text-[var(--fg-faint)]">
                    {model.provider}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Cron jobs panel */}
        <div className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-elev)]">
          <div className="flex shrink-0 items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
            <div className="flex items-center gap-2">
              <Clock className="h-3.5 w-3.5 text-[var(--fg-dim)]" />
              <span className="text-xs font-medium text-[var(--fg-dim)]">
                Scheduled jobs
              </span>
            </div>
            <a
              href="/cron"
              className="text-[0.65rem] text-[var(--fg-faint)] transition-colors hover:text-[var(--accent)]"
            >
              Manage →
            </a>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-2">
            {loading && cronJobs.length === 0 ? (
              Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="flex animate-pulse items-center gap-2 px-2 py-2"
                >
                  <div className="h-1.5 w-1.5 rounded-full bg-[var(--bg-mute)]" />
                  <div className="h-3 w-32 rounded bg-[var(--bg-mute)]" />
                </div>
              ))
            ) : cronJobs.length === 0 ? (
              <p className="px-2 py-4 text-center text-xs text-[var(--fg-faint)]">
                No cron jobs configured
              </p>
            ) : (
              cronJobs.map((job) => (
                <div
                  key={`${job.profile ?? job.profile_name ?? "default"}:${job.id}`}
                  className="flex items-center justify-between rounded-lg px-2 py-1.5 transition-colors hover:bg-[var(--bg-mute)]"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <div
                      className={cn(
                        "h-1.5 w-1.5 shrink-0 rounded-full",
                        job.enabled
                          ? "bg-[var(--ok)]"
                          : "bg-[var(--fg-faint)]",
                      )}
                    />
                    <span className="truncate text-xs text-[var(--fg)]">
                      {job.name || job.prompt?.slice(0, 40) || job.id}
                    </span>
                  </div>
                  <span className="shrink-0 font-mono text-[0.65rem] text-[var(--fg-faint)]">
                    {scheduleDisplay(job)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="shrink-0 pt-3">
        <div className="flex items-center justify-between">
          <span className="text-[0.65rem] text-[var(--fg-faint)]">
            Auto-refreshing every 30s · {sessionCount} total sessions
          </span>
          <button
            type="button"
            onClick={() => void fetchData()}
            className="flex items-center gap-1 text-xs text-[var(--fg-faint)] transition-colors hover:text-[var(--fg-dim)]"
          >
            <Activity className="h-3 w-3" />
            Refresh
          </button>
        </div>
      </div>
    </div>
  );
}
