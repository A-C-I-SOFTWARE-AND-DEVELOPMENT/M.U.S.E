import { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FusionCore } from '@/components/axiom/FusionCore';
import { useNexusStore } from '@/store/useNexusStore';
import { runFusion, ALL_GATES } from '@/lib/fusion';
import { balancedWeights } from '@/lib/steering';
import { museSurface } from '@/adapters';
import type {
  AxiomGateKey,
  FusionSource,
  FusionStrategy,
  GateStatus,
  VertexDef,
  WeightVector,
} from '@/lib/types';
import { buildSteeringVector } from '@/lib/steering';

const STRATEGIES: { key: FusionStrategy; label: string; hint: string }[] = [
  { key: 'weighted-mean', label: 'Blend', hint: 'Weighted mean of all sources' },
  { key: 'max-axis', label: 'Union', hint: 'Per-axis maximum (widest intent)' },
  { key: 'owner-priority', label: 'Priority', hint: 'Lead source dominates' },
  { key: 'geometric', label: 'Consensus', hint: 'Geometric mean (punishes disagreement)' },
];

const STATUS_COLOR: Record<GateStatus, string> = {
  pass: 'var(--state-running)',
  warn: 'var(--state-auth)',
  fail: 'var(--state-error)',
  skipped: 'var(--ink-faint)',
};

// A factuality/safety-leaning baseline so fusion is always demonstrable and the
// Axiom Gate has a grounding anchor to fuse against.
function groundingBaseline(vertices: VertexDef[]): WeightVector {
  const w: WeightVector = {};
  vertices.forEach((v) => {
    w[v.key] =
      v.key === 'factuality' ? 0.34 : v.key === 'logic' || v.key === 'synthesis' ? 0.16 : 0.05;
  });
  const sum = Object.values(w).reduce((a, b) => a + b, 0);
  vertices.forEach((v) => (w[v.key] = w[v.key] / sum));
  return w;
}

