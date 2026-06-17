import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { allAvailableModels, clearModelCache, type CatalogModel } from '@/lib/modelCatalog';
import { configuredProviders } from '@/lib/providers';
import { getChatConfig, setChatConfig } from '@/lib/chat';

const TRANSPORT_COLOR: Record<string, string> = {
  direct: 'var(--state-running)',
  openrouter: 'var(--acc-creativity)',
  gateway: 'var(--acc-reasoning)',
  unavailable: 'var(--state-error)',
};
const TRANSPORT_LABEL: Record<string, string> = {
  direct: 'direct',
  openrouter: 'via OpenRouter',
  gateway: 'gateway',
  unavailable: 'unavailable',
};

export default function ModelsPage() {
  const navigate = useNavigate();
  const [models, setModels] = useState<CatalogModel[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [active, setActive] = useState(getChatConfig().model);
  const [providerFilter, setProviderFilter] = useState<string>('all');

  const load = (force = false) => {
    setLoading(true);
    allAvailableModels(force).then((m) => { setModels(m); setLoading(false); });
  };
  useEffect(() => { load(); }, []);

  const providers = configuredProviders();
  const filtered = useMemo(() => {
    if (!models) return [];
    const s = q.trim().toLowerCase();
    return models.filter((m) =>
      (providerFilter === 'all' || m.provider.id === providerFilter) &&
      (!s || m.id.toLowerCase().includes(s)),
    );
  }, [models, q, providerFilter]);

  const use = (id: string) => {
    setChatConfig({ model: id });
    setActive(id);
  };

  return (
    <div className="px-4 pb-6">
      <div className="glass mb-3 flex items-center justify-between px-3 py-2.5">
        <div>
          <div className="text-[13px] font-semibold">Models</div>
          <div className="mono text-[10px] text-[var(--ink-dim)]">
            {models?.length ?? 0} models · {providers.length} provider{providers.length === 1 ? '' : 's'}
          </div>
        </div>
        <button onClick={() => { clearModelCache(); load(true); }} className="mono text-[10px] text-[var(--octa-glow)]">↻ refresh</button>
      </div>

      {providers.length === 0 ? (
        <div className="glass px-4 py-8 text-center">
          <div className="text-[12px] text-[var(--ink-dim)]">No providers connected</div>
          <div className="mt-1 text-[10px] text-[var(--ink-faint)]">Add a provider key in Settings, then your models appear here.</div>
          <button onClick={() => navigate('/settings')} className="mt-3 rounded-md px-3 py-1.5 text-[11px] font-semibold text-black" style={{ background: 'var(--octa-glow)' }}>Open Settings</button>
        </div>
      ) : (
        <>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search models…" className="mb-2 w-full rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-3 py-2 text-[12px] text-[var(--ink)]" />
          <div className="mb-3 flex flex-wrap gap-1.5">
            <button onClick={() => setProviderFilter('all')} className="rounded-full border px-2.5 py-0.5 text-[10px]" style={{ borderColor: providerFilter === 'all' ? 'var(--octa-glow)' : 'var(--hairline)', color: providerFilter === 'all' ? 'var(--octa-glow)' : 'var(--ink-dim)' }}>all</button>
            {providers.map((p) => (
              <button key={p.id} onClick={() => setProviderFilter(p.id)} className="rounded-full border px-2.5 py-0.5 text-[10px]" style={{ borderColor: providerFilter === p.id ? 'var(--octa-glow)' : 'var(--hairline)', color: providerFilter === p.id ? 'var(--octa-glow)' : 'var(--ink-dim)' }}>{p.label}</button>
            ))}
          </div>

          {loading ? (
            <div className="py-6 text-center text-[12px] text-[var(--ink-dim)]">Loading models…</div>
          ) : (
            <div className="flex flex-col gap-1.5">
              {filtered.map((m) => {
                const isActive = m.id === active;
                return (
                  <button key={m.id} onClick={() => use(m.id)} className="glass flex items-center justify-between px-3 py-2 text-left active:scale-[0.99]" style={{ borderColor: isActive ? 'var(--octa-glow)' : undefined }}>
                    <div className="min-w-0">
                      <div className="mono truncate text-[12px] text-[var(--ink)]">{m.id}</div>
                      <div className="mono text-[9px] text-[var(--ink-faint)]">{m.provider.label}</div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <span className="mono rounded-full px-1.5 py-0.5 text-[8px]" style={{ color: TRANSPORT_COLOR[m.transport], border: `1px solid ${TRANSPORT_COLOR[m.transport]}55` }}>{TRANSPORT_LABEL[m.transport]}</span>
                      {isActive ? <span className="mono text-[10px]" style={{ color: 'var(--octa-glow)' }}>active ✓</span> : <span className="mono text-[10px] text-[var(--ink-faint)]">use</span>}
                    </div>
                  </button>
                );
              })}
              {filtered.length === 0 && <div className="py-6 text-center text-[11px] text-[var(--ink-dim)]">No models match.</div>}
            </div>
          )}
        </>
      )}
    </div>
  );
}
