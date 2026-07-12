import { motion } from 'framer-motion';
import type { ObsActiveJob } from '@/lib/types';

interface Props {
  nodes: string[];
  activeJobs: ObsActiveJob[];
  queueDepth: number;
  gateFlare: { verdict: 'pass' | 'fail' | 'override'; ts: number } | null;
}

const STAGE_ORDER = ['job', 'navigator', 'worker', 'gate', 'ledger'];

/** The station graph Job → Navigator → Worker → Gate → Ledger with live packets. */
export function StationPipeline({ nodes, activeJobs, queueDepth, gateFlare }: Props) {
  const stages = nodes.length ? nodes : STAGE_ORDER;
  const flareActive = gateFlare && Date.now() - gateFlare.ts < 1200;

  return (
    <div className="glass px-3 py-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="hud-label">Pipeline</div>
        <div className="mono text-[10px] text-[var(--ink-dim)]">queue {queueDepth}</div>
      </div>
      <div className="relative flex items-center justify-between">
        {/* rail */}
        <div className="absolute left-3 right-3 top-1/2 h-px -translate-y-1/2 bg-[var(--hairline)]" />
        {stages.map((s) => {
          const here = activeJobs.filter(
            (j) => j.stage === s || (s === 'job' && j.stage === 'queued'),
          );
          const isGate = s === 'gate';
          const color =
            isGate && flareActive
              ? gateFlare!.verdict === 'fail'
                ? 'var(--state-error)'
                : 'var(--state-running)'
              : here.length
                ? 'var(--octa-glow)'
                : 'var(--ink-faint)';
          return (
            <div key={s} className="relative z-10 flex flex-1 flex-col items-center gap-1">
              <motion.div
                animate={{ scale: here.length ? [1, 1.25, 1] : 1 }}
                transition={{ duration: 1, repeat: here.length ? Infinity : 0 }}
                className="grid h-7 w-7 place-items-center rounded-full border bg-[var(--bg-base)]"
                style={{ borderColor: color, boxShadow: here.length ? `0 0 8px ${color}` : undefined }}
              >
                <span className="h-2 w-2 rounded-full" style={{ background: color }} />
              </motion.div>
              <span className="mono text-[8px] uppercase tracking-wide text-[var(--ink-dim)]">{s}</span>
              {here.length > 0 && (
                <span className="mono text-[8px]" style={{ color }}>
                  {here.length}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
