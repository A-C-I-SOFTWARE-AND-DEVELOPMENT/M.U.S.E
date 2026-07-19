import {
  useEffect,
  useLayoutEffect,
  useState,
  useCallback,
  useRef,
} from "react";
import { FileText, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { FilterGroup, Segmented } from "@nous-research/ui/ui/components/segmented";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Switch } from "@nous-research/ui/ui/components/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyStateCard } from "@/components/EmptyStateCard";
import { Label } from "@/components/ui/label";
import { useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";
import { PluginSlot } from "@/plugins";

const FILES = ["agent", "errors", "gateway"] as const;
const LEVELS = ["ALL", "DEBUG", "INFO", "WARNING", "ERROR"] as const;
const COMPONENTS = ["all", "gateway", "agent", "tools", "cli", "cron"] as const;
const LINE_COUNTS = [50, 100, 200, 500] as const;

type Severity = "error" | "warning" | "info" | "debug";

function classifyLine(line: string): Severity {
  const upper = line.toUpperCase();
  if (
    upper.includes("ERROR") ||
    upper.includes("CRITICAL") ||
    upper.includes("FATAL")
  )
    return "error";
  if (upper.includes("WARNING") || upper.includes("WARN")) return "warning";
  if (upper.includes("DEBUG")) return "debug";
  return "info";
}

/** Level-colored severity chip tones, routed through Singularity tokens. */
const CHIP_STYLES: Record<Severity, string> = {
  error: "border-[var(--err)]/40 bg-[var(--err)]/10 text-[var(--err)]",
  warning: "border-[var(--warn)]/40 bg-[var(--warn)]/10 text-[var(--warn)]",
  info: "border-[var(--info)]/40 bg-[var(--info)]/10 text-[var(--info)]",
  debug: "border-[var(--border)] bg-[var(--bg-mute)] text-[var(--fg-faint)]",
};

const CHIP_LABELS: Record<Severity, string> = {
  error: "err",
  warning: "warn",
  info: "info",
  debug: "debug",
};

const LINE_COLORS: Record<Severity, string> = {
  error: "text-[var(--err)]",
  warning: "text-[var(--fg)]",
  info: "text-[var(--fg-dim)]",
  debug: "text-[var(--fg-faint)]",
};

const toOptions = <T extends string>(values: readonly T[]) =>
  values.map((v) => ({ value: v, label: v }));

const filterGroupClass =
  "flex min-w-0 w-full flex-col items-start gap-1.5 sm:w-auto sm:max-w-full sm:flex-row sm:items-center";

const segmentedClass =
  "w-fit max-w-full flex-wrap justify-start self-start";

export default function LogsPage() {
  const [file, setFile] = useState<(typeof FILES)[number]>("agent");
  const [level, setLevel] = useState<(typeof LEVELS)[number]>("ALL");
  const [component, setComponent] =
    useState<(typeof COMPONENTS)[number]>("all");
  const [lineCount, setLineCount] = useState<(typeof LINE_COUNTS)[number]>(100);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lines, setLines] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { t } = useI18n();
  const { setAfterTitle, setEnd } = usePageHeader();

  const fetchLogs = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .getLogs({ file, lines: lineCount, level, component })
      .then((resp) => {
        setLines(resp.lines);
        setTimeout(() => {
          if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
          }
        }, 50);
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [file, lineCount, level, component]);

  useLayoutEffect(() => {
    setAfterTitle(
      <span className="flex items-center gap-2">
        {loading && <Spinner className="shrink-0 text-base text-[var(--accent)]" />}
        <Badge tone="secondary" className="text-[10px]">
          {file} · {level} · {component}
        </Badge>
      </span>,
    );
    setEnd(
      <div className="flex w-full min-w-0 flex-wrap items-center justify-start gap-2 sm:gap-3">
        <div className="flex items-center gap-2">
          <Switch
            checked={autoRefresh}
            onCheckedChange={setAutoRefresh}
            id="logs-auto-refresh"
          />
          <Label htmlFor="logs-auto-refresh" className="text-xs cursor-pointer">
            {t.logs.autoRefresh}
          </Label>
          {autoRefresh && (
            <Badge tone="success" className="text-[10px]">
              <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
              {t.common.live}
            </Badge>
          )}
        </div>
        <Button
          type="button"
          size="sm"
          outlined
          onClick={fetchLogs}
          disabled={loading}
          prefix={loading ? <Spinner /> : <RefreshCw />}
        >
          {t.common.refresh}
        </Button>
      </div>,
    );
    return () => {
      setAfterTitle(null);
      setEnd(null);
    };
  }, [
    autoRefresh,
    component,
    file,
    level,
    loading,
    setAfterTitle,
    setEnd,
    t.common.live,
    t.common.refresh,
    t.logs.autoRefresh,
    fetchLogs,
  ]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, fetchLogs]);

  return (
    <div className="flex min-w-0 max-w-full flex-col gap-4">
      <PluginSlot name="logs:top" />

      <p className="text-sm text-[var(--fg-dim)]">
        Tail agent, error, and gateway logs with live filters.
      </p>

      <div
        role="toolbar"
        aria-label={t.logs.title}
        className="flex min-w-0 max-w-full flex-col items-start gap-3 sm:flex-row sm:flex-wrap sm:items-start sm:gap-x-6 sm:gap-y-3"
      >
        <FilterGroup label={t.logs.file} className={filterGroupClass}>
          <Segmented
            className={segmentedClass}
            value={file}
            onChange={setFile}
            options={toOptions(FILES)}
          />
        </FilterGroup>

        <FilterGroup label={t.logs.level} className={filterGroupClass}>
          <Segmented
            className={segmentedClass}
            value={level}
            onChange={setLevel}
            options={toOptions(LEVELS)}
          />
        </FilterGroup>

        <FilterGroup label={t.logs.component} className={filterGroupClass}>
          <Segmented
            className={segmentedClass}
            value={component}
            onChange={setComponent}
            options={toOptions(COMPONENTS)}
          />
        </FilterGroup>

        <FilterGroup label={t.logs.lines} className={filterGroupClass}>
          <Segmented
            className={segmentedClass}
            value={String(lineCount)}
            onChange={(v) =>
              setLineCount(Number(v) as (typeof LINE_COUNTS)[number])
            }
            options={LINE_COUNTS.map((n) => ({
              value: String(n),
              label: String(n),
            }))}
          />
        </FilterGroup>
      </div>

      <Card className="min-w-0 max-w-full overflow-hidden rounded-xl bg-[var(--bg-elev)]">
        <CardHeader className="px-4 py-3">
          <CardTitle className="flex items-center gap-2 font-mono text-sm normal-case tracking-normal">
            <FileText className="h-4 w-4 text-[var(--fg-dim)]" />
            {file}.log
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {error && (
            <div className="border-b border-[var(--err)]/30 bg-[var(--err)]/10 p-3">
              <p className="text-sm text-[var(--err)]">{error}</p>
            </div>
          )}

          <div
            ref={scrollRef}
            className="max-h-[calc(100vh-220px)] min-h-[400px] max-w-full overflow-auto p-4 font-mono text-xs leading-5 break-words"
          >
            {lines.length === 0 && !loading && (
              <EmptyStateCard
                icon={FileText}
                title={t.logs.noLogLines}
                className="border-transparent bg-transparent"
              />
            )}
            {lines.map((line, i) => {
              const sev = classifyLine(line);
              return (
                <div
                  key={i}
                  className="-mx-1 flex items-baseline gap-2 px-1 hover:bg-[var(--bg-mute)]/60"
                >
                  <span
                    className={`inline-block w-12 shrink-0 rounded border px-1 text-center text-[9px] leading-4 ${CHIP_STYLES[sev]}`}
                  >
                    {CHIP_LABELS[sev]}
                  </span>
                  <span className={`min-w-0 ${LINE_COLORS[sev]}`}>{line}</span>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
      <PluginSlot name="logs:bottom" />
    </div>
  );
}
