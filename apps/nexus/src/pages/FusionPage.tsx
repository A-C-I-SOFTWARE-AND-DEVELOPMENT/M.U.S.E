import { useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { FusionGraph } from '@/components/fusion/FusionGraph';
import { RecommendPicker } from '@/components/fusion/RecommendPicker';
import { PRESETS, clonePreset } from '@/lib/presets';
import { streamFusion, type FusionMeta } from '@/lib/fusionClient';
import { shapeOf, type FusionDef, type LegResult } from '@/lib/fusionTypes';
import { useNexusStore } from '@/store/useNexusStore';
import { effectiveTransport } from '@/lib/chat';
import { hasDirectKey } from '@/lib/directProvider';

type Tab = 'presets' | 'recommend' | 'history';

export default function FusionPage() {
  const saved = useNexusStore((s) => s.savedFusions);
  const favorites = useNexusStore((s) => s.fusionFavorites);
  const history = useNexusStore((s) => s.fusionHistory);
  const saveFusion = useNexusStore((s) => s.saveFusion);
  const toggleFav = useNexusStore((s) => s.toggleFusionFavorite);
  const addRun = useNexusStore((s) => s.addFusionRun);

  const [tab, setTab] = useState<Tab>('presets');
  const [active, setActive] = useState<FusionDef | null>(null);
  const [prompt, setPrompt] = useState('');
  const [output, setOutput] = useState('');
  const [legs, setLegs] = useState<LegResult[]>([]);
  const [meta, setMeta] = useState<FusionMeta | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const abortRef = useRef<AbortController | null>(null);

  const all = useMemo(() => {
    const list = [...saved, ...PRESETS];
    return list.sort((a, b) => Number(favorites.includes(b.id)) - Number(favorites.includes(a.id)));
  }, [saved, favorites]);

  const run = async (def: FusionDef) => {
    setActive(def);
    setOutput('');
    setLegs([]);
    setMeta(null);
    setErr('');
    if (!prompt.trim()) {
      setErr('Enter a prompt to run the fusion.');
      return;
    }
    setBusy(true);
    abortRef.current = new AbortController();
    const started = Date.now();
    try {
      const res = await streamFusion(
        def,
        [{ role: 'user', content: prompt }],
        (leg) => setLegs((l) => [...l, leg]),
        (delta) => setOutput((o) => o + delta),
        abortRef.current.signal,
      );
      setMeta(res.meta);
      addRun({
        id: `run-${Date.now()}`,
        fusionId: def.id,
        fusionName: def.name,
        prompt,
        legs: res.meta?.legs?.map((l) => ({ model: l.model, role: l.role as any, layer: l.layer, content: l.content ?? '', error: l.error })) ?? [],
        output: res.output,
        attestation: res.meta?.attestation ?? null,
        costUsd: 0,
        latencyMs: Date.now() - started,
        timestamp: Date.now(),
      });
    } catch (e) {
      setErr(String((e as Error).message ?? e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-4 pb-6">
      {/* Tabs */}
      <div className="glass mb-3 flex gap-1 p-1">
        {(['presets', 'recommend', 'history'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="relative flex-1 rounded-md py-1.5 text-[11px] font-medium capitalize"
            style={{ color: tab === t ? 'var(--ink)' : 'var(--ink-dim)' }}
          >
            {tab === t && <motion.span layoutId="fusion-tab" className="absolute inset-0 -z-0 rounded-md" style={{ background: 'color-mix(in oklab, var(--octa-glow) 14%, transparent)' }} />}
            <span className="relative z-10">{t}</span>
          </button>
        ))}
      </div>

      {/* Prompt */}
      <div className="glass mb-3 px-3 py-2.5">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={2}
          placeholder="Prompt for the fusion run…"
          className="w-full resize-none bg-transparent text-[13px] text-[var(--ink)] outline-none"
        />
      </div>

      {!(effectiveTransport() === 'direct' ? hasDirectKey() : true) && (
        <div className="mono mb-3 rounded-md border border-[var(--hairline)] px-3 py-2 text-[10px] text-[var(--ink-dim)]">
          Add an OpenRouter key in Settings → Credentials to run fusions directly — no gateway, no terminal.
        </div>
      )}

      {tab === 'recommend' && (
        <RecommendPicker
          onRun={(def) => { setTab('presets'); run(def); }}
          onSave={(def) => saveFusion(clonePreset(def, def.name))}
        />
      )}

      {tab === 'history' && (
        <div className="flex flex-col gap-2">
          {history.length === 0 ? (
            <div className="glass px-4 py-6 text-center text-[11px] text-[var(--ink-dim)]">No fusion runs yet</div>
          ) : (
            history.map((r) => (
              <div key={r.id} className="glass px-3 py-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[12px] font-medium">{r.fusionName}</span>
                  <span className="mono text-[9px] text-[var(--ink-faint)]">{(r.latencyMs / 1000).toFixed(1)}s</span>
                </div>
                <div className="mt-0.5 truncate text-[10px] text-[var(--ink-dim)]">{r.prompt}</div>
                {r.attestation && <div className="mono mt-1 text-[9px]" style={{ color: 'var(--state-running)' }}>{r.attestation}</div>}
              </div>
            ))
          )}
        </div>
      )}

      {tab === 'presets' && (
        <>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            {all.map((def) => (
              <div key={def.id} className="glass flex flex-col gap-2 px-3 py-2.5">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-[13px] font-semibold">{def.name}</div>
                    <div className="mono text-[9px] uppercase text-[var(--ink-faint)]">
                      {shapeOf(def)} · {def.displayMode}{def.attest ? ' · attest' : ''}
                    </div>
                  </div>
                  <button onClick={() => toggleFav(def.id)} className="text-[14px]" style={{ color: favorites.includes(def.id) ? 'var(--state-auth)' : 'var(--ink-faint)' }}>
                    {favorites.includes(def.id) ? '★' : '☆'}
                  </button>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => run(def)} disabled={busy} className="flex-1 rounded-md py-1.5 text-[11px] font-semibold text-black disabled:opacity-40" style={{ background: 'var(--octa-glow)' }}>
                    Run
                  </button>
                  <button onClick={() => saveFusion(clonePreset(def))} className="rounded-md border border-[var(--hairline)] px-2.5 py-1.5 text-[11px]">
                    Clone
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Active run */}
          {active && (
            <div className="glass mt-3 px-3 py-3">
              <div className="flex items-center justify-between">
                <div className="hud-label">{active.name}</div>
                {busy && <button onClick={() => abortRef.current?.abort()} className="mono text-[10px] text-[var(--state-error)]">stop</button>}
              </div>
              <div className="my-2 flex justify-center">
                <FusionGraph def={active} active={busy} />
              </div>
              {err && <div className="mono text-[10px] text-[var(--state-error)]">{err}</div>}
              {active.displayMode === 'transparent' && legs.length > 0 && (
                <div className="mb-2 flex flex-col gap-1.5">
                  {legs.map((l, i) => (
                    <details key={i} className="rounded-md border border-[var(--hairline)] px-2.5 py-1.5">
                      <summary className="mono cursor-pointer text-[10px]" style={{ color: l.error ? 'var(--state-error)' : 'var(--ink-dim)' }}>
                        {l.role} · {l.model}{l.error ? ' · failed' : ''}
                      </summary>
                      <div className="mt-1 whitespace-pre-wrap text-[11px] text-[var(--ink-dim)]">{l.error ?? l.content}</div>
                    </details>
                  ))}
                </div>
              )}
              {output && (
                <div className="rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-3 py-2.5">
                  <div className="hud-label mb-1">{active.aggregator ? 'Synthesized answer' : 'Answer'}</div>
                  <div className="whitespace-pre-wrap text-[13px] leading-relaxed text-[var(--ink)]">{output}</div>
                </div>
              )}
              {meta?.attestation && <div className="mono mt-2 text-[10px]" style={{ color: 'var(--state-running)' }}>{meta.attestation}</div>}
            </div>
          )}
        </>
      )}
    </div>
  );
}
