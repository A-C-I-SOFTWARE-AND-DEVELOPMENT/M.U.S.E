import { useCallback, useMemo, useState } from 'react';
import { Octagon } from '@/components/octagon/Octagon';
import { VertexSliders } from '@/components/octagon/VertexSliders';
import { TelemetryPanel } from '@/components/octagon/TelemetryPanel';
import { useNexusStore } from '@/store/useNexusStore';
import {
  positionToWeights,
  weightsToPosition,
  buildSteeringVector,
  type Point,
} from '@/lib/steering';
import type { SteeringVector } from '@/lib/types';
import { museSurface } from '@/adapters';

export default function SteerPage() {
  const vertices = useNexusStore((s) => s.vertices);
  const presetKey = useNexusStore((s) => s.presetKey);
  const setPreset = useNexusStore((s) => s.setPreset);
  const profiles = useNexusStore((s) => s.profiles);
  const activeId = useNexusStore((s) => s.activeProfileId);
  const setActive = useNexusStore((s) => s.setActiveProfile);
  const addProfile = useNexusStore((s) => s.addProfile);
  const toggleLock = useNexusStore((s) => s.toggleLock);
  const emitVector = useNexusStore((s) => s.emitVector);

  const active = profiles.find((p) => p.id === activeId)!;
  const [node, setNode] = useState<Point>({ x: 0, y: 0 });
  const [vector, setVector] = useState<SteeringVector | null>(null);

  const weights = useMemo(() => positionToWeights(node, vertices), [node, vertices]);

  const handleVector = useCallback(
    (v: SteeringVector) => {
      setVector(v);
      emitVector(v);
    },
    [emitVector],
  );

  // Slider override: nudge an axis, then re-solve the node to the new centroid.
  const handleAxis = useCallback(
    (key: string, value: number) => {
      const next = { ...weights, [key]: value };
      const sum = Object.values(next).reduce((a, b) => a + b, 0) || 1;
      Object.keys(next).forEach((k) => (next[k] = next[k] / sum));
      setNode(weightsToPosition(next, vertices));
    },
    [weights, vertices],
  );

  const balance = () => setNode({ x: 0, y: 0 });

  const applyToMuse = async () => {
    const v = vector ?? buildSteeringVector(active.id, node, vertices);
    await museSurface.applySteering?.('default', v);
  };

  return (
    <div className="px-4 pb-6">
      {/* Header strip: profile + state label */}
      <div className="glass mb-3 flex items-center justify-between px-3 py-2.5">
        <div className="flex items-center gap-2">
          <select
            value={activeId}
            onChange={(e) => setActive(e.target.value)}
            className="mono rounded-md bg-[var(--panel-solid)] px-2 py-1 text-[11px] text-[var(--ink)]"
          >
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <button
            onClick={() => addProfile(`Profile ${profiles.length + 1}`)}
            className="grid h-6 w-6 place-items-center rounded-md border border-[var(--hairline)] text-[var(--ink-dim)]"
          >
            +
          </button>
        </div>
        <div
          className="mono text-[11px] font-semibold"
          style={{ color: 'var(--octa-glow)' }}
        >
          {vector?.glowState.label ?? 'Balanced'}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[200px_1fr]">
        <TelemetryPanel />

        <div className="glass flex flex-col items-center px-3 py-4">
          <Octagon
            vertices={vertices}
            profileId={active.id}
            locked={active.locked}
            node={node}
            onNodeChange={setNode}
            onVector={handleVector}
          />
          <div className="mt-1 text-center">
            <div className="text-[13px] font-semibold tracking-wide">
              Agent Optimization Control
            </div>
            <div className="mono mt-0.5 text-[10px] text-[var(--ink-dim)]">
              Real-time inference steering · {presetKey.toUpperCase()} preset
            </div>
          </div>

          {/* Controls */}
          <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
            <button
              onClick={balance}
              className="rounded-md border border-[var(--hairline)] px-3 py-1.5 text-[11px] font-medium text-[var(--ink)]"
            >
              Balance
            </button>
            <button
              onClick={() => toggleLock(active.id)}
              className="rounded-md border px-3 py-1.5 text-[11px] font-medium"
              style={{
                borderColor: active.locked ? 'var(--octa-glow)' : 'var(--hairline)',
                color: active.locked ? 'var(--octa-glow)' : 'var(--ink)',
              }}
            >
              {active.locked ? 'Locked' : 'Lock'}
            </button>
            <button
              onClick={() => setPreset(presetKey === 'default' ? 'ops' : 'default')}
              className="rounded-md border border-[var(--hairline)] px-3 py-1.5 text-[11px] font-medium text-[var(--ink)]"
            >
              {presetKey === 'default' ? 'Ops preset' : 'Default preset'}
            </button>
            <button
              onClick={applyToMuse}
              className="rounded-md px-3 py-1.5 text-[11px] font-semibold text-black"
              style={{ background: 'var(--octa-glow)' }}
            >
              Apply → M.U.S.E.
            </button>
          </div>
        </div>
      </div>

      {/* Fine sliders */}
      <div className="glass mt-3 px-3 py-3">
        <div className="hud-label mb-2.5">Weight Adjustment · deviation from neutral</div>
        <VertexSliders
          vertices={vertices}
          weights={weights}
          onAxis={handleAxis}
          disabled={active.locked}
        />
      </div>

      {/* Mapped inference payload (the practical output) */}
      {vector && (
        <div className="glass mt-3 px-3 py-3">
          <div className="hud-label mb-2">Mapped inference params</div>
          <div className="mono grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-[var(--ink-dim)] sm:grid-cols-3">
            <Param k="temperature" v={vector.inference.temperature.toFixed(2)} />
            <Param k="top_p" v={vector.inference.topP.toFixed(2)} />
            <Param k="think_tokens" v={String(vector.inference.maxThinkingTokens)} />
            <Param k="grounding" v={vector.inference.groundingStrength.toFixed(2)} />
            <Param k="dominant" v={vector.dominant ?? '—'} />
            <Param k="style" v={vector.inference.systemStyleHint} />
          </div>
        </div>
      )}
    </div>
  );
}

function Param({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-[var(--hairline)] py-0.5">
      <span className="text-[var(--ink-faint)]">{k}</span>
      <span className="text-[var(--ink)]">{v}</span>
    </div>
  );
}
