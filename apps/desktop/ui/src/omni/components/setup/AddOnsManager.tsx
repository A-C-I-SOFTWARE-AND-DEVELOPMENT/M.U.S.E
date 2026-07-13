import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MCP_SERVERS,
  CLI_LANES,
  getCustomAddons,
  addCustomAddon,
  removeCustomAddon,
  addonConfigured,
  liveMcpAddons,
  type AddOn,
  type AddOnKind,
} from '@/lib/addons';
import { getCachedMirror, fetchMirror } from '@/lib/repoSync';
import { SecretField } from './SecretField';

function AddOnCard({ a, onRemove }: { a: AddOn; onRemove?: () => void }) {
  const [open, setOpen] = useState(false);
  const on = addonConfigured(a);
  return (
    <div className="glass overflow-hidden">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between px-3 py-2.5 text-left">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: on ? 'var(--state-auth)' : 'var(--ink-faint)' }} />
          <div>
            <div className="text-[12px] font-semibold">{a.label}{a.custom ? ' ·' : ''}<span className="text-[var(--ink-faint)]">{a.custom ? ' custom' : ''}</span></div>
            <div className="text-[9px] text-[var(--ink-faint)]">{a.blurb}{on ? ' · configured, not health-checked' : ''}</div>
          </div>
        </div>
        <span className="mono text-[12px] text-[var(--ink-dim)]">{open ? '−' : '+'}</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="flex flex-col gap-2.5 border-t border-[var(--hairline)] px-3 py-3">
              {a.fields.map((f) => <SecretField key={f.env} f={f} />)}
              {a.custom && onRemove && (
                <button onClick={onRemove} className="self-start rounded-md border border-[var(--state-error)] px-2.5 py-1 text-[10px] text-[var(--state-error)]">Remove</button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function AddYourOwn({ kind, onAdd }: { kind: AddOnKind; onAdd: (label: string) => void }) {
  const [label, setLabel] = useState('');
  return (
    <div className="flex gap-2">
      <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder={`Add your own ${kind}…`} className="flex-1 rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] px-2.5 py-1.5 text-[11px] text-[var(--ink)]" />
      <button onClick={() => { if (label.trim()) { onAdd(label.trim()); setLabel(''); } }} disabled={!label.trim()} className="rounded-md px-3 py-1.5 text-[11px] font-semibold text-black disabled:opacity-40" style={{ background: 'var(--octa-glow)' }}>+ Add</button>
    </div>
  );
}

export function AddOnsManager() {
  const [version, setVersion] = useState(0);
  const mirror = getCachedMirror();
  const [mcpList, setMcpList] = useState<AddOn[]>(() =>
    mirror ? liveMcpAddons(mirror.mcpServers, mirror.optionalMcps) : MCP_SERVERS,
  );
  useEffect(() => {
    const bump = () => setVersion((v) => v + 1);
    window.addEventListener('nexus:config', bump);
    // Reflect the live repo: hydrate the MCP list from the MUSE mirror.
    fetchMirror(false)
      .then((m) => {
        const live = liveMcpAddons(m.mcpServers, m.optionalMcps);
        if (live.length) setMcpList(live);
      })
      .catch(() => {/* offline → static fallback */});
    return () => window.removeEventListener('nexus:config', bump);
  }, []);
  const custom = getCustomAddons();

  const section = (title: string, kind: AddOnKind, builtins: AddOn[]) => {
    const mine = custom.filter((c) => c.kind === kind);
    return (
      <div key={kind}>
        <div className="hud-label mb-2">{title}</div>
        <div className="flex flex-col gap-2">
          {builtins.map((a) => <AddOnCard key={`${a.id}-${version}`} a={a} />)}
          {mine.map((a) => <AddOnCard key={`${a.id}-${version}`} a={a} onRemove={() => { removeCustomAddon(a.id); setVersion((v) => v + 1); }} />)}
        </div>
        <div className="mt-2">
          <AddYourOwn kind={kind} onAdd={(l) => { addCustomAddon(kind, l); setVersion((v) => v + 1); }} />
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[11px] leading-relaxed text-[var(--ink-dim)]">
        The full MUSE integration surface — MCP servers (mirrored live from <span className="mono">.mcp.json</span> + <span className="mono">optional-mcps/</span> on <b className="text-[var(--ink)]">main</b>) and CLI lanes — plus <b className="text-[var(--ink)]">add your own</b>.
        These run gateway-side; values are stored encrypted on-device and exported to <span className="mono">~/.hermes/.env</span>.
      </p>
      {section(`MCP servers · ${mcpList.length}`, 'mcp', mcpList)}
      {section('CLI lanes', 'cli', CLI_LANES)}
      {section('Custom providers', 'provider', [])}
    </div>
  );
}
