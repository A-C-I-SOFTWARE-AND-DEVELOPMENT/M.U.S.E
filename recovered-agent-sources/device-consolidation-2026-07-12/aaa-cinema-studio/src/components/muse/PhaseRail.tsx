'use client'

import { useMemo } from 'react'
import { cn } from '@/lib/utils'

/**
 * PhaseRail — the Singularity milestone tracker.
 * States: done (spectral ring), current (incandescent core), pending (void), failed (danger).
 * Canonical M.U.S.E component, ported to Tailwind.
 */
export type PhaseState = 'done' | 'current' | 'pending' | 'failed'

export interface PhaseRailProps {
  phases: Array<{ id: string; label: string; state: PhaseState }>
  className?: string
}

export function PhaseRail({ phases, className }: PhaseRailProps) {
  const nodes = useMemo(
    () => phases.map((p, i) => ({ ...p, isLast: i === phases.length - 1 })),
    [phases],
  )

  return (
    <div
      className={cn('flex items-center flex-wrap gap-0', className)}
      role="list"
      aria-label="Milestone phases"
    >
      {nodes.map((phase) => (
        <div key={phase.id} className="flex items-center gap-1.5" role="listitem">
          <span
            className={cn(
              'h-2.5 w-2.5 rounded-full border transition-colors',
              phase.state === 'done' && 'border-[#7ae0ff] bg-[#7ae0ff]',
              phase.state === 'current' && 'border-white bg-white phase-pulse',
              phase.state === 'pending' && 'border-[#1c2030] bg-transparent',
              phase.state === 'failed' && 'border-[#ff5c63] bg-[#ff5c63]',
            )}
            aria-label={`${phase.label}: ${phase.state}`}
          />
          {phase.state === 'done' && (
            <span className="w-6 h-px bg-[#7ae0ff] mx-0.5 phase-shimmer" aria-hidden="true" />
          )}
          <span
            className={cn(
              'text-[11px]',
              phase.state === 'done' && 'text-[#aab2c4]',
              phase.state === 'current' && 'text-white',
              (phase.state === 'pending' || phase.state === 'failed') && 'text-[#6b7388]',
            )}
          >
            {phase.label}
          </span>
        </div>
      ))}
    </div>
  )
}

export default PhaseRail
