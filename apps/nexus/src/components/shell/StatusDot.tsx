import type { AgentRunState } from '@/lib/types';

// The cockpit "Singularity" status dot. Four matte UI-status colours + one live
// cyan pulse — never brand art, never a bloom. The dot is a flat tonal mark; the
// only motion is the `live` cyan opacity pulse, which is neutralised under
// prefers-reduced-motion (see tokens.css's reduced-motion block). Colours come
// straight from the Singularity tokens: --ok / --warn / --danger / --ring-1.

// The four cockpit dot states. `live` is the cyan ring pulse; `off` is the idle
// disconnected mute. AgentRunState maps onto these so every existing call site
// (state={...} / withLabel) keeps working unchanged.
type DotState = 'ok' | 'warn' | 'danger' | 'live' | 'off';

const STATE_MAP: Record<AgentRunState, { dot: DotState; color: string; label: string }> = {
  idle: { dot: 'off', color: 'var(--signal-mute)', label: 'Idle' },
  running: { dot: 'live', color: 'var(--ring-1)', label: 'Running' },
  error: { dot: 'danger', color: 'var(--danger)', label: 'Error' },
  'needs-auth': { dot: 'warn', color: 'var(--warn)', label: 'Needs auth' },
  unknown: { dot: 'off', color: 'var(--signal-mute)', label: 'Unknown' },
};

const DOT_COLOR: Record<DotState, string> = {
  ok: 'var(--ok)',
  warn: 'var(--warn)',
  danger: 'var(--danger)',
  live: 'var(--ring-1)',
  off: 'var(--signal-mute)',
};

// The live cyan pulse is a matte opacity fade (1 → 0.4), exactly like the
// cockpit's `dot-pulse`. Defined here (scoped, idempotent) so the component is
// self-contained and the keyframe lives with the dot it animates. The global
// prefers-reduced-motion block in tokens.css already neutralises animation
// durations, so the pulse stops for reduced-motion users.
const PULSE_CSS = `
@keyframes nexus-dot-pulse { from { opacity: 1; } to { opacity: 0.4; } }
.nexus-dot-live { animation: nexus-dot-pulse 350ms cubic-bezier(0.2,0,0,1) infinite alternate; }
@media (prefers-reduced-motion: reduce) { .nexus-dot-live { animation: none; } }
`;

/**
 * A bare cockpit status dot driven directly by a {@link DotState}. Exposed for
 * surfaces (like the live header pill) that already know the cockpit dot state
 * rather than an agent run state.
 */
export function Dot({ state }: { state: DotState }) {
  return (
    <>
      <style>{PULSE_CSS}</style>
      <span
        className={`inline-block h-2 w-2 shrink-0 rounded-full${state === 'live' ? ' nexus-dot-live' : ''}`}
        style={{ background: DOT_COLOR[state] }}
      />
    </>
  );
}

/**
 * Agent run-state dot. Keeps the original `{ state, withLabel }` prop contract
 * (consumed by AgentsPage and ConsolePage), now rendered in the Singularity dot
 * language.
 */
export function StatusDot({ state, withLabel }: { state: AgentRunState; withLabel?: boolean }) {
  const m = STATE_MAP[state];
  return (
    <span className="inline-flex items-center gap-1.5">
      <Dot state={m.dot} />
      {withLabel && <span className="mono text-[10px] text-[var(--ink-dim)]">{m.label}</span>}
    </span>
  );
}
