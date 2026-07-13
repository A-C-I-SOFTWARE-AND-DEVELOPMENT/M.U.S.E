import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  assembleAgentContext,
  cppTrioSeed,
  type AdapterRef,
  type ForgeAgent,
  type KnowledgePack,
  type Persona,
} from '@/lib/forge';
import {
  putDoc,
  deleteDoc,
  listDocs,
  totalBytes,
  clearPack,
  exportPackJsonl,
  formatBytes,
  localStoreAvailable,
  type StoredDoc,
} from '@/lib/localStore';
import { cockpit, cockpitConfigured } from '@/adapters/cockpit';
import { useLinkState } from '@/lib/health';

const LS = 'nexus.forge.v1';
type DocMeta = Omit<StoredDoc, 'blob'>;
type TrainTarget = 'local' | 'gateway';
interface ForgeState {
  packs: KnowledgePack[];
  personas: Persona[];
  adapters: AdapterRef[];
  agents: ForgeAgent[];
  target: TrainTarget;
  localTrainerUrl: string;
}
function load(): ForgeState {
  try {
    const s = JSON.parse(localStorage.getItem(LS) ?? 'null');
    if (s) return { target: 'local', localTrainerUrl: 'http://127.0.0.1:8799/train', ...s };
  } catch { /* ignore */ }
  return { packs: [], personas: [], adapters: [], agents: [], target: 'local', localTrainerUrl: 'http://127.0.0.1:8799/train' };
}
function save(s: ForgeState) {
  try { localStorage.setItem(LS, JSON.stringify(s)); } catch { /* ignore */ }
}

