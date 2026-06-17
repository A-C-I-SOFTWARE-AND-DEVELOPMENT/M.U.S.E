import type { AgentRunState } from '@/lib/types';

const MAP: Record<AgentRunState, { color: string; label: string }> = {
  idle: { color: 'var(--state-idle)', label: 'Idle' },
  running: { color: 'var(--state-running)', label: 'Running' },
  error: { color: 'var(--state-error)', label: 'Error' },
  'needs-auth': { color: 'var(--state-auth)', label: 'Needs auth' },
  unknown: { color: 'var(--ink-faint)', label: 'Unknown' },
};

export function StatusDot({ state, withLabel }: { state: AgentRunState; withLabel?: boolean }) {
  const m = MAP[state];
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="inline-block h-2 w-2 rounded-full"
        style={{
          background: m.color,
          boxShadow: state === 'running' ? `0 0 8px ${m.color}` : undefined,
        }}
      />
      {withLabel && <span className="mono text-[10px] text-[var(--ink-dim)]">{m.label}</span>}
    </span>
  );
}
