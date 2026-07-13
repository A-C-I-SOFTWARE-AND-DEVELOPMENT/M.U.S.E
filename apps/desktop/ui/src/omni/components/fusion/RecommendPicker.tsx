import { useState } from 'react';
import { classifyTask, recommendFusions, type FusionRecommendation } from '@/lib/recommend';
import { shapeOf, type FusionDef } from '@/lib/fusionTypes';

// "Describe what you need" → 2–4 ranked fusion recommendation cards.
export function RecommendPicker({ onRun, onSave }: { onRun: (d: FusionDef) => void; onSave: (d: FusionDef) => void }) {
  const [desc, setDesc] = useState('');
  const [recs, setRecs] = useState<FusionRecommendation[] | null>(null);

  const go = () => {
    const profile = classifyTask(desc);
    setRecs(recommendFusions(profile));
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="glass px-3 py-2.5">
        <textarea
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          rows={2}
          placeholder="Describe what you need — e.g. “rigorously prove a C++ design is thread-safe”"
          className="w-full resize-none bg-transparent text-[13px] text-[var(--ink)] outline-none"
        />
        <button onClick={go} disabled={!desc.trim()} className="mt-1 w-full rounded-md py-2 text-[12px] font-semibold text-black disabled:opacity-40" style={{ background: 'var(--octa-glow)' }}>
          Recommend fusions
        </button>
      </div>

      {recs && (
        <div className="flex flex-col gap-2">
          {recs.map((r, i) => (
            <div key={i} className="glass px-3 py-2.5">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-semibold">{r.preset.name}</span>
                <span className="mono text-[9px] uppercase text-[var(--ink-faint)]">{shapeOf(r.preset)}</span>
              </div>
              <div className="mt-0.5 text-[11px] leading-snug text-[var(--ink-dim)]">{r.rationale}</div>
              <div className="mono mt-1 flex gap-3 text-[9px] text-[var(--ink-faint)]">
                <span>~${r.estCostUsd.toFixed(3)}</span>
                <span>~{(r.estLatencyMs / 1000).toFixed(1)}s</span>
                <span>conf {(r.confidence * 100).toFixed(0)}%</span>
              </div>
              <div className="mt-2 flex gap-2">
                <button onClick={() => onRun(r.preset)} className="flex-1 rounded-md py-1.5 text-[11px] font-semibold text-black" style={{ background: 'var(--octa-glow)' }}>Run</button>
                <button onClick={() => onSave(r.preset)} className="rounded-md border border-[var(--hairline)] px-2.5 py-1.5 text-[11px]">Save</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
