import { useEffect, useMemo, useState } from "react";
import { formatRelativeTime, useNightdeskOverview } from "./useNightdesk";

/* ------------------------------------------------------------------ */
/* TickerStrip — the turn ticker. One mono line cycling through the    */
/* active-model line + recent decision-ledger entries, auto-rotating   */
/* every 6s; rotation pauses while the pointer hovers the strip.       */
/* ------------------------------------------------------------------ */

const ROTATE_MS = 6000;

interface TickerItem {
  key: string;
  text: string;
}

export default function TickerStrip() {
  const { data } = useNightdeskOverview(30000);
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);

  const items = useMemo<TickerItem[]>(() => {
    const out: TickerItem[] = [];
    const kpis = data?.kpis;
    if (kpis?.active_model) {
      const provider = kpis.active_provider || "unknown provider";
      const fallbacks = kpis.fallback_chain?.length ?? 0;
      out.push({
        key: "active-model",
        text: `ACTIVE MODEL ▸ ${kpis.active_model} · ${provider}${
          fallbacks > 0 ? ` · fallback chain ${fallbacks}` : ""
        }`,
      });
    }
    for (const entry of data?.ledger ?? []) {
      out.push({
        key: entry.id,
        text: `[${formatRelativeTime(entry.ts)}] ${entry.title} — session ${entry.session}`,
      });
    }
    return out;
  }, [data]);

  // Clamp the cursor when the item list shrinks under it.
  useEffect(() => {
    if (index >= items.length) setIndex(0);
  }, [items.length, index]);

  useEffect(() => {
    if (paused || items.length <= 1) return;
    const timer = window.setInterval(() => {
      setIndex((i) => (i + 1) % items.length);
    }, ROTATE_MS);
    return () => window.clearInterval(timer);
  }, [paused, items.length]);

  const current = items.length > 0 ? items[Math.min(index, items.length - 1)] : null;

  return (
    <div
      className="nd-ticker"
      data-paused={paused}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      aria-live="off"
    >
      <span className="nd-label nd-ticker-tag">Turns</span>
      {current ? (
        <div key={current.key} className="nd-ticker-line" title={current.text}>
          {current.text}
        </div>
      ) : (
        <div className="nd-ticker-line">no turns recorded yet</div>
      )}
      {items.length > 1 && (
        <span className="nd-ticker-count">
          {Math.min(index, items.length - 1) + 1}/{items.length}
        </span>
      )}
    </div>
  );
}