export default function ForgePage() {
  const [state, setState] = useState<ForgeState>(load);
  const [sel, setSel] = useState<string | null>(state.agents[0]?.id ?? null);
  const [docs, setDocs] = useState<DocMeta[]>([]);
  const [usage, setUsage] = useState(0);
  const [trainMsg, setTrainMsg] = useState<Record<string, string>>({});
  const gatewayConnected = useLinkState() === 'gateway';
  const update = (s: ForgeState) => { setState(s); save(s); };

  const agent = state.agents.find((a) => a.id === sel) ?? null;
  const pack = state.packs.find((p) => p.id === agent?.packId) ?? null;
  const adapter = state.adapters.find((a) => a.id === agent?.adapterId) ?? null;

  const refreshDocs = useCallback(async () => {
    if (!localStoreAvailable()) return;
    setDocs(pack ? await listDocs(pack.id) : []);
    setUsage(await totalBytes());
  }, [pack]);

  useEffect(() => { void refreshDocs(); }, [refreshDocs]);

  const ctx = useMemo(
    () => (agent ? assembleAgentContext(agent, state.packs, state.personas, state.adapters) : null),
    [agent, state],
  );

  const seedTrio = () => {
    const seed = cppTrioSeed();
    update({
      ...state,
      packs: [...state.packs, ...seed.packs],
      personas: [...state.personas, ...seed.personas],
      adapters: [...state.adapters, ...seed.adapters],
      agents: [...state.agents, ...seed.agents],
    });
    setSel(seed.agents[0].id);
  };

  const upload = async (file: File) => {
    if (!pack) return;
    await putDoc(pack.id, file); // always stored ON-DEVICE (IndexedDB)
    await refreshDocs();
  };
  const removeDoc = async (id: string) => { await deleteDoc(id); await refreshDocs(); };
  const clearAll = async () => { if (pack) { await clearPack(pack.id); await refreshDocs(); } };
  const exportJsonl = async () => { if (pack) { const n = await exportPackJsonl(pack.id, pack.name); setTrainMsg((m) => ({ ...m, [pack.id]: `Exported ${n} records to JSONL` })); } };

  const trainAdapter = async () => {
    if (!adapter || !pack) return;
    if (state.target === 'gateway' && !gatewayConnected) {
      setTrainMsg((messages) => ({ ...messages, [adapter.id]: 'Requires a reachable gateway.' }));
      return;
    }
    const setAdapterStatus = (status: AdapterRef['status']) => update({
      ...state,
      adapters: state.adapters.map((entry) => (entry.id === adapter.id ? { ...entry, status } : entry)),
    });
    setAdapterStatus('training');
    if (state.target === 'local') {
      // Local training: data never leaves the device. POST the manifest to a
      // local trainer daemon the user runs (honest — the browser can't run QLoRA).
      try {
        const res = await fetch(state.localTrainerUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ adapter_id: adapter.id, base_model: adapter.baseModel, method: 'qlora', rank: adapter.rank, pack: pack.name, docs: docs.map((d) => d.name) }),
        });
        setAdapterStatus(res.ok ? 'training' : 'error');
        setTrainMsg((m) => ({ ...m, [adapter.id]: res.ok ? 'Local trainer acknowledged the job; completion is not yet reported.' : `Local trainer ${res.status} — or export JSONL and train offline` }));
      } catch {
        setAdapterStatus('error');
        setTrainMsg((m) => ({ ...m, [adapter.id]: `No local trainer at ${state.localTrainerUrl} — export the JSONL and run QLoRA/Unsloth locally` }));
      }
    } else {
      const r = await cockpit.rawPost('/learning', { type: 'adapter', adapter_id: adapter.id, method: 'qlora', rank: adapter.rank });
      setAdapterStatus(r ? 'training' : 'error');
      setTrainMsg((m) => ({ ...m, [adapter.id]: r ? 'Gateway acknowledged the training request; completion is not yet reported.' : cockpitConfigured() ? 'The gateway did not acknowledge the request.' : 'Requires gateway' }));
    }
  };

  return (
    <div className="px-4 pb-6">
      <div className="glass mb-3 px-3 py-2.5">
        <div className="text-[13px] font-semibold">The Forge</div>
        <div className="mono text-[10px] leading-snug text-[var(--ink-dim)]">
          Per-agent knowledge + specialization. Latent base knowledge is <b className="text-[var(--ink)]">scoped &amp; constrained</b>, not deleted.
        </div>
      </div>

      {/* Storage & training target */}
      <div className="glass mb-3 px-3 py-3">
        <div className="hud-label mb-2">Data &amp; training</div>
        <div className="flex gap-2">
          {(['local', 'gateway'] as TrainTarget[]).map((t) => (
            <button
              key={t}
              onClick={() => update({ ...state, target: t })}
              className="flex-1 rounded-md border px-2.5 py-2 text-left"
              style={{ borderColor: state.target === t ? 'var(--octa-glow)' : 'var(--hairline)' }}
            >
              <div className="text-[12px] font-semibold capitalize">{t === 'local' ? 'Local (on-device)' : 'Gateway'}</div>
              <div className="text-[9px] leading-tight text-[var(--ink-faint)]">{t === 'local' ? 'Data stays in this device’s storage; train via export or a local trainer.' : 'Send to the MUSE learning loop.'}</div>
            </button>
          ))}
        </div>
        <div className="mono mt-2 text-[9px] text-[var(--ink-faint)]">
          On-device storage: {formatBytes(usage)}{!localStoreAvailable() && ' · IndexedDB unavailable here'}
        </div>
        {state.target === 'local' && (
          <input
            value={state.localTrainerUrl}
            onChange={(e) => update({ ...state, localTrainerUrl: e.target.value })}
            placeholder="Local trainer URL (optional)"
            className="mono mt-2 w-full rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-2 py-1.5 text-[11px] text-[var(--ink)]"
          />
        )}
      </div>

      {state.agents.length === 0 && (
        <button onClick={seedTrio} className="mb-3 w-full rounded-md px-3 py-2.5 text-[12px] font-semibold text-black" style={{ background: 'var(--octa-glow)' }}>
          Seed the C++ specialist trio (worked example)
        </button>
      )}

      {state.agents.length > 0 && (
        <>
          <div className="hud-label mb-2">Specialists</div>
          <div className="mb-3 flex flex-wrap gap-2">
            {state.agents.map((a) => (
              <button key={a.id} onClick={() => setSel(a.id)} className="rounded-md border px-2.5 py-1.5 text-[11px]" style={{ borderColor: sel === a.id ? 'var(--octa-glow)' : 'var(--hairline)', color: sel === a.id ? 'var(--octa-glow)' : 'var(--ink)' }}>
                {a.name}
              </button>
            ))}
          </div>

          {agent && ctx && (
            <div className="flex flex-col gap-3">
              <div className="glass px-3 py-3">
                <div className="hud-label mb-1.5">Assembled context · {agent.name}</div>
                <div className="mono text-[10px] text-[var(--ink-dim)]">model: <span className="text-[var(--ink)]">{ctx.model}</span></div>
                <div className="mono text-[10px] text-[var(--ink-dim)]">namespace: <span className="text-[var(--ink)]">{ctx.retrievalNamespace ?? '—'}</span> · scoped: {String(ctx.scoped)}</div>
                <div className="mt-1.5 whitespace-pre-wrap rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-2.5 py-2 text-[11px] text-[var(--ink-dim)]">{ctx.systemPrompt}</div>
              </div>

              {/* Knowledge pack — on-device docs */}
              {pack && (
                <div className="glass px-3 py-3">
                  <div className="mb-2 flex items-center justify-between">
                    <div className="hud-label">Knowledge pack · {pack.name}</div>
                    {docs.length > 0 && <button onClick={clearAll} className="mono text-[9px] text-[var(--state-error)]">clear</button>}
                  </div>
                  {docs.length === 0 ? (
                    <div className="text-[11px] text-[var(--ink-dim)]">No documents — upload to scope this agent’s knowledge (stored on this device).</div>
                  ) : (
                    <div className="flex flex-col gap-1">
                      {docs.map((d) => (
                        <div key={d.id} className="mono flex items-center justify-between text-[10px]">
                          <span className="truncate text-[var(--ink)]">{d.name}</span>
                          <span className="flex items-center gap-2 text-[var(--ink-faint)]">
                            {formatBytes(d.bytes)}
                            <button onClick={() => removeDoc(d.id)} className="text-[var(--state-error)]">✕</button>
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="mt-2 flex flex-wrap gap-2">
                    <label>
                      <span className="inline-block cursor-pointer rounded-md border border-[var(--hairline)] px-2.5 py-1.5 text-[11px]">+ Upload doc</span>
                      <input type="file" className="hidden" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
                    </label>
                    {docs.length > 0 && (
                      <button onClick={exportJsonl} className="rounded-md border border-[var(--hairline)] px-2.5 py-1.5 text-[11px]">Export JSONL</button>
                    )}
                  </div>
                </div>
              )}

              {/* Adapter training */}
              {adapter && (
                <div className="glass px-3 py-3">
                  <div className="hud-label mb-1.5">Adapter · {adapter.name}</div>
                  <div className="mono text-[10px] text-[var(--ink-dim)]">base {adapter.baseModel} · QLoRA rank {adapter.rank} · target <span style={{ color: 'var(--octa-glow)' }}>{state.target}</span> · status <span style={{ color: adapter.status === 'ready' ? 'var(--state-running)' : adapter.status === 'training' ? 'var(--state-auth)' : 'var(--ink-faint)' }}>{adapter.status}</span></div>
                  <button onClick={trainAdapter} disabled={adapter.status === 'training'} className="mt-2 w-full rounded-md px-3 py-1.5 text-[11px] font-semibold text-black disabled:opacity-40" style={{ background: 'var(--octa-glow)' }}>
                    {adapter.status === 'training' ? 'Training…' : `Train adapter (${state.target})`}
                  </button>
                  {trainMsg[adapter.id] && <div className="mono mt-1 text-[10px] text-[var(--ink-dim)]">{trainMsg[adapter.id]}</div>}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
