import { useEffect, useMemo, useState } from "react";
import { fetchJSON } from "@/lib/api";
import "./nightdesk.css";

// ---------------------------------------------------------------------------
// Night Desk — Model router · Cost by provider
// GET /api/nightdesk/pathways → aggregate est_cost per provider →
// horizontal bars (violet/cyan family), value labels, 'estimated' subtitle.
// All-zero → honest 'no billable usage recorded' note; never fake data.
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

/** Violet/cyan family — the theme accent plus its Night Desk kin. */
const BAR_COLORS = [
  "var(--accent)",
  "var(--nd-cyan)",
  "var(--nd-violet)",
  "color-mix(in srgb, var(--nd-cyan) 55%, var(--nd-violet))",
];

function formatCost(v: number): string {
  if (v >= 100) return `$${v.toFixed(0)}`;
  if (v >= 1) return `$${v.toFixed(2)}`;
  if (v > 0) return `$${v.toFixed(4)}`;
  return "$0.00";
}

export default function CostByProvider() {
  const [data, setData] = useState<PathwaysPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  const rows = useMemo(() => {
    const byProvider = new Map<string, number>();
    for (const p of data?.pathways ?? []) {
      const key =
        p.provider && p.provider.trim() !== "" ? p.provider : "unknown";
      byProvider.set(key, (byProvider.get(key) ?? 0) + (p.est_cost || 0));
    }
    return [...byProvider.entries()]
      .map(([provider, cost]) => ({ provider, cost }))
      .sort((a, b) => b.cost - a.cost);
  }, [data]);

  const total = rows.reduce((s, r) => s + r.cost, 0);
  const max = rows.reduce((m, r) => Math.max(m, r.cost), 0);
  const allZero = rows.length === 0 || total <= 0;

  return (
    <section className="nd-panel">
      <header className="nd-panel-head">
        <h2 className="nd-label">Cost by provider</h2>
        <span className="nd-sub" style={{ fontSize: 10 }}>
          estimated
        </span>
      </header>
      <div className="nd-panel-body">
        {error ? (
          <p className="nd-empty">cost data unavailable — {error}</p>
        ) : !data ? (
          <p className="nd-empty">loading cost data…</p>
        ) : allZero ? (
          <p className="nd-empty">no billable usage recorded</p>
        ) : (
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {rows.map((r, i) => (
              <li
                key={r.provider}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "4px 0",
                }}
              >
                <span
                  className="nd-mono"
                  style={{
                    width: 112,
                    flex: "none",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    color: "var(--nd-fg-dim)",
                  }}
                >
                  {r.provider}
                </span>
                <span
                  style={{
                    position: "relative",
                    height: 10,
                    flex: 1,
                    overflow: "hidden",
                    borderRadius: 2,
                    background: "var(--nd-panel-3)",
                  }}
                >
                  <span
                    style={{
                      position: "absolute",
                      top: 0,
                      bottom: 0,
                      left: 0,
                      width: `${max > 0 ? Math.max((r.cost / max) * 100, 1.5) : 0}%`,
                      background: BAR_COLORS[i % BAR_COLORS.length],
                      opacity: 0.75,
                      borderRadius: 2,
                    }}
                  />
                </span>
                <span
                  className="nd-num"
                  style={{
                    width: 80,
                    flex: "none",
                    textAlign: "right",
                    color: "var(--nd-fg-dim)",
                  }}
                >
                  {formatCost(r.cost)}
                </span>
              </li>
            ))}
          </ul>
        )}
        {data?.cost_basis && !error && (
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
            {data.cost_basis}
          </p>
        )}
      </div>
    </section>
  );
}
