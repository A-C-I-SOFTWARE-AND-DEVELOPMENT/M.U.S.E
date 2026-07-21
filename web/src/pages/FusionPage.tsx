import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Anchor,
  Cpu,
  FlaskConical,
  Gauge,
  GitBranch,
  Layers,
  Loader2,
  Play,
  RefreshCw,
  RotateCcw,
  TrendingUp,
  Zap,
} from "lucide-react";
import { fetchJSON } from "@/lib/api";
import { cn } from "@/lib/utils";
import { usePageHeader } from "@/contexts/usePageHeader";
import { Markdown } from "@/components/Markdown";

/* ------------------------------------------------------------------ */
/* Types — mirror hermes_cli/web_fusion_api.py response shapes.        */
/* ------------------------------------------------------------------ */

interface FusionStatus {
  mode: string;
  active: boolean;
  reference_models: string[];
  aggregator_model: string;
  rounds: number;
  difficulty_aware: boolean;
  moe_routing: boolean;
  lti_stable: boolean;
  round_specialization: boolean;
  override: boolean | null;
  effective_active: boolean;
}

interface FusionRunResult {
  ok: boolean;
  prompt: string;
  fused_response: string;
  elapsed_seconds: number;
  council: {
    models: string[];
    aggregator: string;
    rounds: number;
    strategy: string;
    moe_query_type: string | null;
    moe_scores: Record<string, number> | null;
  };
  round_schedule: string[];
  mechanisms: {
    difficulty_aware: boolean;
    moe_routing: boolean;
    lti_stable: boolean;
    round_specialization: boolean;
  };
}

/* ------------------------------------------------------------------ */
/* The five Mythos-inspired mechanisms, explained compactly.           */
/* ------------------------------------------------------------------ */

const MECHANISMS: {
  name: string;
  analog: string;
  blurb: string;
  icon: typeof Gauge;
  flag: keyof FusionRunResult["mechanisms"] | null;
}[] = [
  {
    name: "ACT difficulty routing",
    analog: "Mythos ACT halting",
    blurb:
      "Easy queries halt early and skip fusion; hard queries get the full council. Compute is spent only where the problem earns it.",
    icon: Gauge,
    flag: "difficulty_aware",
  },
  {
    name: "MoE model routing",
    analog: "Mythos / DeepSeek-V3 mixture-of-experts",
    blurb:
      "Queries are classified by type — code, math, creative — and routed to the best-suited models, with load balancing so no provider is exhausted.",
    icon: GitBranch,
    flag: "moe_routing",
  },
  {
    name: "LTI-stable iterative fusion",
    analog: "Mythos LTI injection",
    blurb:
      "Multi-round fusion uses stability-weighted aggregation so responses can't drift — the recurrence is stable by construction, more rounds never make it worse.",
    icon: Anchor,
    flag: "lti_stable",
  },
  {
    name: "Per-round specialization",
    analog: "Mythos LoRA adapters",
    blurb:
      "Each fusion round gets its own system prompt — DIVERSE → SYNTHESIZE → VERIFY → POLISH — like adapters specializing a shared block at each depth.",
    icon: Layers,
    flag: "round_specialization",
  },
  {
    name: "Depth extrapolation",
    analog: "Mythos inference-time scaling",
    blurb:
      "Hard queries are given extra fusion rounds at inference time — the same trick as raising the loop count for harder problems.",
    icon: TrendingUp,
    flag: null,
  },
];

