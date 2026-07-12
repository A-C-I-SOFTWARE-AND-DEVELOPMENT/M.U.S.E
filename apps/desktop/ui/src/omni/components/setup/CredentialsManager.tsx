import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CRED_CATEGORIES,
  INTEGRATIONS,
  gatewayEnvKeys,
  integrationsByCategory,
  type CredField,
  type Integration,
} from '@/lib/credentials';
import {
  getConfig,
  getSecret,
  setConfig,
  setSecret,
  envSnippet,
} from '@/lib/config';

function fieldValue(f: CredField): string {
  if (f.configKey) return (getConfig() as any)[f.configKey] ?? '';
  return getSecret(f.env);
}

function saveField(f: CredField, value: string) {
  if (f.configKey) setConfig({ [f.configKey]: value } as any);
  else setSecret(f.env, value);
}

function Field({ f }: { f: CredField }) {
  const [val, setVal] = useState(fieldValue(f));
  const [reveal, setReveal] = useState(false);
  const [saved, setSaved] = useState(false);
  const isSecret = f.type === 'password';
  return (
    <div className="flex flex-col gap-1">
      <label className="hud-label">{f.label}</label>
      <div className="flex gap-2">
        <input
          value={val}
          onChange={(e) => {
            setVal(e.target.value);
            setSaved(false);
          }}
          onBlur={() => {
            saveField(f, val.trim());
            setSaved(true);
          }}
          type={isSecret && !reveal ? 'password' : 'text'}
          placeholder={f.placeholder}
          autoComplete="off"
          autoCapitalize="off"
          spellCheck={false}
          className="flex-1 rounded-md border px-2.5 py-2 text-[12px] text-[var(--ink)]"
          style={{ borderColor: saved ? 'var(--state-running)' : 'var(--hairline)', background: 'var(--panel-solid)' }}
        />
        {isSecret && (
          <button onClick={() => setReveal((r) => !r)} className="rounded-md border border-[var(--hairline)] px-2 text-[11px] text-[var(--ink-dim)]">
            {reveal ? '🙈' : '👁'}
          </button>
        )}
      </div>
      <div className="mono text-[8px] text-[var(--ink-faint)]">{f.env}{saved ? ' · saved' : ''}</div>
    </div>
  );
}

function IntegrationCard({ integ }: { integ: Integration }) {
  const [open, setOpen] = useState(false);
  const filled = integ.fields.some((f) => fieldValue(f));
  return (
    <div className="glass overflow-hidden">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between px-3 py-2.5 text-left">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: filled ? 'var(--state-running)' : 'var(--ink-faint)' }} />
          <div>
            <div className="text-[12px] font-semibold">{integ.label}</div>
            <div className="text-[9px] text-[var(--ink-faint)]">{integ.usage === 'local' ? 'used by the app' : 'applied on the gateway'}</div>
          </div>
        </div>
        <span className="mono text-[12px] text-[var(--ink-dim)]">{open ? '−' : '+'}</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="flex flex-col gap-2.5 border-t border-[var(--hairline)] px-3 py-3">
              <p className="text-[10px] leading-snug text-[var(--ink-dim)]">{integ.blurb}</p>
              {integ.fields.map((f) => <Field key={f.env} f={f} />)}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function CredentialsManager() {
  const [snippet, setSnippet] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  // Secrets hydrate asynchronously (encrypted at rest) and change on "Forget
  // all" — re-mount the field tree when the config signals an update.
  const [version, setVersion] = useState(0);
  useEffect(() => {
    const bump = () => setVersion((v) => v + 1);
    window.addEventListener('nexus:config', bump);
    return () => window.removeEventListener('nexus:config', bump);
  }, []);

  const buildSnippet = () => {
    const text = envSnippet(gatewayEnvKeys());
    setSnippet(text || '# No gateway credentials entered yet');
  };
  const copy = async () => {
    if (snippet) {
      try {
        await navigator.clipboard.writeText(snippet);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      } catch {
        /* clipboard may be blocked */
      }
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[11px] leading-relaxed text-[var(--ink-dim)]">
        Enter any third-party connection here. <b className="text-[var(--ink)]">App</b> credentials
        apply immediately; <b className="text-[var(--ink)]">gateway</b> credentials are collected and
        exported as a <span className="mono">.env</span> snippet to paste on your gateway host
        (MUSE keeps provider/messaging keys server-side, by design). Values are stored only in this
        device’s local storage — clear them anytime with “Forget all”.
      </p>

      {CRED_CATEGORIES.map((cat) => {
        const items = integrationsByCategory(cat);
        if (!items.length) return null;
        return (
          <div key={cat}>
            <div className="hud-label mb-2">{cat}</div>
            <div className="flex flex-col gap-2">
              {items.map((i) => <IntegrationCard key={`${i.id}-${version}`} integ={i} />)}
            </div>
          </div>
        );
      })}

      {/* Gateway .env export */}
      <div className="glass px-3 py-3">
        <div className="hud-label mb-2">Gateway .env export</div>
        <p className="mb-2 text-[10px] text-[var(--ink-faint)]">
          Paste into <span className="mono">~/.hermes/.env</span> on the gateway host, then restart it.
        </p>
        <div className="flex gap-2">
          <button onClick={buildSnippet} className="flex-1 rounded-md px-3 py-2 text-[12px] font-semibold text-black" style={{ background: 'var(--octa-glow)' }}>
            Generate .env
          </button>
          {snippet && (
            <button onClick={copy} className="rounded-md border border-[var(--hairline)] px-3 py-2 text-[12px]">
              {copied ? 'Copied ✓' : 'Copy'}
            </button>
          )}
        </div>
        {snippet && (
          <pre className="mono mt-2 max-h-[30vh] overflow-auto rounded-md border border-[var(--hairline)] bg-[var(--panel-solid)] p-2.5 text-[10px] text-[var(--ink-dim)]">
            {snippet}
          </pre>
        )}
      </div>

      <button
        onClick={() => {
          INTEGRATIONS.flatMap((i) => i.fields).forEach((f) => saveField(f, ''));
          setSnippet(null);
          window.dispatchEvent(new CustomEvent('nexus:config'));
        }}
        className="rounded-md border border-[var(--state-error)] px-3 py-2 text-[12px] text-[var(--state-error)]"
      >
        Forget all credentials on this device
      </button>
    </div>
  );
}
