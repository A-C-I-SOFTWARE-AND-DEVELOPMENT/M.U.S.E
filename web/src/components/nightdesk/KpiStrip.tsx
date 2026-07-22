import { formatTokenCount } from "@/lib/format";
import { useNightdeskOverview } from "./useNightdesk";

/* ------------------------------------------------------------------ */
/* KpiStrip — the four Night Desk KPI tiles.                           */
/*   TOKENS TODAY      (cyan)    sub: turns today                      */
/*   EST. COST TODAY   (magenta) sub: honesty label when estimated     */
/*   KNOWLEDGE GRAPH   (violet)  sub: edges                            */
/*   ACTIVE MODEL      (green)   sub: provider + fallback chain length */
/* Shares the single overview poller via useNightdeskOverview(30000).  */
/* ------------------------------------------------------------------ */

function formatCost(usd: number): string {
  if (usd > 0 && usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

function truncateMiddle(value: string, max = 26): string {
  if (value.length <= max) return value;
  const head = Math.ceil((max - 1) / 2);
  const tail = Math.floor((max - 1) / 2);
  return `${value.slice(0, head)}…${value.slice(value.length - tail)}`;
}

export default function KpiStrip() {
  const { data, error, loading } = useNightdeskOverview(30000);
  const kpis = data?.kpis ?? null;

  const tokens = kpis?.tokens_today ?? null;
  const turns = kpis?.turns_today ?? null;
  const cost = kpis?.cost_today_usd ?? null;
  const costEstimated = kpis?.cost_estimated ?? false;
  const graphNodes = kpis?.graph_nodes ?? null;
  const graphEdges = kpis?.graph_edges ?? null;
  const activeModel = kpis?.active_model ?? null;
  const activeProvider = kpis?.active_provider ?? null;
  const fallbackCount = kpis?.fallback_chain?.length ?? 0;

  const modelSub = (() => {
    if (!kpis) return loading ? "loading…" : "—";
    if (!activeModel) return "no active model configured";
    const provider = activeProvider || "unknown provider";
    return fallbackCount > 0
      ? `${provider} · +${fallbackCount} fallback${fallbackCount === 1 ? "" : "s"}`
      : provider;
  })();

  return (
    <section aria-label="Night Desk KPIs">
      <div className="nd-kpis">
        <div className="nd-kpi" data-accent="cyan" data-loading={loading && !kpis}>
          <span className="nd-label">Tokens today</span>
          <span className="nd-kpi-value">
            {tokens === null ? "—" : formatTokenCount(tokens)}
          </span>
          <span className="nd-kpi-sub">
            {turns === null
              ? "no turns recorded today"
              : `${turns.toLocaleString()} turn${turns === 1 ? "" : "s"} today`}
          </span>
        </div>

        <div className="nd-kpi" data-accent="magenta" data-loading={loading && !kpis}>
          <span className="nd-label">Est. cost today</span>
          <span className="nd-kpi-value">{cost === null ? "—" : formatCost(cost)}</span>
          <span className="nd-kpi-sub">
            {cost === null
              ? "loading…"
              : costEstimated
                ? "estimated — actual spend not metered"
                : "actual"}
          </span>
        </div>

        <div className="nd-kpi" data-accent="violet" data-loading={loading && !kpis}>
          <span className="nd-label">Knowledge graph</span>
          <span className="nd-kpi-value">
            {graphNodes === null ? "—" : graphNodes.toLocaleString()}
          </span>
          <span className="nd-kpi-sub">
            {graphNodes === null
              ? "graph unavailable"
              : `${(graphEdges ?? 0).toLocaleString()} edges`}
          </span>
        </div>

        <div className="nd-kpi" data-accent="green" data-loading={loading && !kpis}>
          <span className="nd-label">Active model</span>
          <span className="nd-kpi-value" title={activeModel ?? undefined}>
            {activeModel ? truncateMiddle(activeModel) : "—"}
          </span>
          <span className="nd-kpi-sub">{modelSub}</span>
        </div>
      </div>
      {error && (
        <p className="nd-sub" role="status" style={{ marginTop: 8 }}>
          overview fetch failed: {error}
        </p>
      )}
    </section>
  );
}
