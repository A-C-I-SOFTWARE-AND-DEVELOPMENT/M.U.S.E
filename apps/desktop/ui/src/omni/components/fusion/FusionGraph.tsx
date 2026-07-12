import { motion } from 'framer-motion';
import type { FusionDef } from '@/lib/fusionTypes';
import { modelsOf } from '@/lib/fusionTypes';

// Animated proposers -> aggregator -> attested-output graph. Reuses the visual
// language of the Axiom FusionCore (beams converging on a synthesizing core).
export function FusionGraph({ def, active }: { def: FusionDef; active?: boolean }) {
  const VIEW = 320;
  const CY = 130;
  const proposers = def.layers.flatMap((l) => l.legs);
  const aggX = VIEW - 56;
  const accent = 'var(--octa-glow)';

  const py = (i: number, n: number) => (n <= 1 ? CY : 30 + (i * (CY * 2 - 60)) / (n - 1));

  return (
    <svg viewBox={`0 0 ${VIEW} ${CY * 2}`} width="100%" style={{ maxWidth: 360 }}>
      <defs>
        <linearGradient id="fbeam" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={accent} stopOpacity="0.1" />
          <stop offset="100%" stopColor={accent} stopOpacity="0.7" />
        </linearGradient>
      </defs>

      {proposers.map((leg, i) => {
        const y = py(i, proposers.length);
        return (
          <g key={i}>
            <motion.path
              d={`M 56 ${y} C 150 ${y}, ${aggX - 70} ${CY}, ${aggX - 18} ${CY}`}
              fill="none"
              stroke="url(#fbeam)"
              strokeWidth={1.4}
              strokeDasharray="3 6"
              animate={active ? { strokeDashoffset: [0, -18] } : {}}
              transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
            />
            <circle cx={40} cy={y} r={12} fill="#0e141d" stroke={accent} strokeWidth={1.4} />
            <text x={40} y={y + 26} textAnchor="middle" fontSize={7} fontFamily="'JetBrains Mono', monospace" fill="var(--ink-dim)">
              {leg.model.split('/').pop()?.slice(0, 14)}
            </text>
          </g>
        );
      })}

      {/* Aggregator core */}
      <circle cx={aggX} cy={CY} r={26} fill={accent} fillOpacity={0.12} />
      <motion.rect
        x={aggX - 16} y={CY - 16} width={32} height={32} rx={7}
        transform={`rotate(45 ${aggX} ${CY})`}
        fill="#0a0e14" stroke={accent} strokeWidth={2}
        animate={active ? { scale: [1, 1.06, 1] } : {}}
        transition={{ duration: 1.4, repeat: Infinity }}
        style={{ transformOrigin: `${aggX}px ${CY}px` }}
      />
      <text x={aggX} y={CY + 2} textAnchor="middle" fontSize={7.5} fontFamily="'JetBrains Mono', monospace" fill={accent}>
        {def.aggregator ? 'AGG' : 'OUT'}
      </text>
      <text x={aggX} y={CY * 2 - 10} textAnchor="middle" fontSize={7} fontFamily="'JetBrains Mono', monospace" fill="var(--ink-faint)">
        {def.aggregator ? def.aggregator.model.split('/').pop()?.slice(0, 14) : `${modelsOf(def).length} model${modelsOf(def).length > 1 ? 's' : ''}`}
      </text>
    </svg>
  );
}
