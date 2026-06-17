import { useMemo, useState } from 'react';
import {
  assembleAgentContext,
  cppTrioSeed,
  type AdapterRef,
  type ForgeAgent,
  type KnowledgePack,
  type Persona,
} from '@/lib/forge';
import { cockpit, cockpitConfigured } from '@/adapters/cockpit';

const LS = 'nexus.forge.v1';
type ForgeState = { packs: KnowledgePack[]; personas: Persona[]; adapters: AdapterRef[]; agents: ForgeAgent[] };
function load(): ForgeState {
  try {
    const s = JSON.parse(localStorage.getItem(LS) ?? 'null');
    if (s) return s;
  } catch { /* ignore */ }
  return { packs: [], personas: [], adapters: [], agents: [] };
}
function save(s: ForgeState) {
  try { localStorage.setItem(LS, JSON.stringify(s)); } catch { /* ignore */ }
}

export default function ForgePage() {
  const [state, setState] = useState<ForgeState>(load);
  const [sel, setSel] = useState<string | null>(state.agents[0]?.id ?? null);
  const [trainMsg, setTrainMsg] = useState<Record<string, string>>({});
  const update = (s: ForgeState) => { setState(s); save(s); };

  const seedTrio = () => {
    const seed = cppTrioSeed();
    const next: ForgeState = {
      packs: [...state.packs, ...seed.packs],
      personas: [...state.personas, ...seed.personas],
      adapters: [...state.adapters, ...seed.adapters],
      agents: [...state.agents, ...seed.agents],
    };
    update(next);
    setSel(seed.agents[0].id);
  };

  const agent = state.agents.find((a) => a.id === sel) ?? null;
  const ctx = useMemo(
    () => (agent ? assembleAgentContext(agent, state.packs, state.personas, state.adapters) : null),
    [agent, state],
  );

  const addDoc = (packId: string, file: File) => {
    update({
      ...state,
      packs: state.packs.map((p) =>
        p.id === packId ? { ...p, docs: [...p.docs, { id: `doc-${Date.now()}`, name: file.name, bytes: file.size, status: 'pending' }] } : p,
      ),
    });
  };

  const trainAdapter = async (adapterId: string) => {
    update({ ...state, adapters: state.adapters.map((a) => (a.id === adapterId ? { ...a, status: 'training' } : a)) });
    // Kick the real learning loop; honest server-side progress (no fake completion).
    const r = await cockpit.rawPost('/learning', { type: 'adapter', adapter_id: adapterId, method: 'qlora', rank: 16 });
    setTrainMsg((m) => ({ ...m, [adapterId]: r ? 'Training job submitted to gateway' : cockpitConfigured() ? 'Submit failed' : 'Requires gateway (apps/nexus/server + MUSE learning loop)' }));
  };

  return (
    <div className="px-4 pb-6">
      <div className="glass mb-3 px-3 py-2.5">
        <div className="text-[13px] font-semibold">The Forge</div>
        <div className="mono text-[10px] leading-snug text-[var(--ink-dim)]">
          Per-agent knowledge + specialization. Honest caveat: base-model latent knowledge is
          <b className="text-[var(--ink)]"> scoped &amp; constrained</b>, not deleted — pack + persona (+ optional LoRA).
        </div>
      </div>

      {state.agents.length === 0 && (
        <button onClick={seedTrio} className="mb-3 w-full rounded-md px-3 py-2.5 text-[12px] font-semibold text-black" style={{ background: 'var(--octa-glow)' }}>
          Seed the C++ specialist trio (worked example)
        </button>
      )}

      {/* Agent roster */}
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
              {/* Assembled context */}
              <div className="glass px-3 py-3">
                <div className="hud-label mb-1.5">Assembled context · {agent.name}</div>
                <div className="mono text-[10px] text-[var(--ink-dim)]">model: <span className="text-[var(--ink)]">{ctx.model}</span></div>
                <div className="mono text-[10px] text-[var(--ink-dim)]">namespace: <span className="text-[var(--ink)]">{ctx.retrievalNamespace ?? '—'}</span> · scoped: {String(ctx.scoped)}</div>
                <div className="mt-1.5 whitespace-pre-wrap rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-2.5 py-2 text-[11px] text-[var(--ink-dim)]">{ctx.systemPrompt}</div>
              </div>

              {/* Knowledge pack */}
              {(() => {
                const pack = state.packs.find((p) => p.id === agent.packId);
                if (!pack) return null;
                return (
                  <div className="glass px-3 py-3">
                    <div className="hud-label mb-2">Knowledge pack · {pack.name}</div>
                    {pack.docs.length === 0 ? (
                      <div className="text-[11px] text-[var(--ink-dim)]">No documents — upload to scope this agent's knowledge.</div>
                    ) : (
                      <div className="flex flex-col gap-1">
                        {pack.docs.map((d) => (
                          <div key={d.id} className="mono flex items-center justify-between text-[10px]">
                            <span className="truncate text-[var(--ink)]">{d.name}</span>
                            <span className="text-[var(--ink-faint)]">{d.status}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    <label className="mt-2 block">
                      <span className="inline-block cursor-pointer rounded-md border border-[var(--hairline)] px-2.5 py-1.5 text-[11px]">+ Upload doc</span>
                      <input type="file" className="hidden" onChange={(e) => e.target.files?.[0] && addDoc(pack.id, e.target.files[0])} />
                    </label>
                  </div>
                );
              })()}

              {/* Adapter training */}
              {(() => {
                const adapter = state.adapters.find((a) => a.id === agent.adapterId);
                if (!adapter) return null;
                return (
                  <div className="glass px-3 py-3">
                    <div className="hud-label mb-1.5">Adapter · {adapter.name}</div>
                    <div className="mono text-[10px] text-[var(--ink-dim)]">base {adapter.baseModel} · QLoRA rank {adapter.rank} · status <span style={{ color: adapter.status === 'ready' ? 'var(--state-running)' : adapter.status === 'training' ? 'var(--state-auth)' : 'var(--ink-faint)' }}>{adapter.status}</span></div>
                    <button onClick={() => trainAdapter(adapter.id)} disabled={adapter.status === 'training'} className="mt-2 w-full rounded-md border border-[var(--hairline)] px-3 py-1.5 text-[11px] disabled:opacity-40">
                      {adapter.status === 'training' ? 'Training…' : 'Train adapter (QLoRA)'}
                    </button>
                    {trainMsg[adapter.id] && <div className="mono mt-1 text-[10px] text-[var(--ink-dim)]">{trainMsg[adapter.id]}</div>}
                  </div>
                );
              })()}
            </div>
          )}
        </>
      )}
    </div>
  );
}