export default function FusionPage() {
  const [status, setStatus] = useState<FusionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState(false);

  const [prompt, setPrompt] = useState("");
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [result, setResult] = useState<FusionRunResult | null>(null);

  const { setTitle, setAfterTitle, setEnd } = usePageHeader();

  const fetchStatus = useCallback(async () => {
    setError(null);
    try {
      const s = await fetchJSON<FusionStatus>("/api/fusion/status");
      setStatus(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load fusion status");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchStatusRef = useRef(fetchStatus);
  fetchStatusRef.current = fetchStatus;

  // Sentence-case header + one-line description + refresh action (design 2.3).
  useLayoutEffect(() => {
    setTitle("Fusion");
    setAfterTitle(
      <span className="whitespace-nowrap text-xs text-[var(--fg-faint)]">
        Mixture-of-agents council with Mythos-inspired adaptive routing.
      </span>,
    );
    setEnd(
      <button
        type="button"
        onClick={() => void fetchStatusRef.current()}
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
    void fetchStatus();
  }, [fetchStatus]);

  const postOverride = useCallback(
    async (enabled: boolean | null) => {
      setToggling(true);
      setError(null);
      try {
        await fetchJSON<{ ok: boolean }>("/api/fusion/override", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled }),
        });
        await fetchStatus();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to set fusion override");
      } finally {
        setToggling(false);
      }
    },
    [fetchStatus],
  );

  const runCouncil = useCallback(async () => {
    const p = prompt.trim();
    if (!p || running) return;
    setRunning(true);
    setRunError(null);
    setResult(null);
    try {
      const r = await fetchJSON<FusionRunResult>("/api/fusion/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: p }),
      });
      setResult(r);
    } catch (e) {
      setRunError(e instanceof Error ? e.message : "Fusion run failed");
    } finally {
      setRunning(false);
    }
  }, [prompt, running]);

  const fusionOn = status?.effective_active ?? false;
  const overridden = status != null && status.override !== null;

  return (
    <div className="muse-fusion flex min-h-0 flex-1 flex-col overflow-hidden">
      {/* Inline error banner with retry (design 2.3) */}
      {error && (
        <div className="mb-3 flex shrink-0 items-center gap-2 rounded-xl border border-[var(--err)]/30 bg-[var(--err)]/5 px-3 py-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-[var(--err)]" />
          <span className="flex-1 text-xs text-[var(--err)]">{error}</span>
          <button
            type="button"
            onClick={() => void fetchStatus()}
            className="rounded-md border border-[var(--err)]/40 px-2 py-0.5 text-xs text-[var(--err)] transition-colors hover:bg-[var(--err)]/10"
          >
            Retry
          </button>
        </div>
      )}

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
        {/* Status + toggle row */}
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          {/* Enable/disable toggle card */}
          <div className="flex flex-col gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-elev)] p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="h-3.5 w-3.5 text-[var(--accent)]" />
                <span className="text-xs font-medium text-[var(--fg-dim)]">
                  Fusion mode
                </span>
              </div>
              {overridden && (
                <span className="rounded bg-[var(--accent)]/10 px-1.5 py-0.5 text-[0.65rem] text-[var(--accent)]">
                  override
                </span>
              )}
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                role="switch"
                aria-checked={fusionOn}
                disabled={toggling || loading || !status}
                onClick={() => void postOverride(!fusionOn)}
                className={cn(
                  "relative h-6 w-11 shrink-0 rounded-full border transition-colors disabled:opacity-50",
                  fusionOn
                    ? "border-[var(--accent)] bg-[var(--accent)]/25"
                    : "border-[var(--border)] bg-[var(--bg-mute)]",
                )}
              >
                <span
                  className={cn(
                    "absolute top-0.5 h-4.5 w-4.5 rounded-full transition-all",
                    fusionOn
                      ? "left-[1.4rem] bg-[var(--accent)]"
                      : "left-0.5 bg-[var(--fg-faint)]",
                  )}
                />
              </button>
              <span className="text-sm font-medium text-[var(--fg)]">
                {loading && !status
                  ? "Loading…"
                  : fusionOn
                    ? "Council active"
                    : "Single model"}
              </span>
            </div>

            <p className="text-xs leading-relaxed text-[var(--fg-faint)]">
              {overridden
                ? `Forced ${status.override ? "on" : "off"} for this process — config.yaml is being bypassed.`
                : "Following config.yaml. Toggling sets a process-level override."}
            </p>

            {overridden && (
              <button
                type="button"
                disabled={toggling}
                onClick={() => void postOverride(null)}
                className="inline-flex w-fit items-center gap-1.5 rounded-lg border border-[var(--border)] px-2 py-1 text-xs text-[var(--fg-dim)] transition-colors hover:bg-[var(--bg-mute)] hover:text-[var(--fg)] disabled:opacity-50"
              >
                <RotateCcw className="h-3 w-3" />
                Clear override
              </button>
            )}
          </div>

          {/* Status card */}
          <div className="flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-elev)] p-4">
            <div className="flex items-center gap-2">
              <Cpu className="h-3.5 w-3.5 text-[var(--fg-dim)]" />
              <span className="text-xs font-medium text-[var(--fg-dim)]">
                Pipeline status
              </span>
            </div>
            {loading && !status ? (
              <div className="flex animate-pulse flex-col gap-2 pt-1">
                <div className="h-3 w-40 rounded bg-[var(--bg-mute)]" />
                <div className="h-3 w-28 rounded bg-[var(--bg-mute)]" />
                <div className="h-3 w-32 rounded bg-[var(--bg-mute)]" />
              </div>
            ) : !status ? (
              <p className="pt-1 text-xs text-[var(--fg-faint)]">
                Status unavailable.
              </p>
            ) : (
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 pt-1 text-xs">
                <dt className="text-[var(--fg-faint)]">Mode</dt>
                <dd className="font-mono text-[var(--fg)]">{status.mode}</dd>
                <dt className="text-[var(--fg-faint)]">Rounds</dt>
                <dd className="font-mono text-[var(--fg)]">{status.rounds}</dd>
                <dt className="text-[var(--fg-faint)]">Aggregator</dt>
                <dd className="truncate font-mono text-[var(--fg)]">
                  {status.aggregator_model || "—"}
                </dd>
                <dt className="text-[var(--fg-faint)]">Mechanisms</dt>
                <dd className="flex flex-wrap gap-1">
                  {(
                    [
                      ["ACT", status.difficulty_aware],
                      ["MoE", status.moe_routing],
                      ["LTI", status.lti_stable],
                      ["Rounds", status.round_specialization],
                    ] as const
                  ).map(([label, on]) => (
                    <span
                      key={label}
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[0.65rem]",
                        on
                          ? "bg-[var(--ok)]/10 text-[var(--ok)]"
                          : "bg-[var(--bg-mute)] text-[var(--fg-faint)]",
                      )}
                    >
                      {label} {on ? "on" : "off"}
                    </span>
                  ))}
                </dd>
              </dl>
            )}
          </div>

          {/* Council card */}
          <div className="flex min-h-0 flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-elev)] p-4">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-[var(--fg-dim)]">
                Council
              </span>
              <span className="text-xs text-[var(--fg-faint)]">
                {status?.reference_models.length ?? 0} models
              </span>
            </div>
            <div className="flex min-h-0 flex-col gap-1 overflow-y-auto">
              {loading && !status ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-6 animate-pulse rounded bg-[var(--bg-mute)]"
                  />
                ))
              ) : !status || status.reference_models.length === 0 ? (
                <p className="py-2 text-xs text-[var(--fg-faint)]">
                  No reference models configured.
                </p>
              ) : (
                status.reference_models.map((m) => (
                  <div
                    key={m}
                    className="flex items-center justify-between gap-2 rounded-lg px-2 py-1 transition-colors hover:bg-[var(--bg-mute)]"
                  >
                    <span className="truncate font-mono text-xs text-[var(--fg)]">
                      {m}
                    </span>
                    {m === status.aggregator_model && (
                      <span className="shrink-0 rounded bg-[var(--accent)]/10 px-1.5 py-0.5 text-[0.65rem] text-[var(--accent)]">
                        aggregator
                      </span>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Mechanisms explainer */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-elev)]">
          <div className="flex items-center gap-2 border-b border-[var(--border)] px-3 py-2">
            <Layers className="h-3.5 w-3.5 text-[var(--accent)]" />
            <span className="text-xs font-medium text-[var(--fg-dim)]">
              Five Mythos-inspired mechanisms
            </span>
          </div>
          <div className="grid grid-cols-1 gap-2.5 p-3 sm:grid-cols-2 xl:grid-cols-5">
            {MECHANISMS.map((mech) => {
              const Icon = mech.icon;
              const enabled =
                mech.flag && status ? status[mech.flag] : null;
              return (
                <div
                  key={mech.name}
                  className="flex flex-col gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3 transition-colors hover:border-[var(--accent-dim)]"
                >
                  <div className="flex items-center justify-between gap-2">
                    <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--accent)]" />
                    {enabled !== null && (
                      <span
                        className={cn(
                          "rounded px-1 py-0.5 text-[0.6rem]",
                          enabled
                            ? "bg-[var(--ok)]/10 text-[var(--ok)]"
                            : "bg-[var(--bg-mute)] text-[var(--fg-faint)]",
                        )}
                      >
                        {enabled ? "on" : "off"}
                      </span>
                    )}
                  </div>
                  <span className="text-xs font-medium text-[var(--fg)]">
                    {mech.name}
                  </span>
                  <span className="text-[0.65rem] text-[var(--accent-dim)]">
                    {mech.analog}
                  </span>
                  <p className="text-[0.7rem] leading-relaxed text-[var(--fg-faint)]">
                    {mech.blurb}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Test-the-council console */}
        <div className="flex flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-elev)]">
          <div className="flex shrink-0 items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
            <div className="flex items-center gap-2">
              <FlaskConical className="h-3.5 w-3.5 text-[var(--accent)]" />
              <span className="text-xs font-medium text-[var(--fg-dim)]">
                Test the council
              </span>
            </div>
            <span className="text-[0.65rem] text-[var(--fg-faint)]">
              Runs synchronously — multi-round fusion can take minutes
            </span>
          </div>

          <div className="flex shrink-0 flex-col gap-2 border-b border-[var(--border)] p-3">
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  void runCouncil();
                }
              }}
              placeholder="Ask the council something hard — e.g. a design trade-off, a proof sketch, a gnarly refactor plan…"
              rows={3}
              disabled={running}
              className="w-full resize-y rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-faint)] focus:border-[var(--accent-dim)] focus:outline-hidden disabled:opacity-60"
            />
            <div className="flex items-center justify-between">
              <span className="text-[0.65rem] text-[var(--fg-faint)]">
                Ctrl/⌘ + Enter to run
              </span>
              <button
                type="button"
                disabled={running || !prompt.trim()}
                onClick={() => void runCouncil()}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--accent-dim)] bg-[var(--accent)]/10 px-3 py-1.5 text-xs font-medium text-[var(--accent)] transition-colors hover:bg-[var(--accent)]/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {running ? (
                  <>
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Fusing…
                  </>
                ) : (
                  <>
                    <Play className="h-3 w-3" />
                    Run council
                  </>
                )}
              </button>
            </div>
          </div>

          {runError && (
            <div className="flex shrink-0 items-center gap-2 border-b border-[var(--border)] bg-[var(--err)]/5 px-3 py-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-[var(--err)]" />
              <span className="text-xs text-[var(--err)]">{runError}</span>
            </div>
          )}

          {result && (
            <div className="flex min-h-0 flex-col">
              {/* Council detail */}
              <div className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-[var(--border)] px-3 py-2 text-[0.65rem] text-[var(--fg-faint)]">
                <span>
                  elapsed{" "}
                  <span className="font-mono text-[var(--fg-dim)]">
                    {result.elapsed_seconds}s
                  </span>
                </span>
                <span>
                  models{" "}
                  <span className="font-mono text-[var(--fg-dim)]">
                    {result.council.models.length}
                  </span>
                </span>
                <span>
                  rounds{" "}
                  <span className="font-mono text-[var(--fg-dim)]">
                    {result.council.rounds}
                  </span>
                </span>
                {result.council.moe_query_type && (
                  <span>
                    query type{" "}
                    <span className="font-mono text-[var(--accent)]">
                      {result.council.moe_query_type}
                    </span>
                  </span>
                )}
                <span className="flex items-center gap-1">
                  {result.round_schedule.map((role, i) => (
                    <span key={i} className="flex items-center gap-1">
                      {i > 0 && <span>→</span>}
                      <span className="rounded bg-[var(--bg-mute)] px-1 py-0.5 font-mono text-[var(--fg-dim)]">
                        {role}
                      </span>
                    </span>
                  ))}
                </span>
              </div>

              {/* Models used */}
              <div className="flex shrink-0 flex-wrap gap-1.5 border-b border-[var(--border)] px-3 py-2">
                {result.council.models.map((m) => (
                  <span
                    key={m}
                    className={cn(
                      "rounded-lg border px-2 py-0.5 font-mono text-[0.65rem]",
                      m === result.council.aggregator
                        ? "border-[var(--accent-dim)] bg-[var(--accent)]/10 text-[var(--accent)]"
                        : "border-[var(--border)] text-[var(--fg-dim)]",
                    )}
                    title={
                      result.council.moe_scores?.[m] != null
                        ? `MoE score ${result.council.moe_scores[m]}`
                        : undefined
                    }
                  >
                    {m}
                    {m === result.council.aggregator && " · agg"}
                  </span>
                ))}
              </div>

              {/* Fused output */}
              <div className="min-h-0 max-h-[28rem] overflow-y-auto p-3">
                <Markdown content={result.fused_response} />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="shrink-0 pb-1">
          <span className="text-[0.65rem] text-[var(--fg-faint)]">
            muse fusion routes each request through a mixture-of-agents council
            — depth and membership adapt to the difficulty of the query.
          </span>
        </div>
      </div>
    </div>
  );
}
