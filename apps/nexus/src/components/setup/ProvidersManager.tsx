import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { PROVIDERS, isConfigured, getProvider, type Provider } from '@/lib/providers';
import { getSecret, setSecret } from '@/lib/config';
import { SecretField } from './SecretField';

function ProviderCard({ p, onChange }: { p: Provider; onChange: () => void }) {
  const [open, setOpen] = useState(false);
  const configured = isConfigured(p);
  return (
    <div className="glass overflow-hidden">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between px-3 py-2.5 text-left">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: configured ? 'var(--state-running)' : 'var(--ink-faint)', boxShadow: configured ? '0 0 6px var(--state-running)' : undefined }} />
          <div>
            <div className="text-[12px] font-semibold">{p.label}</div>
            <div className="text-[9px] text-[var(--ink-faint)]">{p.browserDirect ? 'browser-direct' : 'via OpenRouter / gateway'}{p.local ? ' · local' : ''}</div>
          </div>
        </div>
        <span className="mono text-[12px] text-[var(--ink-dim)]">{open ? '−' : '+'}</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="flex flex-col gap-2.5 border-t border-[var(--hairline)] px-3 py-3" onBlur={onChange}>
              {p.note && <p className="text-[10px] leading-snug text-[var(--ink-dim)]">{p.note}</p>}
              {p.id === 'custom' && (
                <SecretField f={{ env: 'CUSTOM_BASE_URL', label: 'Base URL (OpenAI-compatible)', type: 'url', placeholder: 'https://…/v1' }} />
              )}
              {!p.local && <SecretField f={{ env: p.keyEnv, label: 'API key', type: 'password', placeholder: 'sk-…' }} />}
              {p.local && <p className="text-[10px] text-[var(--ink-faint)]">No key needed — runs at {p.baseUrl}.</p>}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function ProvidersManager() {
  const navigate = useNavigate();
  const [version, setVersion] = useState(0);
  const [q, setQ] = useState('');
  useEffect(() => {
    const bump = () => setVersion((v) => v + 1);
    window.addEventListener('nexus:config', bump);
    return () => window.removeEventListener('nexus:config', bump);
  }, []);

  const connected = PROVIDERS.filter((p) => isConfigured(p));
  const list = PROVIDERS.filter((p) => (p.label + ' ' + p.id).toLowerCase().includes(q.trim().toLowerCase()));

  return (
    <div className="flex flex-col gap-3">
      <p className="text-[11px] leading-relaxed text-[var(--ink-dim)]">
        Enter a key for any provider — Claude, GPT, Gemini, Groq, Mistral, DeepSeek & more. CORS-friendly
        ones run straight from this app; others auto-route via OpenRouter or the gateway. Models appear in the
        <button onClick={() => navigate('/models')} className="mx-1 underline" style={{ color: 'var(--octa-glow)' }}>Models tab</button>.
      </p>

      {connected.length > 0 && (
        <div className="glass px-3 py-2.5">
          <div className="hud-label mb-1.5">Connected · {connected.length}</div>
          <div className="flex flex-wrap gap-1.5">
            {connected.map((p) => (
              <span key={p.id} className="mono rounded-full px-2 py-0.5 text-[10px]" style={{ background: 'rgba(52,229,200,0.14)', color: 'var(--state-running)' }}>{p.label}</span>
            ))}
          </div>
        </div>
      )}

      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search providers…" className="w-full rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-3 py-2 text-[12px] text-[var(--ink)]" />

      <div key={version} className="flex flex-col gap-2">
        {list.map((p) => <ProviderCard key={p.id} p={p} onChange={() => setVersion((v) => v + 1)} />)}
      </div>
    </div>
  );
}

// re-export so callers can wire elsewhere
export { getProvider, getSecret, setSecret };
