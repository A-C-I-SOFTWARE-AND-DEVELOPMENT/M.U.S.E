import { useEffect, useMemo, useState } from "react";
import { fetchJSON } from "@/lib/api";
import "./nightdesk.css";

// ---------------------------------------------------------------------------
// Night Desk — Model router · Throughput chart
// GET /api/nightdesk/throughput?hours=24 → {series:[{t,tokens}], unit, note}
// Hand-rolled SVG area chart: single accent stroke + low-alpha solid fill
// (no gradient), hairline gridlines, hour ticks. No external chart dep —
// @observablehq/plot is installed but unused anywhere in src/, and
// AnalyticsPage charts are hand-built too, so this stays consistent.
// Static render only: nothing animates, so reduced-motion is respected.
// ---------------------------------------------------------------------------

interface ThroughputPoint {
  t: number;
  tokens: number;
}

interface ThroughputPayload {
  series: ThroughputPoint[];
  unit?: string;
  bucket_seconds?: number;
  window_hours?: number;
  note?: string;
}

const W = 720;
const H = 208;
const PAD = { l: 46, r: 14, t: 12, b: 26 };
const INNER_W = W - PAD.l - PAD.r;
const INNER_H = H - PAD.t - PAD.b;
const BASELINE_Y = PAD.t + INNER_H;

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

/** Round a max value up to a 1 / 2 / 2.5 / 5 × 10^k gridline ceiling. */
function niceCeil(v: number): number {
  if (v <= 0) return 1;
  const exp = Math.floor(Math.log10(v));
  const base = Math.pow(10, exp);
  const f = v / base;
  const nf = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
  return nf * base;
}

function hourLabel(t: number): string {
  const d = new Date(t * 1000);
  return `${String(d.getHours()).padStart(2, "0")}:00`;
}

export default function ThroughputChart() {
  const [data, setData] = useState<ThroughputPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchJSON<ThroughputPayload>("/api/nightdesk/throughput?hours=24")
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

  const series = useMemo(() => data?.series ?? [], [data]);
  const maxTokens = useMemo(
    () => series.reduce((m, p) => Math.max(m, p.tokens), 0),
    [series],
  );
  const allZero = series.length > 0 && maxTokens === 0;

  const geom = useMemo(() => {
    if (series.length === 0) return null;
    const t0 = series[0].t;
    const t1 = series[series.length - 1].t;
    const span = Math.max(t1 - t0, 1);
    const maxY = niceCeil(maxTokens);
    const x = (t: number) => PAD.l + ((t - t0) / span) * INNER_W;
    const y = (v: number) => BASELINE_Y - (v / maxY) * INNER_H;

    const linePts = series.map(
      (p) => `${x(p.t).toFixed(2)},${y(p.tokens).toFixed(2)}`,
    );
    const linePath = `M${linePts.join(" L")}`;
    const areaPath = `${linePath} L${x(t1).toFixed(2)},${BASELINE_Y} L${x(t0).toFixed(2)},${BASELINE_Y} Z`;

    // Y gridlines at 25 / 50 / 75 / 100 % of the nice ceiling.
    const yTicks = [0.25, 0.5, 0.75, 1].map((f) => ({
      v: maxY * f,
      y: y(maxY * f),
    }));

    // X ticks at hour boundaries, ~3h apart, inside the window.
    const xTicks: { t: number; x: number }[] = [];
    const step = 3 * 3600;
    let tick = Math.ceil(t0 / 3600) * 3600;
    while (tick <= t1) {
      xTicks.push({ t: tick, x: x(tick) });
      tick += step;
    }

    return { linePath, areaPath, yTicks, xTicks };
  }, [series, maxTokens]);

  const unit = data?.unit ?? "tokens/15min";
  const hours = data?.window_hours ?? 24;

  return (
    <section className="nd-panel">
      <header className="nd-panel-head">
        <h2 className="nd-label">Throughput · {unit} ({hours}h)</h2>
        {data && !allZero && series.length > 0 && (
          <span className="nd-sub">
            peak <span className="nd-num">{formatTokens(maxTokens)}</span>
          </span>
        )}
      </header>
      <div className="nd-panel-body">
        {error ? (
          <p className="nd-empty">throughput unavailable — {error}</p>
        ) : !data ? (
          <p className="nd-empty">loading throughput…</p>
        ) : series.length === 0 ? (
          <p className="nd-empty">no token volume recorded in window</p>
        ) : (
          <>
            <svg
              viewBox={`0 0 ${W} ${H}`}
              style={{ display: "block", width: "100%", height: "auto" }}
              role="img"
              aria-label={`Throughput, ${unit}, last ${hours} hours`}
            >
              {/* hairline gridlines */}
              {geom?.yTicks.map((g) => (
                <line
                  key={g.v}
                  x1={PAD.l}
                  x2={W - PAD.r}
                  y1={g.y}
                  y2={g.y}
                  stroke="var(--nd-hairline)"
                  strokeWidth="1"
                />
              ))}
              <line
                x1={PAD.l}
                x2={W - PAD.r}
                y1={BASELINE_Y}
                y2={BASELINE_Y}
                stroke="var(--nd-hairline-strong)"
                strokeWidth="1"
              />

              {/* area + line — single accent, no gradient, no animation */}
              {geom && (
                <>
                  <path
                    d={geom.areaPath}
                    fill="var(--accent)"
                    fillOpacity={allZero ? 0 : 0.08}
                  />
                  <path
                    d={geom.linePath}
                    fill="none"
                    stroke="var(--accent)"
                    strokeWidth="1.25"
                    strokeLinejoin="round"
                    strokeLinecap="round"
                    strokeOpacity={allZero ? 0.35 : 1}
                  />
                </>
              )}

              {/* y axis labels */}
              {geom?.yTicks.map((g) => (
                <text
                  key={`yl-${g.v}`}
                  x={PAD.l - 6}
                  y={g.y + 3}
                  textAnchor="end"
                  fontSize="9"
                  fill="var(--nd-fg-faint)"
                  fontFamily="var(--font-mono)"
                >
                  {formatTokens(g.v)}
                </text>
              ))}

              {/* x hour ticks */}
              {geom?.xTicks.map((tick) => (
                <text
                  key={`xl-${tick.t}`}
                  x={tick.x}
                  y={H - 8}
                  textAnchor="middle"
                  fontSize="9"
                  fill="var(--nd-fg-faint)"
                  fontFamily="var(--font-mono)"
                >
                  {hourLabel(tick.t)}
                </text>
              ))}

              {/* honest all-zero overlay */}
              {allZero && (
                <text
                  x={W / 2}
                  y={PAD.t + INNER_H / 2}
                  textAnchor="middle"
                  fontSize="10"
                  fill="var(--nd-fg-dim)"
                  fontFamily="var(--font-mono)"
                >
                  no token volume recorded in window
                </text>
              )}
            </svg>
            {data.note && (
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
                {data.note}
              </p>
            )}
          </>
        )}
      </div>
    </section>
  );
}
