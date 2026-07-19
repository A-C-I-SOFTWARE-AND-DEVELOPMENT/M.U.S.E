import type { CSSProperties, ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Singularity meter primitives (design contract Part 2.3) — pure divs +
 * token CSS vars, zero dependencies. Shared by Analytics/Models-style pages
 * to replace hand-rolled one-off bar markup.
 *
 * Colors route through the Part-0 semantic tokens:
 *   accent → var(--accent)   ok → var(--ok)    warn → var(--warn)
 *   err    → var(--err)      info → var(--info)
 */

export type MeterColor = "accent" | "ok" | "warn" | "err" | "info";

const COLOR_VAR: Record<MeterColor, string> = {
  accent: "var(--accent)",
  ok: "var(--ok)",
  warn: "var(--warn)",
  err: "var(--err)",
  info: "var(--info)",
};

export interface MeterProps {
  /** Current value. Clamped to [0, max] for rendering. */
  value: number;
  /** Scale maximum. Values <= 0 render an empty bar. */
  max: number;
  /** Token color of the filled segment. Defaults to "accent". */
  color?: MeterColor;
  /** Optional left label rendered above the bar (dim, sentence case). */
  label?: ReactNode;
  /** Optional right-aligned slot next to the label (e.g. formatted value). */
  right?: ReactNode;
  className?: string;
}

/** Horizontal bar: muted track + token-colored fill, 12px-radius page grammar. */
export function Meter({
  value,
  max,
  color = "accent",
  label,
  right,
  className,
}: MeterProps) {
  const pct =
    max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;

  return (
    <div className={cn("flex min-w-0 flex-col gap-1", className)}>
      {(label !== undefined || right !== undefined) && (
        <div className="flex min-w-0 items-baseline justify-between gap-2 text-xs">
          <span className="min-w-0 truncate text-[var(--fg-dim)]">{label}</span>
          {right !== undefined && (
            <span className="shrink-0 tabular-nums text-[var(--fg-faint)]">
              {right}
            </span>
          )}
        </div>
      )}
      <div
        role="progressbar"
        aria-valuenow={Math.round(value)}
        aria-valuemin={0}
        aria-valuemax={Math.round(max)}
        className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--bg-mute)]"
      >
        <div
          className="h-full rounded-full transition-[width] duration-200"
          style={
            {
              width: `${pct}%`,
              backgroundColor: COLOR_VAR[color],
            } as CSSProperties
          }
        />
      </div>
    </div>
  );
}

export interface SparkProps {
  /** Series values; each becomes one bar. Empty array renders nothing. */
  values: number[];
  /** Token color of the bars. Defaults to "accent". */
  color?: MeterColor;
  className?: string;
}

/** Tiny inline bar-series (sparkline). Track-free; bar heights normalize to max. */
export function Spark({ values, color = "accent", className }: SparkProps) {
  if (values.length === 0) return null;
  const max = Math.max(...values, 1);

  return (
    <div
      aria-hidden
      className={cn("flex h-6 items-end gap-px", className)}
    >
      {values.map((v, i) => (
        <div
          key={i}
          className="min-w-0 flex-1 rounded-[1px] transition-[height] duration-200"
          style={
            {
              height: `${Math.max(v > 0 ? 8 : 2, (v / max) * 100)}%`,
              backgroundColor: COLOR_VAR[color],
              opacity: v > 0 ? 1 : 0.3,
            } as CSSProperties
          }
        />
      ))}
    </div>
  );
}
