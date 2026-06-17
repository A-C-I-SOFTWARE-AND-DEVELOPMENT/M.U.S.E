import { useMemo } from 'react';
import { motion } from 'framer-motion';
import type { ObsSnapshot } from '@/lib/types';

interface Props {
  snapshot: ObsSnapshot | null;
  /** clusterId -> live pulse intensity (0..1), decayed by the page. */
  pulses: Record<string, number>;
  queuePulse: number; // 0..1, drives the Nero core amplitude
  height?: number;
}

const VIEW = 340;
const CX = VIEW / 2;
const CY = VIEW / 2;

// Dominant type → tint (matches the signal palette).
const TYPE_TINT: Record<string, string> = {
  code: '#34E5C8',
  docs: '#7C9EFF',
  test: '#FFB020',
  memory: '#C264FE',
};

function dominantType(mix: Record<string, number>): string {
  return Object.entries(mix).sort((a, b) => b[1] - a[1])[0]?.[0] ?? 'code';
}

/**
 * The Neural Observatory galaxy (Nero Solar dressing). Render-only: positions,
 * radii, heat are gateway-computed. Nero Core at the reserved origin; one planet
 * per cluster; orbit rings derived from planet positions; live activations pulse
 * the touched cluster. Dormant (no graph) ⇒ dim core + starfield, zero planets.
 */
export function Galaxy({ snapshot, pulses, queuePulse, height = 340 }: Props) {
  const clusters = snapshot?.graph.available ? snapshot.graph.clusters : [];

  const projected = useMemo(() => {
    if (clusters.length === 0) return [];
    // Fit cluster (x,z) plane into the viewbox with a slight isometric tilt.
    const xs = clusters.map((c) => c.pos[0]);
    const zs = clusters.map((c) => c.pos[2]);
    const span = Math.max(1, ...xs.map(Math.abs), ...zs.map(Math.abs));
    const k = (VIEW * 0.34) / span;
    return clusters.map((c) => {
      const [x, y, z] = c.pos;
      const sx = CX + x * k;
      const sy = CY + z * k * 0.62 - y * k * 0.22;
      const orbit = Math.hypot(sx - CX, sy - CY);
      return { c, sx, sy, orbit };
    });
  }, [clusters]);

  const byId = useMemo(
    () => Object.fromEntries(projected.map((p) => [p.c.id, p])),
    [projected],
  );

  const coreR = 16 + queuePulse * 10;

  return (
    <svg viewBox={`0 0 ${VIEW} ${VIEW}`} width="100%" style={{ maxWidth: 420, height }} className="touch-none select-none">
      <defs>
        <radialGradient id="coreGrad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#FFD9A0" stopOpacity="0.95" />
          <stop offset="45%" stopColor="#FF8A3D" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#FF8A3D" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="vignette" cx="50%" cy="50%" r="60%">
          <stop offset="60%" stopColor="#000" stopOpacity="0" />
          <stop offset="100%" stopColor="#000" stopOpacity="0.5" />
        </radialGradient>
      </defs>

      {/* Decorative starfield (clearly chrome, not data) */}
      {Array.from({ length: 46 }).map((_, i) => {
        const a = (i * 137.5 * Math.PI) / 180;
        const r = 30 + ((i * 53) % 130);
        return (
          <circle
            key={`s-${i}`}
            cx={CX + Math.cos(a) * r}
            cy={CY + Math.sin(a) * r * 0.7}
            r={i % 7 === 0 ? 1.2 : 0.6}
            fill="#9FB4C8"
            opacity={0.18 + (i % 5) * 0.04}
          />
        );
      })}

      {/* Orbit rings (derived from planet positions) */}
      {projected.map((p) => (
        <ellipse
          key={`o-${p.c.id}`}
          cx={CX}
          cy={CY}
          rx={p.orbit}
          ry={p.orbit * 0.7}
          fill="none"
          stroke="var(--hairline)"
          strokeWidth={0.8}
          opacity={0.5}
        />
      ))}

      {/* Cluster edges */}
      {snapshot?.graph.cluster_edges.map((e, i) => {
        const a = byId[e.a];
        const b = byId[e.b];
        if (!a || !b) return null;
        return (
          <line
            key={`e-${i}`}
            x1={a.sx}
            y1={a.sy}
            x2={b.sx}
            y2={b.sy}
            stroke={e.heat != null ? '#34E5C8' : 'var(--hairline)'}
            strokeWidth={0.6 + (e.heat ?? 0) * 1.4}
            strokeOpacity={0.25 + (e.heat ?? 0) * 0.4}
          />
        );
      })}

      {/* Nero Core (sun) — pulse ∝ queue depth */}
      <motion.circle
        cx={CX}
        cy={CY}
        animate={{ r: [coreR, coreR + 3, coreR] }}
        transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
        fill="url(#coreGrad)"
      />
      <circle cx={CX} cy={CY} r={7} fill="#FFB877" />

      {/* Planets (clusters) */}
      {projected.map((p) => {
        const tint = TYPE_TINT[dominantType(p.c.type_mix)] ?? '#34E5C8';
        const heat = p.c.heat; // null = no measured activations → neutral grey
        const fill = heat == null ? '#5A6B7D' : tint;
        const r = 4 + p.c.radius * 1.6;
        const pulse = pulses[p.c.id] ?? 0;
        return (
          <g key={p.c.id}>
            {pulse > 0.02 && (
              <circle cx={p.sx} cy={p.sy} r={r + 6 + pulse * 14} fill={tint} opacity={pulse * 0.5} />
            )}
            <circle
              cx={p.sx}
              cy={p.sy}
              r={r}
              fill={fill}
              fillOpacity={heat == null ? 0.5 : 0.4 + heat * 0.6}
              stroke={fill}
              strokeWidth={1.2}
              style={{ filter: heat != null ? `drop-shadow(0 0 ${4 + heat * 10}px ${tint})` : undefined }}
            >
              <title>{`${p.c.label} · ${p.c.members} members · heat ${heat == null ? 'n/a' : heat.toFixed(2)}`}</title>
            </circle>
            <text
              x={p.sx}
              y={p.sy + r + 9}
              textAnchor="middle"
              fontSize={7.5}
              fontFamily="'JetBrains Mono', monospace"
              fill="var(--ink-dim)"
            >
              {p.c.label}
            </text>
          </g>
        );
      })}

      <rect x={0} y={0} width={VIEW} height={VIEW} fill="url(#vignette)" pointerEvents="none" />
    </svg>
  );
}
