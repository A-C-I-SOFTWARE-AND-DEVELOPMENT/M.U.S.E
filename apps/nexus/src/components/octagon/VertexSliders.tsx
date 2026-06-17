import type { VertexDef, WeightVector } from '@/lib/types';

interface Props {
  vertices: VertexDef[];
  weights: WeightVector;
  /** Drag a single axis; parent re-solves the node toward the weighted centroid. */
  onAxis: (key: string, value: number) => void;
  disabled?: boolean;
}

/**
 * Thin per-vertex sliders showing each axis's deviation from neutral, matching
 * the mock's "EMPATHY -70% / CODING +80%" style. Value shown is signed % vs the
 * neutral baseline (1/N).
 */
export function VertexSliders({ vertices, weights, onAxis, disabled }: Props) {
  const neutral = 1 / vertices.length;
  return (
    <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
      {vertices.map((v) => {
        const w = weights[v.key] ?? neutral;
        const deviation = Math.round(((w - neutral) / neutral) * 100);
        const sign = deviation > 0 ? '+' : '';
        return (
          <div key={v.key} className="flex items-center gap-2">
            <span
              className="mono w-[88px] shrink-0 text-[10px] uppercase tracking-wider"
              style={{ color: v.accent }}
            >
              {v.label}
            </span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.001}
              value={w}
              disabled={disabled}
              onChange={(e) => onAxis(v.key, parseFloat(e.target.value))}
              className="nexus-range h-1 flex-1"
              style={{ accentColor: v.accent }}
            />
            <span
              className="mono w-[44px] shrink-0 text-right text-[10px]"
              style={{ color: deviation === 0 ? 'var(--ink-dim)' : v.accent }}
            >
              {sign}
              {deviation}%
            </span>
          </div>
        );
      })}
    </div>
  );
}
