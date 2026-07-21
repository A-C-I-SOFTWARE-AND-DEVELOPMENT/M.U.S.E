import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  Loader2,
  Minus,
  Play,
  Plus,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { fetchJSON } from "@/lib/api";
import { Markdown } from "@/components/Markdown";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { usePageHeader } from "@/contexts/usePageHeader";

/* ------------------------------------------------------------------ */
/*  Types — mirror hermes_cli/web_moa_api.py                            */
/* ------------------------------------------------------------------ */

interface MoaStatus {
  requirements_met: boolean;
  requirements: Array<{ env_var: string; present: boolean; url: string }>;
  toolset: {
    name: string;
    default_off: boolean | null;
    enabled: boolean | null;
    configured: boolean | null;
  };
  configuration: {
    reference_models: string[];
    aggregator_model: string;
    max_concurrent_requests: number;
    max_rounds: number;
  };
  defaults: {
    strategy: string;
    strategies: string[];
    rounds: number;
    reference_models: string[];
    aggregator_model: string;
    max_rounds: number;
  };
}

interface MoaLane {
  model: string;
  content: string;
  ok: boolean;
}

interface MoaRound {
  round: number;
  responses: MoaLane[];
  fused: string | null;
}

interface MoaRunResult {
  success: boolean;
  prompt: string;
  strategy: string;
  aggregator_model: string | null;
  rounds: MoaRound[];
  fused_output: string;
  failed_models: string[];
  elapsed_seconds: number;
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function MoaPage() {
  const { setTitle, setAfterTitle, setEnd } = usePageHeader();

  const [status, setStatus] = useState<MoaStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);

