import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  BarChart3,
  Brain,
  Cpu,
  RefreshCw,
  TrendingUp,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  AnalyticsResponse,
  AnalyticsDailyEntry,
  AnalyticsModelEntry,
  AnalyticsSkillEntry,
} from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Stats } from "@nous-research/ui/ui/components/stats";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Meter, Spark } from "@/components/ui/meter";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { usePageHeader } from "@/contexts/usePageHeader";
import { useI18n } from "@/i18n";
import { PluginSlot } from "@/plugins";

const PERIODS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
] as const;

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatDate(day: string): string {
  try {
    const d = new Date(day + "T00:00:00");
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return day;
  }
}

// ---------------------------------------------------------------------------
// Sorting
// ---------------------------------------------------------------------------

function useTableSort<T>(
  data: T[],
  defaultKey: keyof T & string,
  defaultDir: "asc" | "desc" = "desc",
) {
  const [sortKey, setSortKey] = useState<string>(defaultKey);
  const [sortDir, setSortDir] = useState<"asc" | "desc">(defaultDir);

  const sorted = useMemo(() => {
    return [...data].sort((a, b) => {
      const aVal = a[sortKey as keyof T];
      const bVal = b[sortKey as keyof T];
      // Nulls always last regardless of direction
      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;
      if (aVal === bVal) return 0;
      const cmp = aVal > bVal ? 1 : -1;
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [data, sortKey, sortDir]);

  const toggle = useCallback(
    (key: string) => {
      if (key === sortKey) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir("desc");
      }
    },
    [sortKey],
  );

  return { sorted, sortKey, sortDir, toggle };
}

function SortHeader({
  label,
  col,
  sortKey,
  sortDir,
  toggle,
  className,
}: {
  label: string;
  col: string;
  sortKey: string;
  sortDir: "asc" | "desc";
  toggle: (key: string) => void;
  className?: string;
}) {
  const active = col === sortKey;
  return (
    <th
      onClick={() => toggle(col)}
      className={`cursor-pointer select-none ${className ?? ""}`}
    >
      <span className="inline-flex items-center gap-1.5 rounded px-1 -mx-1 py-0.5 transition-colors hover:bg-[var(--bg-mute)]">
        {label}
        {active ? (
          sortDir === "asc" ? (
            <ArrowUp className="h-3.5 w-3.5 shrink-0 text-[var(--fg)]/80" />
          ) : (
            <ArrowDown className="h-3.5 w-3.5 shrink-0 text-[var(--fg)]/80" />
          )
        ) : (
          <ArrowUpDown className="h-3 w-3 shrink-0 text-[var(--fg-faint)]" />
        )}
      </span>
    </th>
  );
}

/** Section card header: sentence-case title + one-line description (design 2.3). */
function SectionHeader({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof BarChart3;
  title: string;
  description: string;
}) {
  return (
    <CardHeader>
      <div className="flex items-center gap-2">
        <Icon className="h-5 w-5 text-[var(--fg-dim)]" />
        <CardTitle className="text-base normal-case tracking-normal">
          {title}
        </CardTitle>
      </div>
      <p className="text-xs text-[var(--fg-dim)]">{description}</p>
    </CardHeader>
  );
}

/** Daily usage chart built from the shared Spark primitive (accent = input, ok = output). */
function DailyUsageChart({ daily }: { daily: AnalyticsDailyEntry[] }) {
  const { t } = useI18n();
  if (daily.length === 0) return null;

  const inputSeries = daily.map((d) => d.input_tokens);
  const outputSeries = daily.map((d) => d.output_tokens);
  const totalInput = inputSeries.reduce((s, v) => s + v, 0);
  const totalOutput = outputSeries.reduce((s, v) => s + v, 0);

  return (
    <Card className="rounded-xl">
      <SectionHeader
        icon={BarChart3}
        title={t.analytics.dailyTokenUsage}
        description="Tokens processed per day, split into input and output."
      />
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-2 text-xs">
            <span className="flex items-center gap-1.5 text-[var(--fg-dim)]">
              <span className="h-2 w-2 rounded-[1px] bg-[var(--accent)]" />
              {t.analytics.input}
            </span>
            <span className="tabular-nums text-[var(--fg-faint)]">
              {formatTokens(totalInput)}
            </span>
          </div>
          <Spark values={inputSeries} color="accent" className="h-16" />
        </div>
        <div className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-2 text-xs">
            <span className="flex items-center gap-1.5 text-[var(--fg-dim)]">
              <span className="h-2 w-2 rounded-[1px] bg-[var(--ok)]" />
              {t.analytics.output}
            </span>
            <span className="tabular-nums text-[var(--fg-faint)]">
              {formatTokens(totalOutput)}
            </span>
          </div>
          <Spark values={outputSeries} color="ok" className="h-16" />
        </div>

        <div className="flex justify-between text-[10px] text-[var(--fg-faint)]">
          <span>{daily.length > 0 ? formatDate(daily[0].day) : ""}</span>
          {daily.length > 2 && (
            <span>{formatDate(daily[Math.floor(daily.length / 2)].day)}</span>
          )}
          <span>
            {daily.length > 1 ? formatDate(daily[daily.length - 1].day) : ""}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

function DailyTable({ daily }: { daily: AnalyticsDailyEntry[] }) {
  const { t } = useI18n();
  const { sorted, sortKey, sortDir, toggle } = useTableSort(daily, "day", "desc");

  if (daily.length === 0) return null;

  const maxTotal = Math.max(
    ...daily.map((d) => d.input_tokens + d.output_tokens),
    1,
  );

  return (
    <Card className="rounded-xl">
      <SectionHeader
        icon={TrendingUp}
        title={t.analytics.dailyBreakdown}
        description="Per-day session counts and token totals, with relative volume."
      />
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-xs text-[var(--fg-dim)]">
                <SortHeader label={t.analytics.date} col="day" sortKey={sortKey} sortDir={sortDir} toggle={toggle} className="py-2 pr-4 text-left font-medium" />
                <SortHeader label={t.sessions.title} col="sessions" sortKey={sortKey} sortDir={sortDir} toggle={toggle} className="px-4 py-2 text-right font-medium" />
                <SortHeader label={t.analytics.input} col="input_tokens" sortKey={sortKey} sortDir={sortDir} toggle={toggle} className="px-4 py-2 text-right font-medium" />
                <SortHeader label={t.analytics.output} col="output_tokens" sortKey={sortKey} sortDir={sortDir} toggle={toggle} className="py-2 pl-4 text-right font-medium" />
                <th className="hidden w-40 py-2 pl-4 text-left font-medium sm:table-cell" />
              </tr>
            </thead>
            <tbody>
              {sorted.map((d) => {
                const total = d.input_tokens + d.output_tokens;
                return (
                  <tr
                    key={d.day}
                    className="border-b border-[var(--border)]/50 transition-colors hover:bg-[var(--bg-mute)]/50"
                  >
                    <td className="py-2 pr-4 font-medium text-[var(--fg)]">
                      {formatDate(d.day)}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-[var(--fg-dim)]">
                      {d.sessions}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      <span className="text-[var(--accent)]">
                        {formatTokens(d.input_tokens)}
                      </span>
                    </td>
                    <td className="py-2 pl-4 text-right tabular-nums">
                      <span className="text-[var(--ok)]">
                        {formatTokens(d.output_tokens)}
                      </span>
                    </td>
                    <td className="hidden py-2 pl-4 sm:table-cell">
                      <Meter value={total} max={maxTotal} color="accent" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function ModelTable({ models }: { models: AnalyticsModelEntry[] }) {
  const { t } = useI18n();
  const { sorted, sortKey, sortDir, toggle } = useTableSort(models, "input_tokens", "desc");

  if (models.length === 0) return null;

  const maxTokens = Math.max(
    ...models.map((m) => m.input_tokens + m.output_tokens),
    1,
  );

  return (
    <Card className="rounded-xl">
      <SectionHeader
        icon={Cpu}
        title={t.analytics.perModelBreakdown}
        description="Token share per model across the selected period."
      />
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-xs text-[var(--fg-dim)]">
                <SortHeader label={t.analytics.model} col="model" sortKey={sortKey} sortDir={sortDir} toggle={toggle} className="py-2 pr-4 text-left font-medium" />
                <SortHeader label={t.sessions.title} col="sessions" sortKey={sortKey} sortDir={sortDir} toggle={toggle} className="px-4 py-2 text-right font-medium" />
                <SortHeader label={t.analytics.tokens} col="input_tokens" sortKey={sortKey} sortDir={sortDir} toggle={toggle} className="py-2 pl-4 text-right font-medium" />
                <th className="hidden w-40 py-2 pl-4 text-left font-medium sm:table-cell" />
              </tr>
            </thead>
            <tbody>
              {sorted.map((m) => {
                const total = m.input_tokens + m.output_tokens;
                return (
                  <tr
                    key={m.model}
                    className="border-b border-[var(--border)]/50 transition-colors hover:bg-[var(--bg-mute)]/50"
                  >
                    <td className="py-2 pr-4">
                      <span className="font-mono text-xs text-[var(--fg)]">
                        {m.model}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-[var(--fg-dim)]">
                      {m.sessions}
                    </td>
                    <td className="py-2 pl-4 text-right tabular-nums">
                      <span className="text-[var(--accent)]">
                        {formatTokens(m.input_tokens)}
                      </span>
                      <span className="text-[var(--fg-faint)]"> / </span>
                      <span className="text-[var(--ok)]">
                        {formatTokens(m.output_tokens)}
                      </span>
                    </td>
                    <td className="hidden py-2 pl-4 sm:table-cell">
                      <Meter value={total} max={maxTokens} color="info" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function SkillTable({ skills }: { skills: AnalyticsSkillEntry[] }) {
  const { t } = useI18n();
  const { sorted, sortKey, sortDir, toggle } = useTableSort(skills, "total_count", "desc");

  if (skills.length === 0) return null;

  const maxCount = Math.max(...skills.map((s) => s.total_count), 1);

  return (
    <Card className="rounded-xl">
      <SectionHeader
        icon={Brain}
        title={t.analytics.topSkills}
        description="Most-loaded skills, ranked by total invocations."
      />
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-xs text-[var(--fg-dim)]">
                <SortHeader label={t.analytics.skill} col="skill" sortKey={sortKey} sortDir={sortDir} toggle={toggle} className="py-2 pr-4 text-left font-medium" />
                <SortHeader label={t.analytics.loads} col="view_count" sortKey={sortKey} sortDir={sortDir} toggle={toggle} className="px-4 py-2 text-right font-medium" />
                <SortHeader label={t.analytics.edits} col="manage_count" sortKey={sortKey} sortDir={sortDir} toggle={toggle} className="px-4 py-2 text-right font-medium" />
                <SortHeader label={t.analytics.total} col="total_count" sortKey={sortKey} sortDir={sortDir} toggle={toggle} className="px-4 py-2 text-right font-medium" />
                <SortHeader label={t.analytics.lastUsed} col="last_used_at" sortKey={sortKey} sortDir={sortDir} toggle={toggle} className="py-2 pl-4 text-right font-medium" />
                <th className="hidden w-40 py-2 pl-4 text-left font-medium sm:table-cell" />
              </tr>
            </thead>
            <tbody>
              {sorted.map((skill) => (
                <tr
                  key={skill.skill}
                  className="border-b border-[var(--border)]/50 transition-colors hover:bg-[var(--bg-mute)]/50"
                >
                  <td className="py-2 pr-4">
                    <span className="font-mono text-xs text-[var(--fg)]">
                      {skill.skill}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-[var(--fg-dim)]">
                    {skill.view_count}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-[var(--fg-dim)]">
                    {skill.manage_count}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-[var(--fg)]">
                    {skill.total_count}
                  </td>
                  <td className="py-2 pl-4 text-right text-[var(--fg-dim)]">
                    {skill.last_used_at ? timeAgo(skill.last_used_at) : "—"}
                  </td>
                  <td className="hidden py-2 pl-4 sm:table-cell">
                    <Meter value={skill.total_count} max={maxCount} color="ok" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Gated on `dashboard.show_token_analytics` (default off).  When off the
  // page renders an explanation card instead of fetching analytics — the
  // local token counts exclude auxiliary calls and provider retries, so
  // they diverge from provider billing in ways that mislead users.
  const [showTokens, setShowTokens] = useState<boolean | null>(null);
  const { t } = useI18n();
  const { setAfterTitle, setEnd } = usePageHeader();

  useEffect(() => {
    api
      .getConfig()
      .then((cfg) => {
        const dash = (cfg?.dashboard ?? {}) as { show_token_analytics?: unknown };
        setShowTokens(dash.show_token_analytics === true);
      })
      .catch(() => setShowTokens(false));
  }, []);

  const load = useCallback(() => {
    if (!showTokens) return;
    setLoading(true);
    setError(null);
    api
      .getAnalytics(days)
      .then(setData)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [days, showTokens]);

  useLayoutEffect(() => {
    const periodLabel =
      PERIODS.find((p) => p.days === days)?.label ?? `${days}d`;
    setAfterTitle(
      <span className="flex items-center gap-2">
        {loading && <Spinner className="shrink-0 text-base text-[var(--accent)]" />}
        <Badge tone="secondary" className="text-[10px]">
          {periodLabel}
        </Badge>
      </span>,
    );
    setEnd(
      showTokens === false ? null : (
        <div className="flex w-full min-w-0 flex-wrap items-center justify-start gap-2 sm:gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            {PERIODS.map((p) => (
              <Button
                key={p.label}
                type="button"
                size="sm"
                outlined={days !== p.days}
                onClick={() => setDays(p.days)}
              >
                {p.label}
              </Button>
            ))}
          </div>
          <Button
            type="button"
            size="sm"
            outlined
            onClick={load}
            disabled={loading}
            prefix={loading ? <Spinner /> : <RefreshCw />}
          >
            {t.common.refresh}
          </Button>
        </div>
      ),
    );
    return () => {
      setAfterTitle(null);
      setEnd(null);
    };
  }, [days, loading, load, setAfterTitle, setEnd, t.common.refresh, showTokens]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="flex flex-col gap-6">
      <PluginSlot name="analytics:top" />

      {showTokens === false && (
        <Card className="rounded-xl">
          <CardContent className="py-12">
            <div className="mx-auto flex max-w-2xl flex-col gap-3 text-sm text-[var(--fg-dim)]">
              <h2 className="font-display text-base tracking-wide text-[var(--fg)]">
                Token analytics hidden
              </h2>
              <p>
                The token, cost, and per-day analytics on this page are a
                local debug estimate. They only count successful main-agent
                responses with a usable <span className="font-mono">usage</span>{" "}
                block, and silently exclude auxiliary calls (context
                compression, title generation, vision, session search, web
                extract, smart approvals, MCP routing, plugin LLM access)
                plus provider-side retries and fallback attempts. Cache
                writes are missing entirely.
              </p>
              <p>
                On models with heavy auxiliary traffic (Kimi K2.6, MiniMax
                M2.7) the local total can be 10x–100x lower than what your
                provider bills. Hiding these numbers is safer than letting
                them look authoritative.
              </p>
              <p>
                Check your provider dashboard (OpenRouter, Anthropic, etc.)
                for actual usage and billing. To re-enable the local debug
                estimate anyway, set{" "}
                <span className="font-mono">
                  dashboard.show_token_analytics: true
                </span>{" "}
                in{" "}
                <a href="/config" className="text-[var(--accent)] underline">
                  Config
                </a>
                .
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {showTokens && (
        <p className="text-sm text-[var(--fg-dim)]">
          Token usage and activity across your sessions, models, and skills.
        </p>
      )}

      {showTokens && loading && !data && (
        <div className="flex items-center justify-center py-24">
          <Spinner className="text-2xl text-[var(--accent)]" />
        </div>
      )}

      {showTokens && error && (
        <Card className="rounded-xl">
          <CardContent className="py-6">
            <p className="text-center text-sm text-[var(--err)]">{error}</p>
          </CardContent>
        </Card>
      )}

      {showTokens && data && (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card className="rounded-xl">
              <CardContent className="py-6">
                <Stats
                  items={[
                    {
                      label: t.analytics.totalTokens,
                      value: formatTokens(
                        data.totals.total_input + data.totals.total_output,
                      ),
                    },
                    {
                      label: t.analytics.input,
                      value: formatTokens(data.totals.total_input),
                    },
                    {
                      label: t.analytics.output,
                      value: formatTokens(data.totals.total_output),
                    },
                    {
                      label: t.analytics.totalSessions,
                      value: `${data.totals.total_sessions} (~${(data.totals.total_sessions / days).toFixed(1)}${t.analytics.perDayAvg})`,
                    },
                    {
                      label: t.analytics.apiCalls,
                      value: String(
                        data.totals.total_api_calls ??
                          data.daily.reduce((sum, d) => sum + d.sessions, 0),
                      ),
                    },
                  ]}
                />
              </CardContent>
            </Card>

            <DailyUsageChart daily={data.daily} />
          </div>

          <DailyTable daily={data.daily} />
          <ModelTable models={data.by_model} />
          <SkillTable skills={data.skills.top_skills} />
        </>
      )}

      {data &&
        data.daily.length === 0 &&
        data.by_model.length === 0 &&
        data.skills.top_skills.length === 0 && (
          <Card className="rounded-xl">
            <CardContent className="py-12">
              <div className="flex flex-col items-center text-[var(--fg-dim)]">
                <BarChart3 className="mb-3 h-8 w-8 opacity-40" />
                <p className="text-sm font-medium">{t.analytics.noUsageData}</p>
                <p className="mt-1 text-xs text-[var(--fg-faint)]">
                  {t.analytics.startSession}
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      <PluginSlot name="analytics:bottom" />
    </div>
  );
}
