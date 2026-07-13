import { motion } from 'framer-motion';
import type { FusionResult, FusionSource, VertexDef } from '@/lib/types';

interface Props {
  sources: FusionSource[];
  result: FusionResult;
  vertices: VertexDef[];
}

const VIEW = 320;
const CX = VIEW / 2;

/**
 * The Axiom Gate fusion core: source nodes (left) stream into a central gate
 * diamond where verification happens; an attested vector emits (right). The
 * gate's color is the fused glow; it locks (solid) when attested, pulses amber
 * when owner-pending, and flashes red when blocked.
 */
export function FusionCore({ sources, result, vertices }: Props) {
  const glow = result.glowState.color;
  const verdictColor =
    result.verdict === 'attested'
      ? glow
      : result.verdict === 'pending-owner'
        ? '#FFB020'
        : '#FF5470';

  const srcY = (i: number, n: number) => {
    if (n === 1) return CX;
    return 70 + (i * (VIEW - 140)) / (n - 1);
  };
  const srcX = 40;
  const gateX = CX;
  const outX = VIEW - 36;

  const accentOf = (key: string) =>
    vertices.find((v) => v.key === key)?.accent ?? glow;

  return (
    <svg
      viewBox={`0 0 ${VIEW} ${VIEW}`}
      width="100%"
      style={{ maxWidth: 340, filter: `drop-shadow(0 0 16px ${verdictColor}55)` }}
      className="touch-none"
    >
      <defs>
        <radialGradient id="gateGrad" cx="50%" cy="50%" r="60%">
          <stop offset="0%" stopColor={verdictColor} stopOpacity="0.32" />
          <stop offset="100%" stopColor={verdictColor} stopOpacity="0" />
        </radialGradient>
        <linearGradient id="beam" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={glow} stopOpacity="0.1" />
          <stop offset="100%" stopColor={glow} stopOpacity="0.7" />
        </linearGradient>
      </defs>

      {/* Source → gate beams (animated dash flow) */}
      {sources.map((s, i) => {
        const y = srcY(i, sources.length);
        const dom = Object.entries(s.weights).sort((a, b) => b[1] - a[1])[0]?.[0] ?? '';
        return (
          <g key={s.id}>
            <motion.path
              d={`M ${srcX + 18} ${y} C ${CX - 60} ${y}, ${CX - 40} ${CX}, ${gateX - 26} ${CX}`}
              fill="none"
              stroke={accentOf(dom)}
              strokeWidth={1.4}
              strokeOpacity={0.5}
              strokeDasharray="3 6"
              animate={{ strokeDashoffset: [0, -18] }}
              transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
            />
            <circle cx={srcX} cy={y} r={11} fill="#0e141d" stroke={accentOf(dom)} strokeWidth={1.5} />
            <circle cx={srcX} cy={y} r={4} fill={accentOf(dom)} />
          </g>
        );
      })}

      {/* Gate → output beam */}
      <motion.path
        d={`M ${gateX + 26} ${CX} C ${CX + 50} ${CX}, ${outX - 40} ${CX}, ${outX - 10} ${CX}`}
        fill="none"
        stroke="url(#beam)"
        strokeWidth={2}
        animate={{ opacity: result.verdict === 'attested' ? [0.5, 1, 0.5] : 0.3 }}
        transition={{ duration: 1.6, repeat: Infinity }}
      />

      {/* Gate aura */}
      <circle cx={gateX} cy={CX} r={56} fill="url(#gateGrad)" />

      {/* The gate diamond */}
      <motion.g
        animate={{
          scale: result.verdict === 'pending-owner' ? [1, 1.06, 1] : 1,
        }}
        transition={{ duration: 1.4, repeat: result.verdict === 'pending-owner' ? Infinity : 0 }}
        style={{ transformOrigin: `${gateX}px ${CX}px` }}
      >
        <rect
          x={gateX - 26}
          y={CX - 26}
          width={52}
          height={52}
          rx={8}
          transform={`rotate(45 ${gateX} ${CX})`}
          fill="#0a0e14"
          stroke={verdictColor}
          strokeWidth={2.5}
          className="octa-glow-transition"
        />
        <text
          x={gateX}
          y={CX - 2}
          textAnchor="middle"
          fontSize={9}
          fontFamily="'JetBrains Mono', monospace"
          fill={verdictColor}
          letterSpacing="0.1em"
        >
          AXIOM
        </text>
        <text
          x={gateX}
          y={CX + 9}
          textAnchor="middle"
          fontSize={7}
          fontFamily="'JetBrains Mono', monospace"
          fill="var(--ink-dim)"
          letterSpacing="0.08em"
        >
          GATE
        </text>
      </motion.g>

      {/* Output attested node */}
      <circle cx={outX} cy={CX} r={13} fill={verdictColor} fillOpacity={0.18} />
      <circle cx={outX} cy={CX} r={7} fill={verdictColor} stroke="#0a0e14" strokeWidth={2} />
    </svg>
  );
}