  // Council builder state
  const [modelPool, setModelPool] = useState<string[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [customModel, setCustomModel] = useState("");
  const [rounds, setRounds] = useState(1);
  const [strategy, setStrategy] = useState<"parallel" | "single">("parallel");
  const [aggregator, setAggregator] = useState("");
  const [prompt, setPrompt] = useState("");

  // Run console state
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [result, setResult] = useState<MoaRunResult | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<number | null>(null);

  const loadStatus = useCallback(() => {
    setStatusLoading(true);
    setStatusError(null);
    fetchJSON<MoaStatus>("/api/moa/status")
      .then((s) => {
        setStatus(s);
        setModelPool((pool) => {
          const merged = new Set([...s.defaults.reference_models, ...pool]);
          return Array.from(merged);
        });
        setSelected((sel) =>
          sel.size === 0
            ? new Set(s.defaults.reference_models)
            : sel,
        );
        setAggregator((a) => a || s.defaults.aggregator_model);
        setRounds((r) => (r === 1 ? s.defaults.rounds : r));
      })
      .catch((e: Error) => setStatusError(e.message))
      .finally(() => setStatusLoading(false));
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  // Sentence-case header + description (design 2.3).
  useLayoutEffect(() => {
    setTitle("Mixture of agents");
    setAfterTitle(
      <span className="whitespace-nowrap text-xs text-[var(--fg-faint)]">
        Poll a council of frontier models and fuse their answers into one.
      </span>,
    );
    setEnd(
      <Button size="sm" onClick={loadStatus}>
        <RefreshCw className="h-3 w-3" />
        Refresh
      </Button>,
    );
    return () => {
      setTitle(null);
      setAfterTitle(null);
      setEnd(null);
    };
  }, [setTitle, setAfterTitle, setEnd, loadStatus]);

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) window.clearInterval(timerRef.current);
    };
  }, []);

  const maxRounds = status?.defaults.max_rounds ?? 5;
  const requirementsMet = status?.requirements_met ?? false;

  const toggleModel = (model: string) => {
    setSelected((sel) => {
      const next = new Set(sel);
      if (next.has(model)) next.delete(model);
      else next.add(model);
      return next;
    });
  };

  const addCustomModel = () => {
    const slug = customModel.trim();
    if (!slug) return;
    setModelPool((pool) => (pool.includes(slug) ? pool : [...pool, slug]));
    setSelected((sel) => new Set(sel).add(slug));
    setCustomModel("");
  };

  const canRun =
    !running && requirementsMet && prompt.trim().length > 0 && selected.size > 0;

  const runCouncil = () => {
    if (!canRun) return;
    setRunning(true);
    setRunError(null);
    setResult(null);
    setElapsed(0);
    const started = Date.now();
    timerRef.current = window.setInterval(() => {
      setElapsed((Date.now() - started) / 1000);
    }, 200);

    fetchJSON<MoaRunResult>("/api/moa/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: prompt.trim(),
        models: Array.from(selected),
        rounds,
        strategy,
        aggregator: aggregator.trim() || undefined,
      }),
    })
      .then(setResult)
      .catch((e: Error) => setRunError(e.message))
      .finally(() => {
        if (timerRef.current !== null) {
          window.clearInterval(timerRef.current);
          timerRef.current = null;
        }
        setElapsed((Date.now() - started) / 1000);
        setRunning(false);
      });
  };

  return (
    <div className="flex flex-col gap-6">
      {/* ------------------------------------------------ requirements banner */}
      {statusLoading ? (
        <div className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-elev)] px-4 py-3 text-sm text-[var(--fg-dim)]">
          <Loader2 className="h-4 w-4 animate-spin" />
          Checking MoA requirements…
        </div>
      ) : statusError ? (
        <Banner
          tone="err"
          icon={<AlertTriangle className="h-4 w-4" />}
          title="Could not reach the MoA API"
          body={statusError}
        />
      ) : status && !requirementsMet ? (
        <Banner
          tone="warn"
          icon={<AlertTriangle className="h-4 w-4" />}
          title="OpenRouter API key missing"
          body={
            <>
              MoA dispatches every council member through OpenRouter, but{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                OPENROUTER_API_KEY
              </code>{" "}
              is not set. Add it on the{" "}
              <Link to="/env" className="underline underline-offset-2">
                Keys page
              </Link>{" "}
              or in ~/.hermes/.env, then refresh.
            </>
          }
        />
      ) : status ? (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-[var(--ok)]/40 bg-[var(--ok)]/10 px-4 py-3 text-sm text-[var(--ok)]">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            OpenRouter key present
          </span>
          {status.toolset.enabled === false && (
            <span className="text-xs text-[var(--fg-dim)]">
              Note: the moa toolset is off by default for the agent itself —
              this page talks to the council directly and works regardless.
            </span>
          )}
        </div>
      ) : null}

      {/* ---------------------------------------------------- council builder */}
      <section className="rounded-lg border border-[var(--border)] bg-[var(--bg-elev)] p-4">
        <h2 className="mb-4 flex items-center gap-2 text-base text-[var(--fg)]">
          <Brain className="h-4 w-4 text-[var(--accent)]" />
          Council builder
        </h2>

        <div className="grid gap-4">
          {/* reference models */}
          <div className="grid gap-2">
            <Label>Reference models</Label>
            <div className="grid gap-1.5 sm:grid-cols-2">
              {modelPool.map((m) => (
                <Checkbox
                  key={m}
                  id={`moa-model-${m}`}
                  checked={selected.has(m)}
                  onChange={() => toggleModel(m)}
                  label={
                    <span className="font-mono text-xs text-[var(--fg)]">{m}</span>
                  }
                />
              ))}
            </div>
            <div className="flex gap-2">
              <Input
                placeholder="Add an OpenRouter slug, e.g. x-ai/grok-4"
                value={customModel}
                onChange={(e) => setCustomModel(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") addCustomModel();
                }}
                className="font-mono text-xs"
              />
              <Button
                size="sm"
                outlined
                onClick={addCustomModel}
                disabled={!customModel.trim()}
              >
                <Plus className="h-3 w-3" />
                Add
              </Button>
            </div>
            <p className="text-xs text-[var(--fg-faint)]">
              {selected.size} selected — pick models from different families for
              maximum diversity.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {/* strategy */}
            <div className="grid gap-2">
              <Label>Strategy</Label>
              <div className="flex rounded-lg border border-[var(--border)] p-0.5">
                {(["parallel", "single"] as const).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setStrategy(s)}
                    className={`flex-1 rounded-md px-3 py-1.5 text-xs transition-colors ${
                      strategy === s
                        ? "bg-[var(--bg-mute)] text-[var(--fg)]"
                        : "text-[var(--fg-dim)] hover:text-[var(--fg)]"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
              <p className="text-xs text-[var(--fg-faint)]">
                {strategy === "parallel"
                  ? "References answer, then the aggregator fuses them."
                  : "Raw poll — every response returned unfused."}
              </p>
            </div>

            {/* rounds stepper */}
            <div className="grid gap-2">
              <Label>Fusion rounds</Label>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  outlined
                  disabled={strategy === "single" || rounds <= 1}
                  onClick={() => setRounds((r) => Math.max(1, r - 1))}
                >
                  <Minus className="h-3 w-3" />
                </Button>
                <span className="w-8 text-center font-mono text-sm text-[var(--fg)]">
                  {strategy === "single" ? 1 : rounds}
                </span>
                <Button
                  size="sm"
                  outlined
                  disabled={strategy === "single" || rounds >= maxRounds}
                  onClick={() => setRounds((r) => Math.min(maxRounds, r + 1))}
                >
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
              <p className="text-xs text-[var(--fg-faint)]">
                Round 2+ feeds the prior fusion back to every reference.
              </p>
            </div>

            {/* aggregator */}
            <div className="grid gap-2">
              <Label htmlFor="moa-aggregator">Aggregator model</Label>
              <Input
                id="moa-aggregator"
                value={aggregator}
                onChange={(e) => setAggregator(e.target.value)}
                disabled={strategy === "single"}
                placeholder={status?.defaults.aggregator_model ?? ""}
                className="font-mono text-xs"
                list="moa-model-slugs"
              />
              <datalist id="moa-model-slugs">
                {modelPool.map((m) => (
                  <option key={m} value={m} />
                ))}
              </datalist>
              <p className="text-xs text-[var(--fg-faint)]">
                Synthesizes the final answer — use the strongest model you have.
              </p>
            </div>
          </div>

          {/* prompt */}
          <div className="grid gap-2">
            <Label htmlFor="moa-prompt">Prompt</Label>
            <textarea
              id="moa-prompt"
              className="flex min-h-[110px] w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 font-mono text-sm text-[var(--fg)] shadow-sm placeholder:text-[var(--fg-faint)] focus-visible:border-[var(--accent-dim)] focus-visible:outline-none"
              placeholder="A genuinely hard problem — complex math, architecture decisions, multi-step reasoning…"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-3">
            <Button size="sm" onClick={runCouncil} disabled={!canRun}>
              {running ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Play className="h-3 w-3" />
              )}
              {running ? "Running council…" : "Run council"}
            </Button>
            {running && (
              <span className="font-mono text-xs text-[var(--fg-faint)]">
                {elapsed.toFixed(1)}s — {selected.size} reference
                {selected.size === 1 ? "" : "s"}
                {strategy === "parallel" ? " + aggregator" : ""}
              </span>
            )}
            {!running && !requirementsMet && status && !statusLoading && (
              <span className="text-xs text-[var(--warn)]">
                Set OPENROUTER_API_KEY to enable runs.
              </span>
            )}
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------- run console */}
      {runError && (
        <Banner
          tone="err"
          icon={<XCircle className="h-4 w-4" />}
          title="Council run failed"
          body={runError}
        />
      )}

      {result && (
        <section className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base text-[var(--fg)]">Run console</h2>
            <span className="font-mono text-xs text-[var(--fg-faint)]">
              {result.elapsed_seconds}s · {result.strategy}
              {result.aggregator_model ? ` · agg ${result.aggregator_model}` : ""}
            </span>
          </div>

          {result.rounds.map((round) => (
            <div key={round.round} className="flex flex-col gap-3">
              {result.rounds.length > 1 && (
                <h3 className="text-sm text-[var(--fg-dim)]">
                  Round {round.round}
                </h3>
              )}

              {/* per-reference lanes */}
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {round.responses.map((lane) => (
                  <article
                    key={`${round.round}-${lane.model}`}
                    className={`flex min-h-[120px] flex-col rounded-lg border p-3 ${
                      lane.ok
                        ? "border-[var(--border)] bg-[var(--bg-elev)]"
                        : "border-[var(--err)]/40 bg-[var(--err)]/5"
                    }`}
                  >
                    <header className="mb-2 flex items-center gap-2">
                      {lane.ok ? (
                        <span className="h-1.5 w-1.5 rounded-full bg-[var(--ok)]" />
                      ) : (
                        <XCircle className="h-3.5 w-3.5 text-[var(--err)]" />
                      )}
                      <span className="truncate font-mono text-xs text-[var(--fg-dim)]">
                        {lane.model}
                      </span>
                    </header>
                    <div className="min-h-0 flex-1 overflow-y-auto">
                      {lane.ok ? (
                        <Markdown content={lane.content} />
                      ) : (
                        <p className="text-xs text-[var(--err)]">{lane.content}</p>
                      )}
                    </div>
                  </article>
                ))}
              </div>

              {/* fused output for this round */}
              {round.fused && (
                <div className="rounded-lg border border-[var(--accent-dim)]/50 bg-[var(--bg-elev)] p-4">
                  <h3 className="mb-2 text-sm text-[var(--accent)]">
                    Fused output
                    {result.rounds.length > 1 ? ` — round ${round.round}` : ""}
                  </h3>
                  <Markdown content={round.fused} />
                </div>
              )}
            </div>
          ))}

          {/* failed models footnote */}
          {result.failed_models.length > 0 && (
            <p className="text-xs text-[var(--warn)]">
              {result.failed_models.length} model
              {result.failed_models.length === 1 ? "" : "s"} failed and{" "}
              {result.failed_models.length === 1 ? "was" : "were"} excluded
              from fusion:{" "}
              <span className="font-mono">
                {result.failed_models.join(", ")}
              </span>
            </p>
          )}
        </section>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Banner                                                             */
/* ------------------------------------------------------------------ */

function Banner({
  tone,
  icon,
  title,
  body,
}: {
  tone: "warn" | "err";
  icon: React.ReactNode;
  title: string;
  body: React.ReactNode;
}) {
  const color = tone === "warn" ? "var(--warn)" : "var(--err)";
  return (
    <div
      className="flex items-start gap-3 rounded-lg border px-4 py-3 text-sm"
      style={{
        borderColor: `color-mix(in srgb, ${color} 40%, transparent)`,
        background: `color-mix(in srgb, ${color} 10%, transparent)`,
        color,
      }}
    >
      <span className="mt-0.5 shrink-0">{icon}</span>
      <div>
        <p className="font-medium">{title}</p>
        <div className="mt-0.5 text-[var(--fg-dim)]">{body}</div>
      </div>
    </div>
  );
}
