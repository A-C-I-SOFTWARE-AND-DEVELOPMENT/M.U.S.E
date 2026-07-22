import { useEffect, useMemo, useState } from "react";
import { fetchJSON } from "@/lib/api";
import {
  formatRelativeTime,
  normalizeNdStatus,
  useNightdeskOverview,
  type FallbackChainEntry,
} from "./useNightdesk";
import "./nightdesk.css";

// ---------------------------------------------------------------------------
// Night Desk — Model router · Synaptic substrate (model pathways table)
// GET /api/nightdesk/pathways → rows + status_basis / cost_basis footnotes.
// Fallback-chain membership comes from the shared useNightdeskOverview
// snapshot (kpis.fallback_chain); chain rows get a subtle accent highlight.
// Sort: active first, then last_used desc. Null ctx/cost → '—'. Never fake.
// ---------------------------------------------------------------------------

interface PathwayRow {
  model: string;
  provider: string;
  ctx: number | null;
  cost_input_1m: number | null;
  cost_output_1m: number | null;
  turns: number;
  est_cost: number;
  last_used: number | null;
  status: string;
}

interface PathwaysPayload {
  pathways: PathwayRow[];
  status_basis?: string;
  cost_basis?: string;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatCost(v: number): string {
  if (v >= 100) return `$${v.toFixed(0)}`;
  if (v >= 1) return `$${v.toFixed(2)}`;
  if (v > 0) return `$${v.toFixed(4)}`;
  return "$0.00";
}

function statusRank(status: string): number {
  const s = status.toLowerCase();
  if (s === "active") return 0;
  if (s === "idle") return 1;
  if (s === "dormant") return 2;
  return 3;
}

const thStyle: React.CSSProperties = {
  padding: "6px 8px",
  textAlign: "left",
  borderBottom: "1px solid var(--nd-hairline)",
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  padding: "6px 8px",
  borderBottom: "1px solid var(--nd-hairline)",
  verticalAlign: "middle",
};

export default function PathwaysTable() {
  const [data, setData] = useState<PathwaysPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { data: overview } = useNightdeskOverview();

  useEffect(() => {
    let cancelled = false;
    fetchJSON<PathwaysPayload>("/api/nightdesk/pathways")
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const chain = useMemo<FallbackChainEntry[]>(
    () => overview?.kpis?.fallback_chain ?? [],
    [overview],
  );

  const chainKeys = useMemo(() => {
    const exact = new Set<string>();
    const modelOnly = new Set<string>();
    for (const e of chain) {
      const model = (e.model ?? "").toLowerCase();
      const provider = (e.provider ?? "").toLowerCase();
      if (!model) continue;
      if (provider) exact.add(`${provider}::${model}`);
      else modelOnly.add(model);
    }
    return { exact, modelOnly };
  }, [chain]);

  const rows = useMemo(() => {
    return [...(data?.pathways ?? [])].sort((a, b) => {
      const r = statusRank(a.status) - statusRank(b.status);
      if (r !== 0) return r;
      return (b.last_used ?? 0) - (a.last_used ?? 0);
    });
  }, [data]);

  const inChain = (row: PathwayRow): boolean => {
    const model = row.model.toLowerCase();
    const provider = row.provider.toLowerCase();
    return (
      chainKeys.exact.has(`${provider}::${model}`) ||
      chainKeys.modelOnly.has(model)
    );
  };

  return (
    <section className="nd-panel">
      <header className="nd-panel-head">
        <h2 className="nd-label">Synaptic substrate — model pathways</h2>
        <span className="nd-sub" style={{ fontSize: 10 }}>
          One mind over every provider · no lock-in
        </span>
      </header>
      <div className="nd-panel-body" style={{ overflowX: "auto" }}>
        {error ? (
          <p className="nd-empty">pathways unavailable — {error}</p>
        ) : !data ? (
          <p className="nd-empty">loading pathways…</p>
        ) : rows.length === 0 ? (
          <p className="nd-empty">no model usage recorded yet</p>
        ) : (
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              textAlign: "left",
            }}
          >
            <thead>
              <tr>
                <th className="nd-label" style={{ ...thStyle, paddingLeft: 0 }}>
                  Model
                </th>
                <th className="nd-label" style={thStyle}>
                  Provider
                </th>
                <th className="nd-label" style={{ ...thStyle, textAlign: "right" }}>
                  Ctx
                </th>
                <th className="nd-label" style={{ ...thStyle, textAlign: "right" }}>
                  Turns
                </th>
                <th className="nd-label" style={{ ...thStyle, textAlign: "right" }}>
                  Cost-est
                </th>
                <th className="nd-label" style={thStyle}>
                  Last-used
                </th>
                <th className="nd-label" style={{ ...thStyle, paddingRight: 0 }}>
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const chained = inChain(row);
                return (
                  <tr
                    key={`${row.provider}::${row.model}`}
                    style={
                      chained
                        ? {
                            boxShadow: "inset 2px 0 0 var(--accent)",
                            background:
                              "color-mix(in srgb, var(--accent) 4%, transparent)",
                          }
                        : undefined
                    }
                  >
                    <td
                      className="nd-mono"
                      style={{
                        ...tdStyle,
                        paddingLeft: chained ? 10 : 8,
                        maxWidth: 220,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        color: "var(--nd-fg)",
                      }}
                      title={row.model}
                    >
                      {row.model}
                      {chained && (
                        <span
                          className="nd-mono"
                          style={{
                            marginLeft: 8,
                            fontSize: 8,
                            letterSpacing: "0.14em",
                            textTransform: "uppercase",
                            color: "var(--accent)",
                          }}
                          title="member of the configured fallback chain"
                        >
                          chain
                        </span>
                      )}
                    </td>
                    <td
                      className="nd-mono"
                      style={{ ...tdStyle, color: "var(--nd-fg-dim)" }}
                    >
                      {row.provider || "—"}
                    </td>
                    <td
                      className="nd-num"
                      style={{
                        ...tdStyle,
                        textAlign: "right",
                        color: "var(--nd-fg-dim)",
                      }}
                    >
                      {row.ctx == null ? "—" : formatTokens(row.ctx)}
                    </td>
                    <td
                      className="nd-num"
                      style={{
                        ...tdStyle,
                        textAlign: "right",
                        color: "var(--nd-fg-dim)",
                      }}
                    >
                      {row.turns}
                    </td>
                    <td
                      className="nd-num"
                      style={{
                        ...tdStyle,
                        textAlign: "right",
                        color: "var(--nd-fg-dim)",
                      }}
                    >
                      {formatCost(row.est_cost)}
                    </td>
                    <td
                      className="nd-mono"
                      style={{
                        ...tdStyle,
                        fontSize: 10,
                        color: "var(--nd-fg-faint)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {formatRelativeTime(row.last_used)}
                    </td>
                    <td style={{ ...tdStyle, paddingRight: 0 }}>
                      <span
                        className="nd-chip"
                        data-status={normalizeNdStatus(row.status)}
                      >
                        {row.status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        {data?.status_basis && !error && (
          <p
            className="nd-sub"
            style={{
              marginTop: 10,
              paddingTop: 8,
              borderTop: "1px solid var(--nd-hairline)",
              fontSize: 10,
              lineHeight: 1.5,
            }}
          >
            {data.status_basis}
          </p>
        )}
        {data?.cost_basis && !error && (
          <p className="nd-sub" style={{ marginTop: 4, fontSize: 10, lineHeight: 1.5 }}>
            {data.cost_basis}
          </p>
        )}
      </div>
    </section>
  );
}