export default function AxiomGatePage() {
  const vertices = useNexusStore((s) => s.vertices);
  const profiles = useNexusStore((s) => s.profiles);
  const lastVector = useNexusStore((s) => s.lastVector);
  const strategy = useNexusStore((s) => s.fusionStrategy);
  const setStrategy = useNexusStore((s) => s.setFusionStrategy);
  const gateConfig = useNexusStore((s) => s.gateConfig);
  const toggleGate = useNexusStore((s) => s.toggleGate);
  const setOwnerApproved = useNexusStore((s) => s.setOwnerApproved);
  const sourceContrib = useNexusStore((s) => s.sourceContrib);
  const setSourceContrib = useNexusStore((s) => s.setSourceContrib);

  // Build fusion sources: each profile that has a vector, the live octagon
  // vector, and a grounding baseline — at least two so fusion is meaningful.
  const sources = useMemo<FusionSource[]>(() => {
    const out: FusionSource[] = [];
    if (lastVector) {
      out.push({
        id: 'octagon',
        label: 'Octagon (current local vector)',
        kind: 'manual',
        weights: lastVector.weights,
        contribution: sourceContrib['octagon'] ?? 0.6,
      });
    }
    profiles
      .filter((p) => p.vector && p.id !== lastVector?.profileId)
      .forEach((p) =>
        out.push({
          id: p.id,
          label: p.name,
          kind: 'profile',
          weights: p.vector!.weights,
          contribution: sourceContrib[p.id] ?? 0.4,
        }),
      );
    out.push({
      id: 'baseline',
      label: 'Grounding baseline',
      kind: 'baseline',
      weights: groundingBaseline(vertices),
      contribution: sourceContrib['baseline'] ?? 0.35,
    });
    // Ensure ≥2 sources: if only baseline, add a balanced anchor.
    if (out.length < 2) {
      out.unshift({
        id: 'balanced',
        label: 'Balanced anchor',
        kind: 'baseline',
        weights: balancedWeights(vertices),
        contribution: sourceContrib['balanced'] ?? 0.5,
      });
    }
    return out;
  }, [lastVector, profiles, vertices, sourceContrib]);

  const result = useMemo(
    () => runFusion(sources, strategy, vertices, gateConfig),
    [sources, strategy, vertices, gateConfig],
  );

  const ownerPending = result.verdict === 'pending-owner';

  const applyFused = async () => {
    if (result.verdict !== 'attested') return;
    const v = buildSteeringVector('axiom-fused', { x: 0, y: 0 }, vertices);
    await museSurface.applySteering?.('default', { ...v, weights: result.fused, inference: result.inference });
  };

  const verdictMeta = {
    attested: { color: 'var(--state-running)', label: 'ATTESTED', sub: 'Verified · ready to apply' },
    'pending-owner': { color: 'var(--state-auth)', label: 'PENDING OWNER', sub: 'High-risk vector — approval required' },
    blocked: { color: 'var(--state-error)', label: 'BLOCKED', sub: 'An enforced gate failed' },
  }[result.verdict];

  return (
    <div className="px-4 pb-6">
      {/* Header strip */}
      <div className="glass mb-3 flex items-center justify-between px-3 py-2.5">
        <div>
          <div className="text-[13px] font-semibold">Axiom Gate</div>
          <div className="mono text-[10px] text-[var(--ink-dim)]">
            Intelligence proposes · the verifier disposes
          </div>
        </div>
        <motion.div
          key={result.verdict}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="mono rounded-full px-2.5 py-1 text-[10px] font-bold"
          style={{ background: `${verdictMeta.color}22`, color: verdictMeta.color }}
        >
          {verdictMeta.label}
        </motion.div>
      </div>

      {/* Fusion core visual */}
      <div className="glass flex flex-col items-center px-3 py-4">
        <FusionCore sources={sources} result={result} vertices={vertices} />
        <div className="mono mt-1 text-center text-[10px] text-[var(--ink-dim)]">
          {sources.length} sources · {STRATEGIES.find((s) => s.key === strategy)?.label} fusion ·{' '}
          {result.dominant ?? 'balanced'}
        </div>
      </div>

      {/* Strategy selector */}
      <div className="glass mt-3 px-3 py-3">
        <div className="hud-label mb-2">Fusion strategy</div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {STRATEGIES.map((s) => {
            const active = strategy === s.key;
            return (
              <button
                key={s.key}
                onClick={() => setStrategy(s.key)}
                className="relative rounded-[10px] border px-2 py-2 text-left transition-colors"
                style={{
                  borderColor: active ? 'var(--octa-glow)' : 'var(--hairline)',
                  background: active ? 'color-mix(in oklab, var(--octa-glow) 12%, transparent)' : 'transparent',
                }}
              >
                {active && (
                  <motion.span
                    layoutId="strat-dot"
                    className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full"
                    style={{ background: 'var(--octa-glow)' }}
                  />
                )}
                <div className="text-[12px] font-semibold">{s.label}</div>
                <div className="text-[9px] leading-tight text-[var(--ink-faint)]">{s.hint}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Source contributions */}
      <div className="glass mt-3 px-3 py-3">
        <div className="hud-label mb-2">Source contributions</div>
        <div className="flex flex-col gap-2.5">
          {sources.map((s) => (
            <div key={s.id} className="flex items-center gap-2.5">
              <span className="w-[112px] shrink-0 truncate text-[11px] font-medium">{s.label}</span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={s.contribution}
                onChange={(e) => setSourceContrib(s.id, parseFloat(e.target.value))}
                className="nexus-range h-1 flex-1"
                style={{ accentColor: 'var(--octa-glow)' }}
              />
              <span className="mono w-[34px] shrink-0 text-right text-[10px] text-[var(--ink-dim)]">
                {Math.round(s.contribution * 100)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* The 8-gate ladder */}
      <div className="glass mt-3 px-3 py-3">
        <div className="mb-2 flex items-center justify-between">
          <div className="hud-label">Verification gates</div>
          <div className="mono text-[9px] text-[var(--ink-faint)]">tap to enforce / relax</div>
        </div>
        <div className="flex flex-col gap-1.5">
          {ALL_GATES.map((key, i) => {
            const g = result.gates.find((x) => x.key === key)!;
            return (
              <motion.button
                key={key}
                onClick={() => toggleGate(key as AxiomGateKey)}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                className="flex items-center gap-2.5 rounded-[10px] border border-[var(--hairline)] px-2.5 py-2 text-left"
                style={{ opacity: g.enforced ? 1 : 0.55 }}
              >
                <span className="mono w-4 shrink-0 text-[9px] text-[var(--ink-faint)]">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{
                    background: STATUS_COLOR[g.status],
                    boxShadow: g.status === 'pass' ? `0 0 6px ${STATUS_COLOR[g.status]}` : undefined,
                  }}
                />
                <span className="w-[104px] shrink-0 text-[12px] font-medium">{g.label}</span>
                <span className="flex-1 truncate text-[10px] text-[var(--ink-dim)]">{g.detail}</span>
                <span
                  className="mono shrink-0 rounded-full px-1.5 py-0.5 text-[8px] uppercase"
                  style={{
                    color: g.enforced ? STATUS_COLOR[g.status] : 'var(--ink-faint)',
                    border: `1px solid ${g.enforced ? STATUS_COLOR[g.status] + '55' : 'var(--hairline)'}`,
                  }}
                >
                  {g.enforced ? g.status : 'relaxed'}
                </span>
              </motion.button>
            );
          })}
        </div>
      </div>

      {/* Owner approval (the challenge-bound gate) */}
      <AnimatePresence>
        {ownerPending && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="glass mt-3 overflow-hidden px-3 py-3"
            style={{ borderColor: 'var(--state-auth)' }}
          >
            <div className="text-[12px] font-semibold" style={{ color: 'var(--state-auth)' }}>
              Owner authorization required
            </div>
            <div className="mt-0.5 text-[11px] leading-snug text-[var(--ink-dim)]">
              This fused vector is high-risk. Per MUSE's owner gate, it stays deferred until you
              authorize.
            </div>
            <button
              onClick={() => setOwnerApproved(true)}
              className="mt-2.5 w-full rounded-md px-3 py-2 text-[12px] font-semibold text-black"
              style={{ background: 'var(--state-auth)' }}
            >
              Yes, with authorization
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Attestation + apply */}
      <div className="glass mt-3 px-3 py-3">
        <div className="flex items-center justify-between">
          <div>
            <div className="hud-label">Attestation</div>
            <div className="mono mt-1 text-[12px]" style={{ color: verdictMeta.color }}>
              {result.attestation ? `axiom:${result.attestation}` : '—'}
            </div>
            <div className="text-[10px] text-[var(--ink-faint)]">{verdictMeta.sub}</div>
          </div>
          {gateConfig.ownerApproved && (
            <button
              onClick={() => setOwnerApproved(false)}
              className="mono text-[9px] text-[var(--ink-dim)] underline"
            >
              revoke
            </button>
          )}
        </div>
        <button
          onClick={applyFused}
          disabled={result.verdict !== 'attested'}
          className="mt-3 w-full rounded-md px-3 py-2.5 text-[12px] font-semibold text-black transition-opacity disabled:cursor-not-allowed disabled:opacity-30"
          style={{ background: 'var(--octa-glow)' }}
        >
          {result.verdict === 'attested' ? 'Apply fused vector → M.U.S.E.' : 'Resolve gates to apply'}
        </button>
      </div>
    </div>
  );
}
