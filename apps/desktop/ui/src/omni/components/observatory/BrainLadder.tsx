import { motion } from 'framer-motion';
import type { ObsLadderTier } from '@/lib/types';

const TIER_COLOR: Record<ObsLadderTier['tier'], string> = {
  local: '#34E5C8',
  hosted: '#C264FE',
  paired: '#FFB020',
};

/** The Brain Ladder — routing share + latency per tier (local / hosted / paired). */
export function BrainLadder({ tiers, streakTier }: { tiers: ObsLadderTier[]; streakTier: string | null }) {
  return (
    <div className="glass px-3 py-3">
      <div className="hud-label mb-2">Brain Ladder · routing share (1h)</div>
      {tiers.length === 0 ? (
        <div className="py-3 text-center text-[11px] text-[var(--ink-dim)]">
          No routed turns yet
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {tiers.map((t) => {
            const c = TIER_COLOR[t.tier];
            const streaking = streakTier === t.tier;
            return (
              <div key={t.tier} className="flex items-center gap-2.5">
                <span className="mono w-[52px] shrink-0 text-[10px] uppercase" style={{ color: c }}>
                  {t.tier}
                </span>
                <div className="relative h-3 flex-1 overflow-hidden rounded-full bg-[var(--hairline)]">
                  <motion.div
                    className="absolute inset-y-0 left-0 rounded-full"
                    style={{ background: c, boxShadow: streaking ? `0 0 10px ${c}` : undefined }}
                    animate={{ width: `${Math.round(t.share_1h * 100)}%` }}
                    transition={{ type: 'spring', stiffness: 120, damping: 20 }}
                  />
                </div>
                <span className="mono w-[64px] shrink-0 truncate text-right text-[9px] text-[var(--ink-faint)]">
                  {t.model}
                </span>
                <span className="mono w-[34px] shrink-0 text-right text-[10px]" style={{ color: c }}>
                  {Math.round(t.share_1h * 100)}%
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
